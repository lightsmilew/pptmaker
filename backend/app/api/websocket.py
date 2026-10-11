"""
Bidirectional WebSocket gateway for PPTMaker.

Protocol (JSON over WebSocket):

  Client -> Server commands:
    - run_workflow:       Server decides the remaining stages and runs them
    - parse_input:        Run parser node on user_input
    - plan_outline:       Run planner node to produce outline
    - generate_parallel:  Start parallel page generation
    - render_pptx:        Render final PPTX file
    - update_spec:        Patch project spec
    - update_page:        Patch a single page
    - trigger_review:     Manually re-run the critic for a page
    - delete_project:     Remove the project
    - ping:               Keep-alive

  Server -> Client events:
    - initial_state:      Full project snapshot sent on connect
    - state_patch:        Incremental state update (any field)
    - parallel_status:    Aggregate parallel generation progress
    - page_updated:       Single page status change
    - preview_ready:      Preview image is available for a page
    - review_completed:   Critic result for a page
    - completed:          Generation finished (carries download_url)
    - error:              Error message
    - pong:               Keep-alive response
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from copy import deepcopy
from ..llm.telemetry import run_project_step
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from ..agent.state import (
    AgentState,
    create_initial_state,
    get_next_pending_page,
    state_to_project,
)
from ..config import settings
from ..models.page import PageState, PageStatus, PageType
from ..agent.review_policy import can_finalize, has_page_artifacts, repair_limit
from ..storage.memory import memory_store, template_kb
from ..storage.admin_repository import enforce_pages
from ..tools.pptx_generator import PPTXGenerator


# ==================== Connection Manager ====================

class ConnectionManager:
    """Manage WebSocket connections grouped by project_id."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.workflow_locks: Dict[str, asyncio.Lock] = {}
        self.workflow_tasks: Dict[str, asyncio.Task] = {}

    def workflow_running(self, project_id: str) -> bool:
        task = self.workflow_tasks.get(project_id)
        return task is not None and not task.done()

    async def start_workflow(self, project_id: str, command: str, **kwargs) -> None:
        """Keep a single process-local job alive independently of browser tabs."""
        project = memory_store.get_project(project_id)
        if project:
            enforce_pages(project.get("owner_id"), max((project.get("spec") or {}).get("page_count", 8), len(project.get("pages") or []), len(project.get("outline") or [])))
        if self.workflow_running(project_id):
            from .workspace import project_view
            project = memory_store.get_project(project_id)
            if project:
                await self.send_to_project(project_id, {"type":"state_patch", "data":project_view(project)})
            return

        async def send(message):
            await self.send_to_project(project_id, message)
        runner = WorkflowRunner(project_id,send)

        async def execute():
            try:
                await getattr(runner,command)(project_id,**kwargs)
            except asyncio.CancelledError:
                runner.cancel()
                memory_store.update_project(project_id,{"status":"failed", "error":"制作因服务中断而暂停，可继续制作。"})
                raise
            except Exception as exc:
                project = memory_store.get_project(project_id)
                if project:
                    project.update(status="failed",error=str(exc))
                    memory_store.update_project(project_id,project)
                    await runner._broadcast("state_patch",project)
                await send({"type":"error", "data":{"message":str(exc)}})
            finally:
                if self.workflow_tasks.get(project_id) is asyncio.current_task():
                    self.workflow_tasks.pop(project_id,None)
        self.workflow_tasks[project_id] = asyncio.create_task(execute())
        await asyncio.sleep(0)

    async def connect(self, websocket: WebSocket, project_id: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(project_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, project_id: str) -> None:
        if project_id in self.active_connections:
            self.active_connections[project_id].discard(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

    async def send_to_project(self, project_id: str, message: Dict[str, Any]) -> None:
        connections = self.active_connections.get(project_id, set()).copy()
        dead: list = []
        for ws in connections:
            try:
                await ws.send_json(jsonable_encoder(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, project_id)

    def has_connections(self, project_id: str) -> bool:
        return bool(self.active_connections.get(project_id))

    async def close_session(self, session_hash):
        for connections in list(self.active_connections.values()):
            for ws in list(connections):
                if getattr(ws.state, "session_hash", None) == session_hash:
                    await ws.close(code=4401)

    async def close_user(self, user_id):
        for connections in list(self.active_connections.values()):
            for ws in list(connections):
                if getattr(ws.state, "user_id", None) == user_id:
                    await ws.close(code=4401)


manager = ConnectionManager()


# ==================== Active Workflow Runner ====================

class WorkflowRunner:
    """
    Per-project workflow runner that orchestrates the LangGraph state machine
    and broadcasts all state changes over WebSocket.
    """

    def __init__(self, project_id: str, websocket_send):
        self.project_id = project_id
        self.send = websocket_send  # async callable(message: dict) -> None
        self._lock: Optional[asyncio.Lock] = None
        self._cancel = asyncio.Event()

    def _get_lock(self) -> asyncio.Lock:
        """Lazily create the asyncio.Lock (must be called from a running loop)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def cancel(self) -> None:
        self._cancel.set()

    async def _broadcast(self, event_type: str, data: Any) -> None:
        if event_type == "state_patch" and isinstance(data, dict) and data.get("id"):
            from .workspace import project_view
            data = project_view(data)
        await self.send({"type": event_type, "data": data})

    async def _broadcast_state(self, state: AgentState) -> None:
        await self._broadcast("state_patch", state_to_project(state))

    async def _start_stage(self, project, status, step, progress):
        project.update(status=status, current_step=step, progress=progress, error=None)
        memory_store.update_project(project["id"], project)
        await self._broadcast("state_patch", project)

    # ---------- Project creation ----------

    @staticmethod
    def create_project(
        spec: Optional[Dict[str, Any]],
        user_input: str = "",
        uploaded_files: Optional[list] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new project and persist its initial state."""
        project_id = f"proj_{uuid.uuid4().hex[:12]}"

        if spec is None:
            from ..storage.account_repository import account_repository
            preferences = account_repository(owner_id).profile()["preferences"]
            spec = {"topic": "未命名演示", "page_count": preferences["page_count"], "style": preferences["style"],
                    "layout_mode": preferences.get("layout_mode", "auto"), "content_density": preferences.get("content_density", "balanced"), "auto_images": preferences.get("auto_images", True)}
        spec = {"style": "自动", "auto_images": True, **spec}

        state = create_initial_state(
            project_id=project_id,
            spec=spec,
            user_input=user_input or "",
            uploaded_files=uploaded_files or [],
        )
        project_data = state_to_project(state)
        enforce_pages(owner_id, (project_data.get("spec") or {}).get("page_count", 8))
        project_data["owner_id"] = owner_id
        memory_store.create_project(project_id, project_data)
        return project_data

    # ---------- Spec / page updates ----------

    @staticmethod
    def update_spec(project_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        project = memory_store.get_project(project_id)
        if not project:
            return None
        current = dict(project.get("spec") or {})
        current.update(patch or {})
        enforce_pages(project.get("owner_id"), current.get("page_count", 8))
        project["spec"] = current
        if "style" in (patch or {}):
            project.pop("style_selection", None)
        memory_store.update_project(project_id, project)
        return project

    @staticmethod
    def update_page(
        project_id: str, page_id: str, patch: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        project = memory_store.get_project(project_id)
        if not project:
            return None

        pages = project.get("pages") or []
        page_index = next(
            (i for i, p in enumerate(pages) if p.get("page_id") == page_id),
            None,
        )
        if page_index is None:
            return None

        page = pages[page_index]
        for key, value in (patch or {}).items():
            if key in ("content", "layout", "review", "preview"):
                section = dict(page.get(key) or {})
                if isinstance(value, dict):
                    section.update(value)
                    page[key] = section
            else:
                page[key] = value

        pages[page_index] = page
        project["pages"] = pages
        project["status"] = "editing"
        memory_store.update_project(project_id, project)
        return project

    @staticmethod
    def delete_project(project_id: str) -> bool:
        return memory_store.delete_project(project_id)

    # ---------- Workflow commands ----------

    async def cmd_run_workflow(self, project_id: str) -> None:
        """Start/resume from persisted state; clients do not orchestrate stages."""
        lock = manager.workflow_locks.setdefault(project_id, asyncio.Lock())
        async with lock:
            await self._run_workflow(project_id)

    async def _run_workflow(self, project_id: str) -> None:
        project = memory_store.get_project(project_id)
        if not project:
            await self._broadcast("error", {"message": "项目不存在"})
            return
        self._cancel.clear()
        if project.get("status") == "completed":
            output = os.path.join(settings.storage_path, f"{project_id}.pptx")
            if os.path.isfile(output):
                await self._broadcast("state_patch", project)
                await self._broadcast("completed", {"download_url": f"/storage/{project_id}.pptx"})
                return
            if project.get("pages"):
                await self.cmd_render_pptx(project_id)
                return
        if project.get("status") == "editing":
            await self.cmd_render_pptx(project_id)
            return
        if not project.get("outline"):
            if project.get("status") != "parsed":
                await self.cmd_parse_input(project_id)
                project = memory_store.get_project(project_id)
                if self._cancel.is_set() or project.get("status") != "parsed":
                    return
            await self.cmd_plan_outline(project_id)
            project = memory_store.get_project(project_id)
            if self._cancel.is_set() or project.get("status") != "planned":
                return
        if not self._cancel.is_set():
            await self.cmd_generate_parallel(project_id)

    async def cmd_parse_input(self, project_id: str) -> None:
        from ..agent.nodes import parser_node

        project = memory_store.get_project(project_id)
        if not project:
            await self._broadcast("error", {"message": "项目不存在"})
            return

        async with self._get_lock():
            try:
                await self._start_stage(project, "parsing", "正在整理内容", 0)
                spec = project.get("spec") or {}
                user_input = project.get("user_input") or ""
                state = create_initial_state(project_id, spec, user_input)

                # Reuse persisted pages / outline so updates accumulate.
                state["outline"] = project.get("outline", []) or []

                state = await asyncio.to_thread(run_project_step, parser_node, state, project_id)

                if state.get("errors"):
                    raise ValueError(state["errors"][-1]["message"])
                parsed = state["project"].spec
                # Explicit form settings are authoritative; parsing supplies topic/notes.
                parsed.update({k: v for k, v in spec.items() if v not in (None, "") and not (k == "style" and v == "自动")})
                if state.get("style_selection"):
                    project["style_selection"] = state["style_selection"]
                enforce_pages(project.get("owner_id"), parsed.get("page_count", 8))
                project["spec"] = parsed
                project["status"] = "parsed"
                project["current_step"] = "输入已解析"
                project["progress"] = 10
                memory_store.update_project(project_id, project)

                await self._broadcast("state_patch", project)
                await self._broadcast("progress", {
                    "step": project["current_step"],
                    "progress": project["progress"],
                    "message": "",
                })
            except Exception as e:
                project["status"] = "failed"
                project["error"] = f"解析失败: {e}"
                memory_store.update_project(project_id, project)
                await self._broadcast("state_patch", project)
                await self._broadcast("error", {"message": f"解析失败: {e}"})

    async def cmd_plan_outline(self, project_id: str) -> None:
        from ..llm.config import get_llm_client
        from ..agent.nodes import planner_node

        project = memory_store.get_project(project_id)
        if not project:
            await self._broadcast("error", {"message": "项目不存在"})
            return

        try:
            llm = get_llm_client()
            if not llm.config.is_configured():
                message = "LLM 尚未配置，请在 backend/.env 中配置 API Key 并重启后端"
                memory_store.update_project(project_id, {"status":"failed", "error":message})
                await self._broadcast("state_patch", project)
                await self._broadcast("error", {"message": message})
                return
        except Exception as e:
            await self._broadcast("error", {"message": f"LLM 配置错误: {e}"})
            return

        if (project.get("spec") or {}).get("style") == "自动":
            await self.cmd_parse_input(project_id)
            if project.get("status") != "parsed":
                return

        async with self._get_lock():
            try:
                await self._start_stage(project, "planning", "正在规划大纲", 10)
                spec = project.get("spec") or {}
                user_input = project.get("user_input") or ""
                state = create_initial_state(project_id, spec, user_input)

                state = await asyncio.to_thread(run_project_step, planner_node, state, project_id)
                # Guard: if the planner itself reported a failure, surface it clearly
                # instead of masking it behind a misleading 'planned' status.
                planner_errors = state.get("errors") or []
                if planner_errors:
                    last_error = planner_errors[-1]
                    planner_msg = (
                        last_error.get("message", "规划失败")
                        if isinstance(last_error, dict)
                        else getattr(last_error, "message", str(last_error))
                    )
                    project["status"] = "failed"
                    project["error"] = planner_msg
                    memory_store.update_project(project_id, project)
                    await self._broadcast("state_patch", project)
                    await self._broadcast("error", {"message": planner_msg})
                    return

                outline = state.get("outline", []) or []
                if not outline:
                    # Empty outline is also a failure condition worth surfacing.
                    project["status"] = "failed"
                    project["error"] = "大纲生成为空，请重试"
                    memory_store.update_project(project_id, project)
                    await self._broadcast("state_patch", project)
                    await self._broadcast("error", {"message": "大纲生成为空，请检查主题设置后重试"})
                    return

                enforce_pages(project.get("owner_id"), len(outline))
                project["outline"] = outline
                # Initialize page stubs from outline
                existing_pages = {p.get("page_id"): p for p in project.get("pages") or []}
                new_pages = []
                for item in outline:
                    pid = item.get("page_id") or f"page-{len(new_pages) + 1:02d}"
                    if pid in existing_pages:
                        new_pages.append(existing_pages[pid])
                    else:
                        new_pages.append({
                            "page_id": pid,
                            "page_type": item.get("page_type", "content"),
                            "title": item.get("page_title", ""),
                            "content": {
                                "title": item.get("page_title", ""),
                                "subtitle": item.get("subtitle", ""),
                                "key_points": item.get("key_points", []),
                                "bullet_points": [],
                                "speaker_notes": "",
                                "image_id": item.get("image_id"),
                            },
                            "layout": {
                                "layout_type": item.get("suggest_layout", "title_content"),
                            },
                            "status": "pending",
                            "iteration": 1,
                            "max_iterations": 4,
                            "review": None,
                        })
                project["pages"] = new_pages
                project["status"] = "planned"
                project["current_step"] = "大纲已生成"
                project["progress"] = 25
                memory_store.update_project(project_id, project)

                # Broadcast the canonical project snapshot (not the freshly-built
                # AgentState, which still carries an empty `pages` dict).
                await self._broadcast("state_patch", project)
                await self._broadcast("progress", {
                    "step": project["current_step"],
                    "progress": project["progress"],
                    "message": "",
                })
            except Exception as e:
                project["status"] = "failed"
                project["error"] = f"规划失败: {e}"
                memory_store.update_project(project_id, project)
                await self._broadcast("state_patch", project)
                await self._broadcast("error", {"message": f"规划失败: {e}"})

    async def cmd_generate_parallel(self, project_id: str, force: bool = False) -> None:
        from ..agent.nodes import (
            writer_node,
            designer_node,
            preview_renderer_node,
            critic_node,
            revision_planner_node,
            finalizer_node,
        )

        project = memory_store.get_project(project_id)
        if not project:
            await self._broadcast("error", {"message": "项目不存在"})
            return

        outline = project.get("outline") or []
        if not outline:
            await self._broadcast("error", {"message": "请先生成大纲"})
            return

        pages = project.get("pages") or []
        page_count = len(pages)
        if page_count == 0:
            await self._broadcast("error", {"message": "没有可生成的页面"})
            return

        self._cancel.clear()

        async with self._get_lock():
            try:
                await self._start_stage(project, "generating", "正在制作页面", 30)
                # Initial parallel status
                pages_status = {p["page_id"]: "completed" if not force and p.get("status") == "completed" and
                                (p.get("review") or {}).get("status") == "approved" else "pending" for p in pages}
                await self._broadcast("parallel_status", {
                    "total_pages": page_count,
                    "completed_pages": sum(s == "completed" for s in pages_status.values()),
                    "failed_pages": 0,
                    "pages_status": dict(pages_status),
                })

                spec = project.get("spec") or {}
                user_input = project.get("user_input") or ""

                # Concurrency limit: keep enough parallelism for speed but don't
                # overwhelm the LLM proxy with concurrent requests.
                concurrency = min(max(1, int(os.getenv("PPT_CONCURRENCY", "3"))), 8, page_count)
                if project.get("owner_id"):
                    from ..storage.account_repository import account_repository
                    concurrency = min(concurrency, account_repository(project["owner_id"]).membership()["limits"]["concurrency"])
                semaphore = asyncio.Semaphore(concurrency)
                review_semaphore = asyncio.Semaphore(concurrency)
                # Shared only by the page tasks below. Each page owns its
                # AgentState, so stages can advance independently.
                page_states: Dict[str, AgentState] = {}

                async def _emit_progress(forced: str = "") -> None:
                    completed = sum(1 for s in pages_status.values() if s == "completed")
                    failed = sum(1 for s in pages_status.values() if s == "failed")
                    finished = completed + failed
                    progress = 30 + int((finished / max(page_count, 1)) * 70)
                    project["status"] = "generating"
                    project["current_step"] = (
                        forced
                        or f"已完成 {finished}/{page_count} 页"
                    )
                    project["progress"] = progress
                    memory_store.update_project(project_id, project)

                    await self._broadcast("progress", {
                        "step": project["current_step"],
                        "progress": progress,
                        "message": "",
                    })
                    await self._broadcast("parallel_status", {
                        "total_pages": page_count,
                        "completed_pages": completed,
                        "failed_pages": failed,
                        "pages_status": dict(pages_status),
                    })

                # ========== Phase 1: parallel write + design + preview ==========
                # Each page is processed independently by writer → designer →
                # preview_renderer. Review starts immediately for each page.
                async def _generate_initial(page_index: int, page_dict: Dict[str, Any]) -> Dict[str, Any]:
                    page_id = page_dict["page_id"]
                    async with semaphore:
                        if self._cancel.is_set():
                            return {"page_id": page_id, "page_index": page_index, "cancelled": True}

                        if pages_status[page_id] == "completed":
                            return {"page_id": page_id, "page_index": page_index, "skipped": True}

                        saved = self._hydrate_page(page_dict)
                        if not force and has_page_artifacts(saved) and saved.review_status:
                            # Retry review/repair of existing output; never rewrite
                            # already approved pages or discard a usable draft.
                            state = create_initial_state(project_id, spec, user_input)
                            state["outline"] = outline
                            saved.status = PageStatus.REVIEWING
                            saved.error = None
                            state["pages"][page_id] = saved
                            state["current_page_id"] = page_id
                            page_states[page_id] = state
                            try:
                                saved.iteration += 1
                                state = await asyncio.to_thread(run_project_step, preview_renderer_node, state, project_id)
                                if state["pages"][page_id].status == PageStatus.FAILED:
                                    raise ValueError(state["pages"][page_id].error)
                                self._save_page_preview(project, page_index, state["pages"][page_id])
                                memory_store.update_project(project_id, project)
                                return await _critique_and_revise(page_index, page_dict)
                            except Exception as exc:
                                return {"page_id": page_id, "page_index": page_index, "error": str(exc)}

                        self._update_page_field(project_id, page_index, "status", "writing")
                        await self._broadcast_page_updated(project_id, page_id, "writing")

                        state = create_initial_state(project_id, spec, user_input)
                        state["outline"] = outline
                        state["pages"][page_id] = self._hydrate_page(page_dict)
                        state["current_page_id"] = page_id

                        try:
                            state = await asyncio.to_thread(run_project_step, writer_node, state, project_id)
                            if state["pages"][page_id].status == PageStatus.FAILED:
                                raise ValueError(state["pages"][page_id].error)
                            page_obj = state["pages"].get(page_id)
                            if page_obj:
                                self._save_page_content(project, page_index, page_obj)
                                self._update_page_field(project_id, page_index, "status", "designing")
                                await self._broadcast_page_updated(project_id, page_id, "designing")

                            state = await asyncio.to_thread(run_project_step, designer_node, state, project_id)
                            if state["pages"][page_id].status == PageStatus.FAILED:
                                raise ValueError(state["pages"][page_id].error)
                            page_obj = state["pages"].get(page_id)
                            if page_obj:
                                self._save_page_layout(project, page_index, page_obj)
                                self._update_page_field(project_id, page_index, "status", "rendering")
                                await self._broadcast_page_updated(project_id, page_id, "rendering")

                            state = await asyncio.to_thread(run_project_step, preview_renderer_node, state, project_id)
                            if state["pages"][page_id].status == PageStatus.FAILED:
                                raise ValueError(state["pages"][page_id].error)
                            page_obj = state["pages"].get(page_id)
                            if page_obj and getattr(page_obj, "preview", None):
                                self._save_page_preview(project, page_index, page_obj)
                                memory_store.update_project(project_id, project)
                                await self._broadcast(
                                    "preview_ready",
                                    {
                                        "page_id": page_id,
                                        "image_path": page_obj.preview.image_path,
                                        "preview": page_obj.preview.model_dump(),
                                        "iteration": page_obj.iteration,
                                    },
                                )

                            page_states[page_id] = state
                            memory_store.update_project(project_id, project)
                            # The coroutine is resolved only after the full
                            # page pipeline helper is defined, so this review
                            # starts as soon as this page's preview is ready.
                            return await _critique_and_revise(page_index, page_dict)
                        except Exception as e:
                            return {
                                "page_id": page_id,
                                "page_index": page_index,
                                "error": str(e),
                            }

                # Execution is started after the critic coroutine is defined
                # below. This lets each task continue directly into review
                # without waiting for other pages to finish rendering.
                phase1_tasks = [_generate_initial(i, p) for i, p in enumerate(pages)]

                # ========== Per-page critic + revision ==========
                # Initial review plus bounded adjustments. Retain the best usable
                # iteration, without interpreting review advice as generation failure.
                MAX_REVISIONS = repair_limit()

                async def _critique_and_revise(page_index: int, page_dict: Dict[str, Any]) -> Dict[str, Any]:
                    page_id = page_dict["page_id"]
                    if page_id not in page_states:
                        return {"page_id": page_id, "page_index": page_index, "skipped": True}

                    async with review_semaphore:
                        if self._cancel.is_set():
                            return {"page_id": page_id, "page_index": page_index, "cancelled": True}

                        state = page_states[page_id]
                        preview_iteration = state["pages"][page_id].iteration

                        best_score = -1
                        best_page = None
                        # First critic call counts as iteration 1.
                        for iteration in range(1, MAX_REVISIONS + 2):
                            if self._cancel.is_set():
                                return {"page_id": page_id, "page_index": page_index, "cancelled": True}
                            state["critic_iteration"] = iteration - 1
                            page_obj = state["pages"].get(page_id)
                            if page_obj:
                                page_obj.iteration = iteration

                            state = await asyncio.to_thread(run_project_step, critic_node, state, project_id)
                            page_obj = state["pages"].get(page_id)
                            if not page_obj:
                                break
                            page_obj.iteration = preview_iteration + iteration - 1

                            self._save_page_review(project, page_index, page_obj)
                            memory_store.update_project(project_id, project)
                            await self._broadcast(
                                "review_completed",
                                {
                                    "page_id": page_id,
                                    "method": page_obj.review_method,
                                    "status": page_obj.review_status,
                                    "score": page_obj.review_score,
                                    "issues": page_obj.review_issues,
                                    "suggestions": page_obj.review_suggestions,
                                    "warning": page_obj.review_warning,
                                    "iteration": iteration,
                                },
                            )

                            score = page_obj.review_score or 0

                            # Track the best so far.
                            if score >= best_score or page_obj.review_status == "approved":
                                best_score = score
                                best_page = deepcopy(page_obj)

                            if page_obj.review_status == "approved":
                                break

                            if iteration > MAX_REVISIONS:
                                break

                            # Revision cycle: revise plan → re-design → re-render preview.
                            self._update_page_field(project_id, page_index, "status", "revising")
                            await self._broadcast_page_updated(project_id, page_id, "revising")

                            try:
                                from ..tools.slide_quality import review_scene
                                page_obj.review_status = "needs_revision"
                                state = await asyncio.to_thread(run_project_step, revision_planner_node, state, project_id)
                                if state["pages"][page_id].status == PageStatus.FAILED:
                                    raise ValueError(state["pages"][page_id].error)
                                local = review_scene(state["pages"][page_id].to_dict(), spec.get("style", "商务简约"))
                                content_issues = [issue for issue in page_obj.review_issues if issue.get("owner") == "content"]
                                if any(issue.get("owner") == "content" for issue in local["issues"]) or any(
                                        issue.get("category") != "overflow" for issue in content_issues):
                                    state = await asyncio.to_thread(run_project_step, writer_node, state, project_id)
                                    if state["pages"][page_id].status == PageStatus.FAILED:
                                        raise ValueError(state["pages"][page_id].error)
                                    state = await asyncio.to_thread(run_project_step, designer_node, state, project_id)
                                if state["pages"][page_id].status == PageStatus.FAILED:
                                    raise ValueError(state["pages"][page_id].error)
                                state["pages"][page_id].iteration = preview_iteration + iteration
                                state = await asyncio.to_thread(run_project_step, preview_renderer_node, state, project_id)
                                if state["pages"][page_id].status == PageStatus.FAILED:
                                    raise ValueError(state["pages"][page_id].error)
                            except Exception:
                                # A failed improvement must not destroy an earlier
                                # rendered page. Keep its content, geometry and preview.
                                if best_page is None or not has_page_artifacts(best_page):
                                    raise
                                best_page.review_warning = "本次自动调整未完成，已保留上一版页面，可继续调整。"
                                state["pages"][page_id] = deepcopy(best_page)
                                break
                            page_obj = state["pages"].get(page_id)
                            if page_obj:
                                self._save_page_content(project, page_index, page_obj)
                                self._save_page_layout(project, page_index, page_obj)
                            page_obj = state["pages"].get(page_id)
                            if page_obj and getattr(page_obj, "preview", None):
                                self._save_page_preview(project, page_index, page_obj)
                                memory_store.update_project(project_id, project)
                                await self._broadcast(
                                    "preview_ready",
                                    {
                                        "page_id": page_id,
                                        "image_path": page_obj.preview.image_path,
                                        "preview": page_obj.preview.model_dump(),
                                        "iteration": page_obj.iteration,
                                    },
                                )

                            self._update_page_field(project_id, page_index, "status", "reviewing")
                            await self._broadcast_page_updated(project_id, page_id, "reviewing")

                        # Final state for the page.
                        page_obj = state["pages"].get(page_id)
                        if not page_obj:
                            return {"page_id": page_id, "page_index": page_index}

                        if best_page is not None:
                            page_obj = deepcopy(best_page)
                            state["pages"][page_id] = page_obj
                        if page_obj.review_status != "approved" and has_page_artifacts(page_obj):
                            page_obj.review_warning = page_obj.review_warning or "已完成自动调整，仍有检查建议；可下载当前版本或继续调整。"
                        final_status = "completed" if can_finalize(page_obj) else "failed"
                        page_obj.status = PageStatus(final_status)
                        if final_status == "completed":
                            page_obj.error = None
                            self._update_page_field(project_id, page_index, "error", None)
                        self._save_page_content(project, page_index, page_obj)
                        self._save_page_layout(project, page_index, page_obj)
                        self._save_page_preview(project, page_index, page_obj)
                        self._save_page_review(project, page_index, page_obj)
                        self._update_page_field(project_id, page_index, "status", final_status)
                        pages_status[page_id] = final_status
                        await self._broadcast_page_updated(project_id, page_id, final_status)
                        # Publish aggregate progress as soon as this page
                        # finishes; do not wait for the batch gather.
                        await _emit_progress(forced=f"页面 {page_id} 已{('完成' if final_status == 'completed' else '失败')}")
                        return {
                            "page_id": page_id,
                            "page_index": page_index,
                            "final_status": final_status,
                            "score": page_obj.review_score,
                        }

                # Kick off independent page pipelines in parallel. There is
                # no phase barrier between rendering and review.
                results = await asyncio.gather(*phase1_tasks, return_exceptions=False)
                for result in results:
                    if isinstance(result, dict) and result.get("error"):
                        pid = result["page_id"]
                        idx = result["page_index"]
                        self._update_page_field(project_id, idx, "status", "failed")
                        self._update_page_field(project_id, idx, "error", str(result["error"]))
                        pages_status[pid] = "failed"
                        await self._broadcast_page_updated(project_id, pid, "failed")
                        await self._broadcast("error", {
                            "message": f"页面 {pid} 生成失败: {result['error']}",
                        })
                        await _emit_progress(forced=f"页面 {pid} 生成失败")

                await _emit_progress(forced="内容生成与评审完成")

                if self._cancel.is_set() or any(status != "completed" for status in pages_status.values()):
                    project["status"] = "failed"
                    project["error"] = "制作已中断，已生成页面保留，可继续制作。" if self._cancel.is_set() else "部分页面未能生成，已保留完成页面，请重试未完成页面。"
                    memory_store.update_project(project_id, project)
                    await self._broadcast("state_patch", project)
                    return
                # Export before sending a download URL; previously this file did not exist yet.
                os.makedirs(settings.storage_path, exist_ok=True)
                filepath = os.path.join(settings.storage_path, f"{project_id}.pptx")
                await asyncio.to_thread(PPTXGenerator().generate,
                    [self._normalize_page_for_export(p) for p in project["pages"]], filepath,
                    spec.get("topic", "PPT演示文稿"), template_kb.get_template(spec.get("style", "商务简约")))
                project["status"] = "completed"
                project["progress"] = 100
                project["current_step"] = "生成完成"
                project["error"] = None
                memory_store.update_project(project_id, project)
                await self._broadcast("state_patch", project)
                await self._broadcast("completed", {"download_url": f"/storage/{project_id}.pptx"})

            except Exception as e:
                project["status"] = "failed"
                project["error"] = str(e)
                memory_store.update_project(project_id, project)
                await self._broadcast("error", {"message": str(e)})

    async def cmd_trigger_review(self, project_id: str, page_id: str) -> None:
        project = memory_store.get_project(project_id)
        if not project:
            await self._broadcast("error", {"message": "项目不存在"})
            return

        pages = project.get("pages") or []
        page_index = next(
            (i for i, p in enumerate(pages) if p.get("page_id") == page_id), None
        )
        if page_index is None:
            await self._broadcast("error", {"message": "页面不存在"})
            return

        page = pages[page_index]
        async with self._get_lock():
            try:
                project["error"] = None
                state = create_initial_state(project_id, project.get("spec") or {}, project.get("user_input", ""))
                state["pages"][page_id] = self._hydrate_page(page)
                state["current_page_id"] = page_id
                from ..agent.nodes import critic_node
                state = await asyncio.to_thread(run_project_step, critic_node, state, project_id)
                reviewed = state["pages"][page_id]
                result = {"status": reviewed.review_status, "score": reviewed.review_score,
                          "warning": reviewed.review_warning,
                          "issues": reviewed.review_issues, "method": reviewed.review_method}
                usable = can_finalize(reviewed)
                if usable and result["status"] != "approved" and not result["warning"]:
                    result["warning"] = "此页仍有检查建议，可下载当前版本或继续调整。"
                page["review"] = {
                    "method": result.get("method"),
                    "status": result.get("status"),
                    "score": result.get("score"),
                    "warning": result.get("warning"),
                    "issues": result.get("issues", []),
                    "suggestions": [
                        i.get("suggested_action", "")
                        for i in result.get("issues", [])
                    ],
                }
                page["status"] = (
                    "completed" if usable else "failed" if reviewed.status == PageStatus.FAILED else "reviewing"
                )
                if usable:
                    page["error"] = None
                project["pages"][page_index] = page
                memory_store.update_project(project_id, project)

                await self._broadcast(
                    "review_completed",
                    {
                        "page_id": page_id,
                        "method": result.get("method"),
                        "status": result.get("status"),
                        "score": result.get("score"),
                        "warning": result.get("warning"),
                        "issues": result.get("issues", []),
                        "suggestions": page["review"]["suggestions"],
                    },
                )
                await self._broadcast_page_updated(
                    project_id, page_id, page["status"]
                )
            except Exception as e:
                await self._broadcast("error", {"message": f"评审失败: {e}"})

    async def cmd_render_pptx(self, project_id: str) -> None:
        project = memory_store.get_project(project_id)
        if not project:
            await self._broadcast("error", {"message": "项目不存在"})
            return

        pages = project.get("pages") or []
        if not pages:
            await self._broadcast("error", {"message": "没有可导出的页面"})
            return

        async with self._get_lock():
            try:
                await self._start_stage(project, "rendering", "正在导出文件", 98)
                os.makedirs(settings.storage_path, exist_ok=True)
                filename = f"{project_id}.pptx"
                filepath = os.path.join(settings.storage_path, filename)

                spec = project.get("spec") or {}
                title = spec.get("topic", "PPT演示文稿")
                style = spec.get("style", "简约商务")
                theme = template_kb.get_template(style)

                generator = PPTXGenerator()
                normalized_pages = [self._normalize_page_for_export(p) for p in pages]
                await asyncio.to_thread(generator.generate,
                    pages=normalized_pages,
                    output_path=filepath,
                    title=title,
                    theme=theme,
                )

                project["status"] = "completed"
                project["current_step"] = "导出完成"
                project["progress"] = 100
                project["error"] = None
                memory_store.update_project(project_id, project)
                await self._broadcast("state_patch", project)

                await self._broadcast(
                    "completed",
                    {"download_url": f"/storage/{filename}"},
                )
            except Exception as e:
                project.update(status="failed", error=f"导出失败: {e}")
                memory_store.update_project(project_id, project)
                await self._broadcast("state_patch", project)
                await self._broadcast("error", {"message": f"导出失败: {e}"})

    # ---------- Helpers ----------

    @staticmethod
    def _update_page_field(
        project_id: str, page_index: int, field: str, value: Any
    ) -> None:
        project = memory_store.get_project(project_id)
        if not project:
            return
        pages = project.get("pages") or []
        if 0 <= page_index < len(pages):
            pages[page_index][field] = value
            project["pages"] = pages
            memory_store.update_project(project_id, project)

    @staticmethod
    def _normalize_page_for_export(page_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten the stored page structure into the shape the PPTX generator
        expects: title / subtitle / key_points / bullet_points / chart_data /
        table_data / speaker_notes / style_config at the top level, plus the
        designer's layout_json + master_json promoted into a style_config.
        """
        page_dict = page_dict or {}
        content = page_dict.get("content") or {}
        layout = page_dict.get("layout") or {}
        if not isinstance(content, dict):
            content = {}
        if not isinstance(layout, dict):
            layout = {}

        layout_json = layout.get("layout_json") or {}
        master_json = layout.get("master_json") or {}

        # Promote the designer output to the generator's `style_config` key
        # so the inch-based, placeholder-driven renderer is used.
        style_config = None
        if layout_json or master_json:
            style_config = {
                "master": master_json,
                "layouts": [layout_json] if layout_json else [],
            }

        return {
            "page_id": page_dict.get("page_id"),
            "page_type": page_dict.get("page_type", "content"),
            "title": content.get("title", page_dict.get("title", "")),
            "subtitle": content.get("subtitle", page_dict.get("subtitle", "")),
            "key_points": content.get("key_points") or page_dict.get("key_points") or [],
            "bullet_points": content.get("bullet_points") or page_dict.get("bullet_points") or [],
            "chart_data": content.get("chart_data") or page_dict.get("chart_data"),
            "table_data": content.get("table_data") or page_dict.get("table_data"),
            "speaker_notes": content.get("speaker_notes", page_dict.get("speaker_notes", "")),
            "image_id": content.get("image_id", page_dict.get("image_id")),
            "style_config": style_config,
        }

    @staticmethod
    def _hydrate_page(page_dict: Dict[str, Any]) -> PageState:
        """Convert a stored page dict back to a PageState model."""
        content = page_dict.get("content") or {}
        layout = page_dict.get("layout") or {}
        review = page_dict.get("review") or {}
        try:
            return PageState(
                page_id=page_dict["page_id"],
                page_type=PageType(page_dict.get("page_type", "content")),
                title=content.get("title", page_dict.get("title", "")),
                subtitle=content.get("subtitle", page_dict.get("subtitle", "")),
                key_points=content.get("key_points", page_dict.get("key_points", []) or []),
                bullet_points=content.get(
                    "bullet_points", page_dict.get("bullet_points", []) or []
                ),
                speaker_notes=content.get("speaker_notes", page_dict.get("speaker_notes", "")),
                image_id=content.get("image_id", page_dict.get("image_id")),
                chart_data=content.get("chart_data", page_dict.get("chart_data")),
                table_data=content.get("table_data", page_dict.get("table_data")),
                layout_type=layout.get("layout_type", page_dict.get("layout_type", "title_content")),
                layout_json=layout.get("layout_json"),
                master_json=layout.get("master_json"),
                preview=page_dict.get("preview"),
                review_method=review.get("method"),
                review_status=review.get("status"),
                review_score=review.get("score"),
                review_issues=review.get("issues") or [],
                review_suggestions=review.get("suggestions") or [],
                review_warning=review.get("warning"),
                iteration=page_dict.get("iteration", 1),
                max_iterations=page_dict.get("max_iterations", 4),
                status=PageStatus(page_dict.get("status", "pending")),
            )
        except Exception:
            return PageState(page_id=page_dict["page_id"])

    @staticmethod
    def _save_page_content(project: Dict[str, Any], index: int, page: PageState) -> None:
        pages = project.get("pages") or []
        if not (0 <= index < len(pages)):
            return
        pages[index]["content"] = {
            "title": page.title,
            "subtitle": page.subtitle,
            "key_points": page.key_points,
            "bullet_points": page.bullet_points,
            "chart_data": page.chart_data,
            "table_data": page.table_data,
            "speaker_notes": page.speaker_notes,
            "image_id": page.image_id,
        }
        project["pages"] = pages

    @staticmethod
    def _save_page_layout(project: Dict[str, Any], index: int, page: PageState) -> None:
        pages = project.get("pages") or []
        if not (0 <= index < len(pages)):
            return

        pages[index].setdefault('content', {})['image_id'] = page.image_id
        pages[index]["layout"] = {
            "layout_type": page.layout_type,
            "layout_json": page.layout_json,
            "master_json": page.master_json,
        }
        project["pages"] = pages

    @staticmethod
    def _save_page_preview(project: Dict[str, Any], index: int, page: PageState) -> None:
        pages = project.get("pages") or []
        if not (0 <= index < len(pages)):
            return
        preview = getattr(page, "preview", None)
        if preview and hasattr(preview, "model_dump"):
            pages[index]["preview"] = preview.model_dump()
        project["pages"] = pages

    @staticmethod
    def _save_page_review(project: Dict[str, Any], index: int, page: PageState) -> None:
        pages = project.get("pages") or []
        if not (0 <= index < len(pages)):
            return
        pages[index]["review"] = {
            "method": page.review_method,
            "status": page.review_status,
            "score": page.review_score,
            "issues": page.review_issues,
            "suggestions": page.review_suggestions,
            "warning": page.review_warning,
        }
        pages[index]["iteration"] = page.iteration
        project["pages"] = pages

    async def _broadcast_page_updated(
        self, project_id: str, page_id: str, status: str
    ) -> None:
        await self._broadcast(
            "page_updated",
            {"page_id": page_id, "status": status},
        )


# ==================== WebSocket entrypoint ====================

async def websocket_handler(websocket: WebSocket, project_id: str) -> None:
    """Handle bidirectional WebSocket traffic for a project."""
    from .auth import check_origin, owned_project
    from ..storage.auth_repository import AuthRepository, SESSION_COOKIE, user_context
    from fastapi import HTTPException
    token = websocket.cookies.get(SESSION_COOKIE)
    session = AuthRepository().session(token)
    try:
        check_origin(websocket)
        if not session or session["scope"] != "user" or session["role"] != "user":
            raise HTTPException(401, "请先登录")
        owned_project(project_id, session["user_id"])
    except HTTPException as exc:
        await websocket.close(code=4401 if exc.status_code == 401 else 4404 if exc.status_code == 404 else 4403)
        return
    websocket.state.user_id = session["user_id"]
    websocket.state.session_hash = session["token_hash"]
    await manager.connect(websocket, project_id)

    async def send(message: Dict[str, Any]) -> None:
        try:
            await websocket.send_json(jsonable_encoder(message))
        except Exception:
            pass

    project = memory_store.get_project(project_id)
    if project:
        from .workspace import project_view
        await send({"type": "initial_state", "data": project_view(project)})
    else:
        await send({
            "type": "error",
            "data": {"message": f"项目 {project_id} 不存在"},
        })

    runner = WorkflowRunner(project_id, send)

    queue = asyncio.Queue(maxsize=32)
    async def process_commands():
        while True:
            message = await queue.get()
            try:
                if not AuthRepository().session(token):
                    await websocket.close(code=4401)
                    return
                owned_project(project_id, session["user_id"])
                context_token = user_context.set(session["user_id"])
                try:
                    await _dispatch(message, project_id, runner, send)
                finally:
                    user_context.reset(context_token)
            except Exception as exc:
                await send({"type": "error", "data": {"message": str(exc)}})
            finally:
                queue.task_done()
    worker = asyncio.create_task(process_commands())
    try:
        while True:
            raw = await websocket.receive_text()
            if not AuthRepository().session(token):
                await websocket.close(code=4401)
                break
            try:
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    raise ValueError("需要JSON对象")
            except (json.JSONDecodeError, ValueError):
                await send({"type": "error", "data": {"message": "消息格式错误，需要JSON对象"}})
                continue
            if msg.get("type") == "ping":
                await send({"type": "pong", "data": {"ts": time.time()}})
            elif queue.full():
                await send({"type": "error", "data": {"message": "命令队列已满，请稍后重试"}})
            else:
                queue.put_nowait(msg)
    except WebSocketDisconnect:
        pass
    finally:
        runner.cancel()
        worker.cancel()
        manager.disconnect(websocket, project_id)
        project = memory_store.get_project(project_id)
        if project and not manager.workflow_running(project_id) and project.get("status") in {"parsing", "planning", "generating", "reviewing", "rendering"}:
            memory_store.update_project(project_id, {"status": "failed", "current_step": "制作已中断",
                "error": "连接关闭中断了制作。材料与已生成页面已保留，可点击重新制作。"})
        await asyncio.gather(worker, return_exceptions=True)


async def _dispatch(
    msg: Dict[str, Any],
    project_id: str,
    runner: WorkflowRunner,
    send,
) -> None:
    """Route an incoming client message to the appropriate handler."""
    msg_type = msg.get("type")
    data = msg.get("data") or {}

    if msg_type == "ping":
        await send({"type": "pong", "data": {"ts": time.time()}})
        return

    if msg_type in {"run_workflow", "parse_input", "plan_outline", "generate_parallel", "render_pptx", "trigger_review"}:
        project = memory_store.get_project(project_id) or {}
        enforce_pages(project.get("owner_id"), max((project.get("spec") or {}).get("page_count", 8), len(project.get("pages") or []), len(project.get("outline") or [])))

    if msg_type == "run_workflow":
        await manager.start_workflow(project_id,"cmd_run_workflow")
        return

    if msg_type == "parse_input":
        await runner.cmd_parse_input(project_id)
        return

    if msg_type == "plan_outline":
        await runner.cmd_plan_outline(project_id)
        return

    if msg_type == "generate_parallel":
        if not isinstance(data, dict) or not isinstance(data.get("force", False), bool):
            await send({"type":"error", "data":{"message":"force 必须是布尔值"}})
            return
        await manager.start_workflow(project_id,"cmd_generate_parallel",force=data.get("force",False))
        return

    if msg_type == "render_pptx":
        await manager.start_workflow(project_id,"cmd_render_pptx")
        return

    if msg_type == "trigger_review":
        page_id = data.get("page_id")
        if not page_id:
            await send({"type": "error", "data": {"message": "缺少 page_id"}})
            return
        await runner.cmd_trigger_review(project_id, page_id)
        return

    if msg_type in {"update_spec", "update_page", "delete_project"} and manager.workflow_running(project_id):
        await send({"type":"error", "data":{"message":"正在制作，请完成后再修改。"}})
        return

    if msg_type == "update_spec":
        from ..contracts.project_input import validate_spec
        patch = validate_spec(data.get("patch") or {})
        project = WorkflowRunner.update_spec(project_id, patch)
        if project:
            await send({"type": "state_patch", "data": project})
        else:
            await send({"type": "error", "data": {"message": "项目不存在"}})
        return

    if msg_type == "update_page":
        page_id = data.get("page_id")
        patch = data.get("patch") or {}
        if not page_id:
            await send({"type": "error", "data": {"message": "缺少 page_id"}})
            return
        if not isinstance(patch, dict) or set(patch) - {"content","layout","title","page_type","status"}:
            await send({"type": "error", "data": {"message": "只能修改页面内容与排版"}})
            return
        project = WorkflowRunner.update_page(project_id, page_id, patch)
        if project:
            await send({"type": "state_patch", "data": project})
        else:
            await send({"type": "error", "data": {"message": "页面不存在"}})
        return

    if msg_type == "delete_project":
        if WorkflowRunner.delete_project(project_id):
            await send({"type": "state_patch", "data": {"id": project_id, "deleted": True}})
        else:
            await send({"type": "error", "data": {"message": "项目不存在"}})
        return

    await send({"type": "error", "data": {"message": f"未知命令: {msg_type}"}})


# ==================== Convenience helpers ====================

async def broadcast_update(project_id: str, event_type: str, data: Any) -> None:
    """Broadcast a generic update to all connections of a project."""
    await manager.send_to_project(project_id, {"type": event_type, "data": data})
