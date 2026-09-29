"""
Tests for the plan_outline → generate_parallel sequence.

These tests verify the fix for the "请先生成大纲" error that occurred when:
1. plan_outline failed silently (exception caught but status not updated to 'failed')
2. generate_parallel was then called but the stale project state had no outline
3. The error "请先生成大纲" was emitted because outline was empty

The fix ensures:
- cmd_plan_outline always updates status='failed' in memory_store before broadcasting
- cmd_generate_parallel always re-reads project from memory_store (fresh state)
- generate_parallel WITHOUT plan_outline first correctly emits "请先生成大纲"
- generate_parallel AFTER successful plan_outline works correctly
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.websocket import WorkflowRunner, _dispatch
from app.storage.memory import memory_store


# ==================== Scenarios that should emit "请先生成大纲" ====================

class TestOutlineRequired:
    """Verify generate_parallel requires a prior successful plan_outline."""

    @pytest.fixture(autouse=True)
    def fresh_store(self):
        memory_store._projects.clear()
        yield
        memory_store._projects.clear()

    @pytest.fixture
    def project_id(self):
        """A project in 'idle' state with no outline — simulating fresh creation."""
        project = WorkflowRunner.create_project(
            spec={"topic": "Test PPT", "page_count": 4},
            user_input="Make slides about testing",
        )
        return project["id"]

    @pytest.mark.asyncio
    async def test_generate_parallel_without_outline_emits_error(self, project_id):
        """Calling generate_parallel before plan_outline must emit the error."""
        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        await runner.cmd_generate_parallel(project_id)

        error_calls = [
            c for c in send.call_args_list
            if c.args[0]["type"] == "error"
        ]
        assert len(error_calls) == 1
        assert "大纲" in error_calls[0].args[0]["data"]["message"]

    @pytest.mark.asyncio
    async def test_generate_parallel_idle_status_after_failed_plan(self, project_id):
        """
        Simulate plan_outline failing (e.g. LLM exception) and leaving the
        project with status NOT set to 'failed'. Calling generate_parallel
        should STILL emit the outline error (not crash) and NOT attempt generation.
        """
        # Manually set an outline so we test the memory_store read path
        memory_store.update_project(project_id, {"outline": []})

        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        await runner.cmd_generate_parallel(project_id)

        # Must emit the outline error
        error_calls = [
            c for c in send.call_args_list
            if c.args[0]["type"] == "error"
        ]
        assert any("大纲" in c.args[0]["data"]["message"] for c in error_calls)

        # Must NOT emit parallel_status (generation must not start)
        parallel_calls = [
            c for c in send.call_args_list
            if c.args[0]["type"] == "parallel_status"
        ]
        assert len(parallel_calls) == 0

    @pytest.mark.asyncio
    async def test_generate_parallel_empty_outline_array_emits_error(self, project_id):
        """outline present but empty [] must also trigger the guard."""
        memory_store.update_project(project_id, {"outline": []})

        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        await runner.cmd_generate_parallel(project_id)

        error_calls = [
            c for c in send.call_args_list
            if c.args[0]["type"] == "error"
        ]
        assert any("大纲" in c.args[0]["data"]["message"] for c in error_calls)


# ==================== Scenarios that should SUCCEED ====================

class TestSuccessfulSequence:
    """Verify the happy path: plan_outline → generate_parallel works end-to-end."""

    @pytest.fixture(autouse=True)
    def fresh_store(self):
        memory_store._projects.clear()
        yield
        memory_store._projects.clear()

    @pytest.fixture
    def project_id(self):
        project = WorkflowRunner.create_project(
            spec={"topic": "Success Test", "page_count": 2},
            user_input="Test input",
        )
        return project["id"]

    @pytest.mark.asyncio
    async def test_plan_then_generate_succeeds(self, project_id):
        """plan_outline populates outline → generate_parallel runs the pipeline."""
        # Pre-populate with a real outline + page stubs
        memory_store.update_project(project_id, {
            "outline": [
                {
                    "page_id": "page-01",
                    "page_type": "cover",
                    "page_title": "Cover",
                    "key_points": [],
                    "subtitle": "",
                },
                {
                    "page_id": "page-02",
                    "page_type": "content",
                    "page_title": "Content",
                    "key_points": ["point a", "point b"],
                    "subtitle": "",
                },
            ],
            "pages": [
                {
                    "page_id": "page-01",
                    "page_type": "cover",
                    "title": "Cover",
                    "content": {
                        "title": "Cover", "subtitle": "",
                        "key_points": [], "bullet_points": [], "speaker_notes": "",
                    },
                    "layout": {"layout_type": "封面布局"},
                    "status": "pending",
                    "iteration": 1,
                    "max_iterations": 4,
                },
                {
                    "page_id": "page-02",
                    "page_type": "content",
                    "title": "Content",
                    "content": {
                        "title": "Content", "subtitle": "",
                        "key_points": ["point a", "point b"],
                        "bullet_points": [], "speaker_notes": "",
                    },
                    "layout": {"layout_type": "标题正文"},
                    "status": "pending",
                    "iteration": 1,
                    "max_iterations": 4,
                },
            ],
        })

        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        # Mock the LLM and all per-page nodes
        with patch("app.llm.config.get_llm_client") as mock_get, \
             patch("app.agent.nodes.planner_node") as mock_planner, \
             patch("app.agent.nodes.writer_node") as mock_writer, \
             patch("app.agent.nodes.designer_node") as mock_designer, \
             patch("app.agent.nodes.preview_renderer_node") as mock_preview, \
             patch("app.agent.nodes.critic_node") as mock_critic:

            mock_client = MagicMock()
            mock_client.config.is_configured.return_value = True
            mock_get.return_value = mock_client

            # planner_node: set a synthetic outline
            def passthrough(state):
                state["outline"] = [
                    {
                        "page_id": "page-01", "page_type": "cover",
                        "page_title": "Cover", "key_points": [],
                    },
                    {
                        "page_id": "page-02", "page_type": "content",
                        "page_title": "Content", "key_points": ["a", "b"],
                    },
                ]
                return state

            mock_planner.side_effect = passthrough

            # All per-page nodes: mark page approved
            def make_stub():
                def stub(state):
                    pid = state.get("current_page_id") or "page-01"
                    page = state["pages"].get(pid)
                    if page:
                        page.review_status = "approved"
                        page.review_score = 90.0
                    return state
                return stub

            mock_writer.side_effect = make_stub()
            mock_designer.side_effect = make_stub()
            mock_preview.side_effect = make_stub()
            mock_critic.side_effect = make_stub()

            # Step 1: plan_outline
            await runner.cmd_plan_outline(project_id)
            plan_event_types = {c.args[0]["type"] for c in send.call_args_list}
            assert "state_patch" in plan_event_types
            assert "error" not in plan_event_types

            # Verify memory_store was updated with outline
            saved_project = memory_store.get_project(project_id)
            assert saved_project["outline"] is not None
            assert len(saved_project["outline"]) > 0
            assert saved_project["status"] == "planned"

            # Step 2: generate_parallel — should NOT emit outline error
            send.reset_mock()
            await runner.cmd_generate_parallel(project_id)

            gen_error_calls = [
                c for c in send.call_args_list
                if c.args[0]["type"] == "error"
                and "大纲" in c.args[0]["data"]["message"]
            ]
            assert len(gen_error_calls) == 0, (
                f"Unexpected '请先生成大纲' error. All events: "
                f"{[c.args[0]['type'] for c in send.call_args_list]}"
            )

            # Should have started generation
            event_types = {c.args[0]["type"] for c in send.call_args_list}
            assert "parallel_status" in event_types
            assert "completed" in event_types

    @pytest.mark.asyncio
    async def test_plan_outline_llm_failure_marks_project_failed(self, project_id):
        """
        When planner_node raises an exception, cmd_plan_outline must:
        1. Set project.status = 'failed' in memory_store
        2. Broadcast state_patch with status='failed'
        3. Broadcast error event
        """
        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        with patch("app.llm.config.get_llm_client") as mock_get:
            mock_client = MagicMock()
            mock_client.config.is_configured.return_value = True
            mock_get.return_value = mock_client

            with patch("app.agent.nodes.planner_node") as mock_planner:
                mock_planner.side_effect = RuntimeError("LLM connection failed")

                await runner.cmd_plan_outline(project_id)

                # Verify status='failed' in memory_store
                saved_project = memory_store.get_project(project_id)
                assert saved_project["status"] == "failed"
                assert "LLM connection failed" in saved_project.get("error", "")

                # Verify state_patch was sent with status='failed'
                patch_calls = [
                    c for c in send.call_args_list
                    if c.args[0]["type"] == "state_patch"
                ]
                assert any(
                    c.args[0]["data"]["status"] == "failed"
                    for c in patch_calls
                )

                # Verify error event was sent
                error_calls = [
                    c for c in send.call_args_list
                    if c.args[0]["type"] == "error"
                ]
                assert len(error_calls) == 1
                assert "规划失败" in error_calls[0].args[0]["data"]["message"]

    @pytest.mark.asyncio
    async def test_generate_after_failed_plan_does_not_silently_start(self, project_id):
        """
        Plan fails (status='failed'), user clicks start generation.
        Must emit error, not silently attempt generation.
        """
        # Simulate failed plan: status='failed', no outline
        memory_store.update_project(project_id, {
            "status": "failed",
            "error": "规划失败: LLM error",
            "outline": [],
        })

        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        await runner.cmd_generate_parallel(project_id)

        # Must emit the outline error
        error_calls = [
            c for c in send.call_args_list
            if c.args[0]["type"] == "error"
        ]
        assert any("大纲" in c.args[0]["data"]["message"] for c in error_calls)

        # Must NOT emit parallel_status (generation must not start)
        assert not any(
            c.args[0]["type"] == "parallel_status"
            for c in send.call_args_list
        )
