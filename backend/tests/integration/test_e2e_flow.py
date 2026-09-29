"""End-to-end tests for the unified state machine and WebSocket-driven flow."""

import asyncio
import json
import os
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.state import (
    create_initial_state,
    get_next_pending_page,
    all_pages_completed,
    state_to_project,
)
from app.models.page import PageState, PageType, PageStatus
from app.models.project import ProjectStatus


def make_sequential_llm(*responses):
    """Mock LLM client that returns the given responses in order."""
    mock = MagicMock()
    response_iter = iter(responses)

    def generate(*args, **kwargs):
        try:
            r = next(response_iter)
            if isinstance(r, dict):
                return json.dumps(r, ensure_ascii=False)
            return r
        except StopIteration:
            return '{"status": "ok"}'

    mock.generate = generate
    mock.generate_with_image = generate
    mock.config = MagicMock()
    mock.config.is_configured = MagicMock(return_value=True)
    return mock


# ==================== State machine lifecycle ====================

@pytest.mark.e2e
class TestStateLifecycle:
    """Single page through write -> design -> preview -> critic -> finalize."""

    def test_page_lifecycle_approved(self, sample_spec, mock_llm_with_responses):
        from app.agent.nodes import (
            writer_node, designer_node, preview_renderer_node,
            critic_node, finalizer_node,
        )

        mock_llm_with_responses([
            # Write
            {"title": "Test Page", "subtitle": "", "key_points": ["a", "b"],
             "bullet_points": ["bp1"], "speaker_notes": ""},
            # Design
            {
                "theme_name": "t",
                "master": {
                    "background": {"type": "solid", "rgb": [255, 255, 255]},
                    "logo": {"enable": False},
                    "color_scheme": {
                        "primary": [20, 40, 80], "secondary": [80, 100, 140],
                        "accent": [60, 120, 180], "text": [30, 30, 30], "light_text": [255, 255, 255],
                    },
                    "font_scheme": {
                        "title_font": "Arial", "body_font": "Arial", "title_size": 32, "body_size": 16,
                    },
                },
                "layouts": [{
                    "layout_id": "content", "type": "content",
                    "placeholders": [
                        {"name": "title", "type": "title", "x": 1, "y": 0.5, "w": 11, "h": 1},
                        {"name": "content", "type": "text", "x": 1, "y": 2, "w": 11, "h": 4},
                    ],
                }],
            },
            # Critic (approved)
            {"status": "approved", "score": 88,
             "dimensions": {"alignment": 9, "balance": 8, "readability": 9,
                            "hierarchy": 8, "density": 9, "consistency": 9},
             "issues": [], "next_action": "approve"},
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                state = create_initial_state(
                    project_id="test-e2e",
                    spec=sample_spec,
                    user_input="Test",
                )
                page = PageState(
                    page_id="page-01",
                    page_type=PageType.CONTENT,
                    title="",
                    key_points=[],
                )
                state["pages"]["page-01"] = page
                state["current_page_id"] = "page-01"
                state["outline"] = [{
                    "page_id": "page-01", "page_type": "content",
                    "page_title": "Test Page", "subtitle": "",
                    "key_points": ["a", "b"], "suggest_layout": "标题正文",
                }]

                state = writer_node(state)
                assert state["pages"]["page-01"].title == "Test Page"

                state = designer_node(state)
                assert state["pages"]["page-01"].layout_json is not None

                state = preview_renderer_node(state)

                state = critic_node(state)
                assert state["pages"]["page-01"].review_status == "approved"

                state = finalizer_node(state)
                assert state["pages"]["page-01"].status.value == "completed"
                assert all_pages_completed(state) is True
            finally:
                os.chdir(old_cwd)


# ==================== Error recovery ====================

@pytest.mark.e2e
class TestErrorRecovery:
    def test_designer_failure_does_not_crash(self, sample_spec, mock_llm_with_responses):
        from app.agent.nodes import writer_node, designer_node

        mock_llm_with_responses([
            {"title": "t", "subtitle": "", "key_points": ["a"], "bullet_points": ["b"], "speaker_notes": ""},
            "invalid json " * 20,
        ])

        state = create_initial_state(
            project_id="test-err", spec=sample_spec, user_input="Test",
        )
        page = PageState(
            page_id="page-01", page_type=PageType.CONTENT, title="", key_points=[],
        )
        state["pages"]["page-01"] = page
        state["current_page_id"] = "page-01"
        state["outline"] = [{
            "page_id": "page-01", "page_type": "content",
            "page_title": "Test", "key_points": ["a"], "suggest_layout": "标题正文",
        }]

        state = writer_node(state)
        assert state["pages"]["page-01"].title == "t"

        # Designer may fail but shouldn't crash the whole pipeline
        state = designer_node(state)
        assert state is not None


# ==================== Multi-page parallel flow ====================

@pytest.mark.e2e
class TestParallelFlow:
    """Verify get_next_pending_page picks up pages in order across iterations."""

    def test_multi_page_pending_resolution(self, sample_spec):
        state = create_initial_state(project_id="mp", spec=sample_spec, user_input="")
        for i in range(1, 5):
            state["pages"][f"page-0{i}"] = PageState(
                page_id=f"page-0{i}",
                page_type=PageType.CONTENT,
                status=PageStatus.PENDING,
            )

        # First pick
        assert get_next_pending_page(state) == "page-01"
        state["pages"]["page-01"].status = PageStatus.COMPLETED
        state["pages"]["page-01"].mark_completed()

        # Next pick
        assert get_next_pending_page(state) == "page-02"
        state["pages"]["page-02"].status = PageStatus.FAILED

        # Failure is also eligible for retry
        assert get_next_pending_page(state) == "page-02"
        state["pages"]["page-02"].status = PageStatus.COMPLETED

        assert get_next_pending_page(state) == "page-03"
        state["pages"]["page-03"].status = PageStatus.COMPLETED

        assert get_next_pending_page(state) == "page-04"
        state["pages"]["page-04"].status = PageStatus.COMPLETED

        assert get_next_pending_page(state) is None
        assert all_pages_completed(state) is True

    def test_state_to_project_serialization(self, sample_spec):
        state = create_initial_state(
            project_id="serial-test", spec=sample_spec, user_input="hi",
        )
        state["pages"]["p1"] = PageState(
            page_id="p1", page_type=PageType.COVER,
            title="Hello", subtitle="world", key_points=["a", "b"],
        )
        project = state_to_project(state)

        assert project["id"] == "serial-test"
        assert project["spec"]["topic"] == sample_spec["topic"]
        assert isinstance(project["pages"], list)
        assert project["pages"][0]["page_id"] == "p1"
        assert project["pages"][0]["content"]["title"] == "Hello"


# ==================== WebSocket end-to-end ====================

@pytest.mark.e2e
class TestWebSocketEndToEnd:
    """Exercise a full project lifecycle through the WebSocket gateway."""

    @pytest.fixture(autouse=True)
    def clear_store(self):
        from app.storage.memory import memory_store
        memory_store._projects.clear()
        yield
        memory_store._projects.clear()

    @pytest.mark.asyncio
    async def test_full_lifecycle_via_websocket(self, sample_spec, tmp_path):
        from app.api.websocket import WorkflowRunner, _dispatch
        from app.storage.memory import memory_store

        # Create project
        project = WorkflowRunner.create_project(
            spec=sample_spec,
            user_input="An AI overview",
        )
        project_id = project["id"]

        # Inject outline + page stubs
        memory_store.update_project(project_id, {
            "outline": [{
                "page_id": "page-01", "page_type": "cover",
                "page_title": "AI Overview", "key_points": ["intro", "scope"],
            }],
            "pages": [{
                "page_id": "page-01", "page_type": "cover",
                "content": {"title": "AI Overview", "subtitle": "",
                            "key_points": ["intro", "scope"], "bullet_points": [], "speaker_notes": ""},
                "layout": {"layout_type": "cover"},
                "status": "pending", "iteration": 1, "max_iterations": 4,
            }],
        })

        send = AsyncMock()
        runner = WorkflowRunner(project_id, send)

        # Mock the LLM and the per-page nodes
        with patch("app.llm.config.get_llm_client") as mock_get, \
             patch("app.agent.nodes.parser_node") as mock_parser, \
             patch("app.agent.nodes.planner_node") as mock_planner, \
             patch("app.agent.nodes.writer_node") as mock_writer, \
             patch("app.agent.nodes.designer_node") as mock_designer, \
             patch("app.agent.nodes.preview_renderer_node") as mock_preview, \
             patch("app.agent.nodes.critic_node") as mock_critic, \
             patch("app.api.websocket.PPTXGenerator") as mock_gen:
            mock_client = MagicMock()
            mock_client.config.is_configured.return_value = True
            mock_get.return_value = mock_client

            def passthrough(state):
                # Set a synthetic outline for plan_outline
                if "outline" not in state or not state.get("outline"):
                    state["outline"] = [{
                        "page_id": "page-01",
                        "page_type": "cover",
                        "page_title": "AI Overview",
                        "key_points": ["intro", "scope"],
                    }]
                return state

            mock_parser.side_effect = passthrough
            mock_planner.side_effect = passthrough

            def make_stub():
                def stub(state):
                    pid = state["current_page_id"]
                    page = state["pages"][pid]
                    page.review_status = "approved"
                    page.review_score = 90.0
                    return state
                return stub

            mock_writer.side_effect = make_stub()
            mock_designer.side_effect = make_stub()
            mock_preview.side_effect = make_stub()
            mock_critic.side_effect = make_stub()
            mock_gen.return_value.generate.return_value = None

            # Run the full chain via WebSocket commands
            await _dispatch({"type": "plan_outline"}, project_id, runner, send)
            await _dispatch({"type": "generate_parallel"}, project_id, runner, send)
            await _dispatch({"type": "render_pptx"}, project_id, runner, send)

            # Inspect the broadcast timeline
            event_types = [c.args[0]["type"] for c in send.call_args_list]
            assert "state_patch" in event_types
            assert "parallel_status" in event_types
            assert "completed" in event_types

            # The project should be marked completed after render
            project = memory_store.get_project(project_id)
            assert project["status"] == "completed"
