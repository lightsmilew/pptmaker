"""Tests for the bidirectional WebSocket gateway.

Verifies:
- ConnectionManager connection lifecycle
- Initial state delivery
- Bidirectional command dispatch (parse_input, plan_outline, generate_parallel, etc.)
- WorkflowRunner static helpers (create_project, update_spec, update_page, delete_project)
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.websocket import (
    ConnectionManager,
    WorkflowRunner,
    _dispatch,
    manager,
)


# ==================== ConnectionManager ====================

class TestConnectionManager:
    """Connection lifecycle and broadcast isolation."""

    @pytest.fixture
    def conn_manager(self):
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_accepts_and_registers(self, conn_manager):
        ws = AsyncMock()
        await conn_manager.connect(ws, "p1")

        ws.accept.assert_called_once()
        assert ws in conn_manager.active_connections["p1"]

    @pytest.mark.asyncio
    async def test_disconnect_removes_websocket(self, conn_manager):
        ws = AsyncMock()
        await conn_manager.connect(ws, "p1")
        conn_manager.disconnect(ws, "p1")

        assert "p1" not in conn_manager.active_connections

    @pytest.mark.asyncio
    async def test_multiple_connections_same_project(self, conn_manager):
        await conn_manager.connect(AsyncMock(), "p1")
        await conn_manager.connect(AsyncMock(), "p1")

        assert len(conn_manager.active_connections["p1"]) == 2

    @pytest.mark.asyncio
    async def test_send_to_project_fans_out(self, conn_manager):
        ws1, ws2 = AsyncMock(), AsyncMock()
        await conn_manager.connect(ws1, "p1")
        await conn_manager.connect(ws2, "p1")

        await conn_manager.send_to_project("p1", {"type": "x", "data": {}})

        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_project_is_noop(self, conn_manager):
        # Should not raise
        await conn_manager.send_to_project("nope", {"type": "x"})

    @pytest.mark.asyncio
    async def test_failed_send_prunes_connection(self, conn_manager):
        ws_good, ws_bad = AsyncMock(), AsyncMock()
        ws_bad.send_json.side_effect = RuntimeError("socket closed")
        await conn_manager.connect(ws_good, "p1")
        await conn_manager.connect(ws_bad, "p1")

        await conn_manager.send_to_project("p1", {"type": "x"})

        assert ws_good in conn_manager.active_connections["p1"]
        assert ws_bad not in conn_manager.active_connections["p1"]

    @pytest.mark.asyncio
    async def test_send_serializes_message_with_jsonable_encoder(self, conn_manager):
        ws = AsyncMock()
        await conn_manager.connect(ws, "p1")
        from datetime import datetime
        # jsonable_encoder handles datetime -> ISO string
        await conn_manager.send_to_project("p1", {"type": "x", "data": {"ts": datetime.now()}})
        ws.send_json.assert_called_once()


# ==================== WorkflowRunner static helpers ====================

@pytest.fixture(autouse=True)
def clear_store():
    from app.storage.memory import memory_store
    memory_store._projects.clear()
    yield
    memory_store._projects.clear()


class TestWorkflowRunnerCreate:
    def test_create_project_with_full_spec(self):
        project = WorkflowRunner.create_project(
            spec={"topic": "AI", "page_count": 6},
            user_input="Make AI slides",
        )
        assert project["id"].startswith("proj_")
        assert project["spec"]["topic"] == "AI"
        assert project["user_input"] == "Make AI slides"
        assert project["status"] == "idle"

    def test_create_project_with_no_spec_uses_defaults(self):
        project = WorkflowRunner.create_project(spec=None)
        assert project["id"].startswith("proj_")
        assert "topic" in project["spec"]

    def test_create_project_persists_to_memory_store(self):
        project = WorkflowRunner.create_project(spec={"topic": "X"})
        from app.storage.memory import memory_store
        assert memory_store.get_project(project["id"]) is not None


class TestWorkflowRunnerUpdateSpec:
    def test_update_spec_merges_patch(self):
        project = WorkflowRunner.create_project(spec={"topic": "A", "page_count": 5})
        updated = WorkflowRunner.update_spec(
            project["id"], {"topic": "B", "style": "现代"}
        )
        assert updated["spec"]["topic"] == "B"
        assert updated["spec"]["page_count"] == 5  # preserved
        assert updated["spec"]["style"] == "现代"

    def test_update_spec_missing_project_returns_none(self):
        assert WorkflowRunner.update_spec("missing", {"topic": "x"}) is None


class TestWorkflowRunnerUpdatePage:
    def test_update_page_patches_existing_page(self):
        project = WorkflowRunner.create_project(spec={"topic": "T"})
        from app.storage.memory import memory_store
        memory_store.update_project(project["id"], {
            "pages": [{
                "page_id": "p-01",
                "title": "Old",
                "content": {"title": "Old content"},
            }]
        })
        updated = WorkflowRunner.update_page(
            project["id"], "p-01",
            {"title": "New", "content": {"title": "New content"}}
        )
        target = next(p for p in updated["pages"] if p["page_id"] == "p-01")
        assert target["title"] == "New"
        # Content was merged, not replaced
        assert target["content"]["title"] == "New content"

    def test_update_page_missing_returns_none(self):
        assert WorkflowRunner.update_page("missing", "p-01", {"title": "x"}) is None


class TestWorkflowRunnerDelete:
    def test_delete_project_removes_from_store(self):
        project = WorkflowRunner.create_project(spec={"topic": "X"})
        assert WorkflowRunner.delete_project(project["id"]) is True
        from app.storage.memory import memory_store
        assert memory_store.get_project(project["id"]) is None

    def test_delete_missing_returns_false(self):
        assert WorkflowRunner.delete_project("missing") is False


# ==================== Command dispatch ====================

class TestDispatch:
    """Verify client -> server commands are routed correctly."""

    @pytest.fixture
    def runner(self):
        return WorkflowRunner("proj-1", AsyncMock())

    @pytest.fixture
    def send(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_ping_returns_pong(self, runner, send):
        await _dispatch({"type": "ping", "data": {}}, "proj-1", runner, send)

        # First call should be pong
        send.assert_called()
        first_msg = send.call_args_list[0].args[0]
        assert first_msg["type"] == "pong"

    @pytest.mark.asyncio
    async def test_unknown_command_emits_error(self, runner, send):
        await _dispatch({"type": "nonsense", "data": {}}, "proj-1", runner, send)

        # Find the error message
        error_calls = [c for c in send.call_args_list if c.args[0]["type"] == "error"]
        assert len(error_calls) == 1
        assert "未知命令" in error_calls[0].args[0]["data"]["message"]

    @pytest.mark.asyncio
    async def test_update_spec_dispatches_to_runner(self, runner, send):
        project = WorkflowRunner.create_project(spec={"topic": "Old"})
        await _dispatch(
            {"type": "update_spec", "data": {"patch": {"topic": "New"}}},
            project["id"], runner, send,
        )

        # Should broadcast a state_patch
        patch_calls = [c for c in send.call_args_list if c.args[0]["type"] == "state_patch"]
        assert len(patch_calls) == 1
        assert patch_calls[0].args[0]["data"]["spec"]["topic"] == "New"

    @pytest.mark.asyncio
    async def test_update_spec_missing_project_sends_error(self, runner, send):
        await _dispatch(
            {"type": "update_spec", "data": {"patch": {"topic": "X"}}},
            "missing", runner, send,
        )
        error_calls = [c for c in send.call_args_list if c.args[0]["type"] == "error"]
        assert len(error_calls) == 1

    @pytest.mark.asyncio
    async def test_update_page_requires_page_id(self, runner, send):
        project = WorkflowRunner.create_project(spec={"topic": "T"})
        await _dispatch(
            {"type": "update_page", "data": {"patch": {"title": "X"}}},
            project["id"], runner, send,
        )
        error_calls = [c for c in send.call_args_list if c.args[0]["type"] == "error"]
        assert any("page_id" in c.args[0]["data"]["message"] for c in error_calls)

    @pytest.mark.asyncio
    async def test_delete_project_broadcasts_state_patch(self, runner, send):
        project = WorkflowRunner.create_project(spec={"topic": "X"})
        await _dispatch(
            {"type": "delete_project", "data": {}},
            project["id"], runner, send,
        )
        patch_calls = [c for c in send.call_args_list if c.args[0]["type"] == "state_patch"]
        assert any(c.args[0]["data"].get("deleted") for c in patch_calls)

    @pytest.mark.asyncio
    async def test_trigger_review_without_page_id_errors(self, runner, send):
        project = WorkflowRunner.create_project(spec={"topic": "T"})
        await _dispatch(
            {"type": "trigger_review", "data": {}},
            project["id"], runner, send,
        )
        error_calls = [c for c in send.call_args_list if c.args[0]["type"] == "error"]
        assert any("page_id" in c.args[0]["data"]["message"] for c in error_calls)


# ==================== Workflow command integration ====================

class TestWorkflowCommands:
    """End-to-end tests for cmd_* methods on WorkflowRunner."""

    @pytest.fixture
    def project_id(self):
        project = WorkflowRunner.create_project(
            spec={"topic": "Test", "page_count": 3},
            user_input="A test presentation",
        )
        return project["id"]

    @pytest.mark.asyncio
    async def test_parse_input_emits_state_patch(self, project_id):
        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        with patch("app.agent.nodes.parser_node") as mock_parser:
            # Mock parser returning state with parsed spec
            from app.models.project import ProjectStatus
            mock_state = {
                "project": MagicMock(status=ProjectStatus.IDLE, project_id=project_id, spec={}),
                "spec": {"topic": "Parsed Topic", "page_count": 3},
                "outline": [],
                "pages": {},
                "workflow": MagicMock(current_node="parse_input"),
            }
            mock_parser.return_value = mock_state

            await runner.cmd_parse_input(project_id)

            patch_calls = [c for c in send.call_args_list if c.args[0]["type"] == "state_patch"]
            assert len(patch_calls) >= 1

    @pytest.mark.asyncio
    async def test_parse_input_missing_project_sends_error(self):
        send = AsyncMock()
        runner = WorkflowRunner("nonexistent", send)

        await runner.cmd_parse_input("nonexistent")

        error_calls = [c for c in send.call_args_list if c.args[0]["type"] == "error"]
        assert len(error_calls) == 1
        assert "不存在" in error_calls[0].args[0]["data"]["message"]

    @pytest.mark.asyncio
    async def test_plan_outline_without_llm_config_emits_error(self, project_id):
        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        with patch("app.llm.config.get_llm_client") as mock_get:
            mock_client = MagicMock()
            mock_client.config.is_configured.return_value = False
            mock_get.return_value = mock_client

            await runner.cmd_plan_outline(project_id)

            error_calls = [c for c in send.call_args_list if c.args[0]["type"] == "error"]
            assert any("LLM" in c.args[0]["data"]["message"] for c in error_calls)

    @pytest.mark.asyncio
    async def test_generate_parallel_requires_outline(self, project_id):
        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        await runner.cmd_generate_parallel(project_id)

        error_calls = [c for c in send.call_args_list if c.args[0]["type"] == "error"]
        assert any("大纲" in c.args[0]["data"]["message"] for c in error_calls)

    @pytest.mark.asyncio
    async def test_generate_parallel_with_outline_runs_pipeline(self, project_id):
        from app.storage.memory import memory_store

        # Inject an outline + page stubs
        memory_store.update_project(project_id, {
            "outline": [
                {"page_id": "p-01", "page_type": "cover", "page_title": "Cover", "key_points": []},
            ],
            "pages": [{
                "page_id": "p-01",
                "page_type": "cover",
                "title": "Cover",
                "content": {"title": "Cover", "subtitle": "", "key_points": [], "bullet_points": [], "speaker_notes": ""},
                "layout": {"layout_type": "cover"},
                "status": "pending",
                "iteration": 1,
                "max_iterations": 4,
            }],
        })

        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        with patch("app.llm.config.get_llm_client") as mock_get, \
             patch("app.agent.nodes.writer_node") as mock_writer, \
             patch("app.agent.nodes.designer_node") as mock_designer, \
             patch("app.agent.nodes.preview_renderer_node") as mock_preview, \
             patch("app.agent.nodes.critic_node") as mock_critic:
            mock_client = MagicMock()
            mock_client.config.is_configured.return_value = True
            mock_get.return_value = mock_client

            # Stub each node to mark the page as approved
            def make_stub():
                def stub(state):
                    pid = state.get("current_page_id") or "p-01"
                    page = state["pages"][pid]
                    page.review_status = "approved"
                    page.review_score = 90.0
                    return state
                return stub

            mock_writer.side_effect = make_stub()
            mock_designer.side_effect = make_stub()
            mock_preview.side_effect = make_stub()
            mock_critic.side_effect = make_stub()

            await runner.cmd_generate_parallel(project_id)

            # Should broadcast parallel_status, page_updated (writing/designing/rendering/reviewing/completed),
            # preview_ready, review_completed, completed, progress.
            event_types = {c.args[0]["type"] for c in send.call_args_list}
            assert "parallel_status" in event_types
            assert "page_updated" in event_types
            assert "completed" in event_types

    @pytest.mark.asyncio
    async def test_render_pptx_requires_pages(self, project_id):
        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        await runner.cmd_render_pptx(project_id)

        error_calls = [c for c in send.call_args_list if c.args[0]["type"] == "error"]
        assert any("页面" in c.args[0]["data"]["message"] for c in error_calls)

    @pytest.mark.asyncio
    async def test_render_pptx_success_emits_completed(self, project_id, tmp_path):
        from app.storage.memory import memory_store
        memory_store.update_project(project_id, {
            "pages": [{
                "page_id": "p-01", "page_type": "cover",
                "content": {"title": "T", "subtitle": "", "key_points": [], "bullet_points": [], "speaker_notes": ""},
                "layout": {"layout_type": "cover"},
            }]
        })

        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        with patch("app.api.websocket.settings") as mock_settings, \
             patch("app.api.websocket.PPTXGenerator") as mock_gen:
            mock_settings.storage_path = str(tmp_path)
            mock_settings.default_page_count = 8
            mock_gen.return_value.generate.return_value = None

            await runner.cmd_render_pptx(project_id)

            completed_calls = [c for c in send.call_args_list if c.args[0]["type"] == "completed"]
            assert len(completed_calls) == 1
            assert completed_calls[0].args[0]["data"]["download_url"].endswith(".pptx")
