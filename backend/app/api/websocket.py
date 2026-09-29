"""
Bidirectional WebSocket gateway for PPTMaker.

Protocol (JSON over WebSocket):

  Client -> Server commands:
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
from ..storage.memory import memory_store, template_kb
from ..tools.pptx_generator import PPTXGenerator


# ==================== Connection Manager ====================

class ConnectionManager:
    """Manage WebSocket connections grouped by project_id."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}

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
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, project_id)

    def has_connections(self, project_id: str) -> bool:
        return bool(self.active_connections.get(project_id))


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
        await self.send({"type": event_type, "data": data})

    async def _broadcast_state(self, state: AgentState) -> None:
        await self._broadcast("state_patch", state_to_project(state))

    # ---------- Project creation ----------

    @staticmethod
    def create_project(
        spec: Optional[Dict[str, Any]],
        user_input: str = "",
        uploaded_files: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Create a new project and persist its initial state."""
        project_id = f"proj_{uuid.uuid4().hex[:12]}"

        if spec is None:
            spec = {"topic": "未命名PPT", "page_count": 8}

        state = create_initial_state(
            project_id=project_id,
            spec=spec,
            user_input=user_input or "",
            uploaded_files=uploaded_files or [],
        )
        project_data = state_to_project(state)
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
        project["spec"] = current
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

    async def cmd_parse_input(self, project_id: str) -> None:
        from ..agent.nodes import parser_node

        project = memory_store.get_project(project_id)
        if not project:
            await self._broadcast("error", {"message": "项目不存在"})
            return

        async with self._get_lock():
            try:
                spec = project.get("spec") or {}
                user_input = project.get("user_input") or ""
                state = create_initial_state(project_id, spec, user_input)

                # Reuse persisted pages / outline so updates accumulate.
                state["outline"] = project.get("outline", []) or []

                state = parser_node(state)

                if "spec" in state and isinstance(state["spec"], dict):
                    project["spec"] = state["spec"]
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
                await self._broadcast("error", {"message": "LLM 未配置，请先在设置中配置 API Key"})
                return
        except Exception as e:
            await self._broadcast("error", {"message": f"LLM 配置错误: {e}"})
            return

        async with self._get_lock():
            try:
                spec = project.get("spec") or {}
                user_input = project.get("user_input") or ""
                state = create_initial_state(project_id, spec, user_input)

                state = planner_node(state)

                # Guard: if the planner itself reported a failure, surface it clearly
                # instead of masking it behind a misleading 'planned' status.
                planner_errors = state.get("errors") or []
                if planner_errors:
                    planner_msg = planner_errors[-1].get("message", "规划失败")
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

    async def cmd_generate_parallel(self, project_id: str) -> None:
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
                # Initial parallel status
                pages_status = {p["page_id"]: "pending" for p in pages}
                await self._broadcast("parallel_status", {
                    "total_pages": page_count,
                    "completed_pages": 0,
                    "failed_pages": 0,
                    "pages_status": dict(pages_status),
                })

                spec = project.get("spec") or {}
                user_input = project.get("user_input") or ""

                # Concurrency limit: keep enough parallelism for speed but don't
                # overwhelm the LLM proxy with concurrent requests.
                concurrency = min(3, page_count)
                semaphore = asyncio.Semaphore(concurrency)

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
                # preview_renderer. The critic/revision loop runs in phase 2.
                async def _generate_initial(page_index: int, page_dict: Dict[str, Any]) -> Dict[str, Any]:
                    page_id = page_dict["page_id"]
                    async with semaphore:
                        if self._cancel.is_set():
                            return {"page_id": page_id, "page_index": page_index, "cancelled": True}

                        self._update_page_field(project_id, page_index, "status", "writing")
                        await self._broadcast_page_updated(project_id, page_id, "writing")

                        state = create_initial_state(project_id, spec, user_input)
                        state["outline"] = outline
                        state["pages"][page_id] = self._hydrate_page(page_dict)
                        state["current_page_id"] = page_id

                        try:
                            state = writer_node(state)
                            page_obj = state["pages"].get(page_id)
                            if page_obj:
                                self._save_page_content(project, page_index, page_obj)
                                self._update_page_field(project_id, page_index, "status", "designing")
                                await self._broadcast_page_updated(project_id, page_id, "designing")

                            state = designer_node(state)
                            page_obj = state["pages"].get(page_id)
                            if page_obj:
                                self._save_page_layout(project, page_index, page_obj)
                                self._update_page_field(project_id, page_index, "status", "rendering")
                                await self._broadcast_page_updated(project_id, page_id, "rendering")

                            state = preview_renderer_node(state)
                            page_obj = state["pages"].get(page_id)
                            if page_obj and getattr(page_obj, "preview", None):
                                self._save_page_preview(project, page_index, page_obj)
                                await self._broadcast(
                                    "preview_ready",
                                    {
                                        "page_id": page_id,
                                        "image_path": page_obj.preview.image_path,
                                        "iteration": page_obj.iteration,
                                    },
                                )

                            memory_store.update_project(project_id, project)
                            return {
                                "page_id": page_id,
                                "page_index": page_index,
                                "state": state,
                                "page_obj": page_obj,
                            }
                        except Exception as e:
                            return {
                                "page_id": page_id,
                                "page_index": page_index,
                                "error": str(e),
                            }

                phase1_results = await asyncio.gather(
                    *[_generate_initial(i, p) for i, p in enumerate(pages)],
                    return_exceptions=False,
                )

                # Re-build per-page state map for phase 2.
                page_states: Dict[str, AgentState] = {}
                for result in phase1_results:
                    if result.get("error"):
                        pid = result["page_id"]
                        idx = result["page_index"]
                        self._update_page_field(project_id, idx, "status", "failed")
                        self._update_page_field(project_id, idx, "error", str(result["error"]))
                        pages_status[pid] = "failed"
                        await self._broadcast_page_updated(project_id, pid, "failed")
                        await self._broadcast("error", {
                            "message": f"页面 {pid} 初始生成失败: {result['error']}",
                        })
                        continue
                    if result.get("cancelled"):
                        continue
                    page_states[result["page_id"]] = result["state"]

                # ========== Phase 2: parallel critic + revision ==========
                # For each page: up to 3 revision rounds, with a score-monotonic
                # guard. If a new revision scores lower than the previous, we
                # stop and keep the better iteration (avoid score thrashing).
                MAX_REVISIONS = 3

                async def _critique_and_revise(page_index: int, page_dict: Dict[str, Any]) -> Dict[str, Any]:
                    page_id = page_dict["page_id"]
                    if page_id not in page_states:
                        return {"page_id": page_id, "page_index": page_index, "skipped": True}

                    async with semaphore:
                        if self._cancel.is_set():
                            return {"page_id": page_id, "page_index": page_index, "cancelled": True}

                        state = page_states[page_id]

                        best_score = 0
                        best_status = "needs_revision"
                        best_issues: List[Dict[str, Any]] = []
                        # First critic call counts as iteration 1.
                        for iteration in range(1, MAX_REVISIONS + 1):
                            state["critic_iteration"] = iteration
                            page_obj = state["pages"].get(page_id)
                            if page_obj:
                                page_obj.iteration = iteration

                            state = critic_node(state)
                            page_obj = state["pages"].get(page_id)
                            if not page_obj:
                                break

                            self._save_page_review(project, page_index, page_obj)
                            await self._broadcast(
                                "review_completed",
                                {
                                    "page_id": page_id,
                                    "status": page_obj.review_status,
                                    "score": page_obj.review_score,
                                    "issues": page_obj.review_issues,
                                    "suggestions": page_obj.review_suggestions,
                                    "iteration": iteration,
                                },
                            )

                            score = page_obj.review_score or 0

                            # If the revision didn't improve over the previous
                            # best (or initial baseline of 0), stop and keep
                            # the previous iteration's layout.
                            if iteration > 1 and score < best_score:
                                # Roll back the score in broadcast and stop.
                                page_obj.review_status = best_status
                                page_obj.review_score = best_score
                                page_obj.review_issues = best_issues
                                self._save_page_review(project, page_index, page_obj)
                                await self._broadcast(
                                    "review_completed",
                                    {
                                        "page_id": page_id,
                                        "status": best_status,
                                        "score": best_score,
                                        "issues": best_issues,
                                        "suggestions": [],
                                        "iteration": iteration,
                                        "stopped_reason": "score_not_improving",
                                    },
                                )
                                break

                            # Track the best so far.
                            if score > best_score:
                                best_score = score
                                best_status = page_obj.review_status
                                best_issues = page_obj.review_issues

                            if page_obj.review_status == "approved":
                                break

                            if iteration >= MAX_REVISIONS:
                                break

                            # Revision cycle: revise plan → re-design → re-render preview.
                            self._update_page_field(project_id, page_index, "status", "revising")
                            await self._broadcast_page_updated(project_id, page_id, "revising")

                            state = revision_planner_node(state)
                            state = designer_node(state)
                            page_obj = state["pages"].get(page_id)
                            if page_obj:
                                self._save_page_layout(project, page_index, page_obj)

                            state = preview_renderer_node(state)
                            page_obj = state["pages"].get(page_id)
                            if page_obj and getattr(page_obj, "preview", None):
                                self._save_page_preview(project, page_index, page_obj)
                                await self._broadcast(
                                    "preview_ready",
                                    {
                                        "page_id": page_id,
                                        "image_path": page_obj.preview.image_path,
                                        "iteration": page_obj.iteration,
                                    },
                                )

                            self._update_page_field(project_id, page_index, "status", "reviewing")
                            await self._broadcast_page_updated(project_id, page_id, "reviewing")

                        # Final state for the page.
                        page_obj = state["pages"].get(page_id)
                        if not page_obj:
                            return {"page_id": page_id, "page_index": page_index}

                        # Final state for the page. Anything that produced a
                        # usable review (approved, blocked with a reasonable
                        # score, or needs_revision that scored >= 70) is
                        # considered done; pure failures fall through to failed.
                        score = page_obj.review_score or 0
                        if page_obj.review_status == "approved":
                            final_status = "completed"
                        elif page_obj.review_status == "blocked" and score >= 70:
                            final_status = "completed"
                        elif page_obj.review_status in ("needs_revision", "blocked") and score >= 70:
                            final_status = "completed"
                        else:
                            final_status = "failed"
                        self._update_page_field(project_id, page_index, "status", final_status)
                        pages_status[page_id] = final_status
                        await self._broadcast_page_updated(project_id, page_id, final_status)
                        return {
                            "page_id": page_id,
                            "page_index": page_index,
                            "final_status": final_status,
                            "score": page_obj.review_score,
                        }

                # Kick off all critics in parallel.
                await asyncio.gather(
                    *[_critique_and_revise(i, p) for i, p in enumerate(pages)],
                )

                await _emit_progress(forced="内容生成与评审完成")

                project["status"] = "completed"
                project["progress"] = 100
                project["current_step"] = "生成完成"
                memory_store.update_project(project_id, project)

                await self._broadcast("state_patch", project)
                await self._broadcast(
                    "completed",
                    {"download_url": f"/storage/{project_id}.pptx"},
                )

            except Exception as e:
                project["status"] = "failed"
                project["error"] = str(e)
                memory_store.update_project(project_id, project)
                await self._broadcast("error", {"message": str(e)})

    async def cmd_trigger_review(self, project_id: str, page_id: str) -> None:
        from ..agent.nodes import review_page

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
                result = review_page(
                    page_id=page_id,
                    page_data=page.get("content", {}),
                    preview_path=(page.get("preview") or {}).get("image_path", ""),
                    layout_type=page.get("layout", {}).get("layout_type", "title_content"),
                    iteration=page.get("iteration", 1),
                    previous_issues=(page.get("review") or {}).get("issues"),
                )
                page["review"] = {
                    "status": result.get("status"),
                    "score": result.get("score"),
                    "issues": result.get("issues", []),
                    "suggestions": [
                        i.get("suggested_action", "")
                        for i in result.get("issues", [])
                    ],
                }
                page["status"] = (
                    "completed" if result.get("status") == "approved" else "reviewing"
                )
                project["pages"][page_index] = page
                memory_store.update_project(project_id, project)

                await self._broadcast(
                    "review_completed",
                    {
                        "page_id": page_id,
                        "status": result.get("status"),
                        "score": result.get("score"),
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
                os.makedirs(settings.storage_path, exist_ok=True)
                filename = f"{project_id}.pptx"
                filepath = os.path.join(settings.storage_path, filename)

                spec = project.get("spec") or {}
                title = spec.get("topic", "PPT演示文稿")
                style = spec.get("style", "简约商务")
                theme = template_kb.get_template(style)

                generator = PPTXGenerator()
                normalized_pages = [self._normalize_page_for_export(p) for p in pages]
                generator.generate(
                    pages=normalized_pages,
                    output_path=filepath,
                    title=title,
                    theme=theme,
                )

                project["status"] = "completed"
                project["current_step"] = "导出完成"
                memory_store.update_project(project_id, project)

                await self._broadcast(
                    "completed",
                    {"download_url": f"/storage/{filename}"},
                )
            except Exception as e:
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
        content = page_dict.get("content") or {}
        layout = page_dict.get("layout") or {}

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
            "style_config": style_config,
        }

    @staticmethod
    def _hydrate_page(page_dict: Dict[str, Any]) -> PageState:
        """Convert a stored page dict back to a PageState model."""
        content = page_dict.get("content") or {}
        layout = page_dict.get("layout") or {}
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
                layout_type=layout.get("layout_type", page_dict.get("layout_type", "title_content")),
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
            "speaker_notes": page.speaker_notes,
        }
        project["pages"] = pages

    @staticmethod
    def _save_page_layout(project: Dict[str, Any], index: int, page: PageState) -> None:
        pages = project.get("pages") or []
        if not (0 <= index < len(pages)):
            return
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
            "status": page.review_status,
            "score": page.review_score,
            "issues": page.review_issues,
            "suggestions": page.review_suggestions,
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
    await manager.connect(websocket, project_id)

    async def send(message: Dict[str, Any]) -> None:
        try:
            await websocket.send_json(jsonable_encoder(message))
        except Exception:
            pass

    project = memory_store.get_project(project_id)
    if project:
        await send({"type": "initial_state", "data": project})
    else:
        await send({
            "type": "error",
            "data": {"message": f"项目 {project_id} 不存在"},
        })

    runner = WorkflowRunner(project_id, send)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send({"type": "error", "data": {"message": "消息格式错误，需要 JSON"}})
                continue

            await _dispatch(msg, project_id, runner, send)

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, project_id)


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

    if msg_type == "parse_input":
        await runner.cmd_parse_input(project_id)
        return

    if msg_type == "plan_outline":
        await runner.cmd_plan_outline(project_id)
        return

    if msg_type == "generate_parallel":
        await runner.cmd_generate_parallel(project_id)
        return

    if msg_type == "render_pptx":
        await runner.cmd_render_pptx(project_id)
        return

    if msg_type == "trigger_review":
        page_id = data.get("page_id")
        if not page_id:
            await send({"type": "error", "data": {"message": "缺少 page_id"}})
            return
        await runner.cmd_trigger_review(project_id, page_id)
        return

    if msg_type == "update_spec":
        project = WorkflowRunner.update_spec(project_id, data.get("patch") or {})
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
