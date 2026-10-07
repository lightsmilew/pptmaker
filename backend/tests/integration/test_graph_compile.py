"""Test LangGraph workflow."""

import pytest
from unittest.mock import patch, MagicMock
import json

from app.agent.graph import (
    create_ppt_agent_graph,
    compile_graph,
    route_page_review,
    route_after_finalize,
    get_compiled_graph,
)
from app.agent.state import create_initial_state, get_next_pending_page
from app.models.page import PageState, PageType, PageStatus


def make_mock_llm(*responses):
    """Create mock LLM with sequential responses."""
    mock = MagicMock()
    response_iter = iter(responses)

    def generate(*args, **kwargs):
        try:
            r = next(response_iter)
            if isinstance(r, dict):
                return json.dumps(r)
            return r
        except StopIteration:
            return '{"status": "ok"}'

    mock.generate = generate
    mock.generate_with_image = generate
    return mock


class TestGraphRouting:
    """Tests for graph routing functions."""

    def test_route_page_review_approved(self, sample_spec):
        """Route returns approve for approved page."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            review_status="approved",
        )
        state["current_page_id"] = "page-01"

        result = route_page_review(state)
        assert result == "approve"

    def test_route_page_review_failed(self, sample_spec):
        """Route returns failed for failed page."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            review_status="failed",
        )
        state["current_page_id"] = "page-01"

        result = route_page_review(state)
        assert result == "failed"

    def test_route_page_review_blocked(self, sample_spec):
        """Route returns blocked for blocked page."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            review_status="blocked",
        )
        state["current_page_id"] = "page-01"

        result = route_page_review(state)
        assert result == "blocked"

    def test_route_page_review_needs_revision_layout(self, sample_spec):
        """Route returns revise_layout for layout issues."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            review_status="needs_revision",
            review_issues=[{
                "owner": "layout",
                "severity": "medium",
                "description": "misaligned",
            }],
        )
        state["current_page_id"] = "page-01"
        state["critic_iteration"] = 1

        result = route_page_review(state)
        assert result == "revise_layout"

    def test_route_page_review_max_iterations(self, sample_spec):
        """Unresolved layout problems do not become approved at the retry limit."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            review_status="needs_revision",
            review_issues=[{"owner": "layout", "severity": "medium"}],
        )
        state["current_page_id"] = "page-01"
        state["critic_iteration"] = 5  # Exceeds max of 4

        result = route_page_review(state)
        assert result == "failed"

    def test_route_after_finalize_more_pages(self, sample_spec):
        """Route returns next_page when more pages exist."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            status=PageStatus.COMPLETED,
        )
        state["pages"]["page-02"] = PageState(
            page_id="page-02",
            page_type=PageType.CONTENT,
            status=PageStatus.PENDING,
        )

        result = route_after_finalize(state)
        assert result == "next_page"
        assert state["current_page_id"] == "page-02"

    def test_route_after_finalize_all_done(self, sample_spec):
        """Route returns global_review when all done."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            status=PageStatus.COMPLETED,
        )

        result = route_after_finalize(state)
        assert result == "global_review"


class TestGraphCompilation:
    """Tests for graph compilation."""

    def test_create_graph(self):
        graph = create_ppt_agent_graph()
        assert graph is not None

    def test_compile_graph(self):
        compiled = compile_graph()
        assert compiled is not None

    def test_get_compiled_graph_singleton(self):
        g1 = get_compiled_graph()
        g2 = get_compiled_graph()
        assert g1 is g2

    def test_compiled_graph_can_invoke(self, sample_spec, mock_llm):
        """Compiled graph can be invoked end-to-end (all nodes stubbed)."""
        with patch("app.agent.nodes.parser_node") as mock_parser, \
             patch("app.agent.nodes.planner_node") as mock_planner, \
             patch("app.agent.nodes.writer_node") as mock_writer, \
             patch("app.agent.nodes.designer_node") as mock_designer, \
             patch("app.agent.nodes.preview_renderer_node") as mock_preview, \
             patch("app.agent.nodes.critic_node") as mock_critic, \
             patch("app.agent.nodes.finalizer_node") as mock_finalizer, \
             patch("app.agent.nodes.revision_planner_node") as mock_reviser, \
             patch("app.agent.nodes.global_reviewer_node") as mock_global, \
             patch("app.agent.graph.PPTXGenerator") as mock_pptx:
            def passthrough(state):
                return state
            for mock in [mock_parser, mock_planner, mock_writer, mock_designer,
                         mock_preview, mock_critic, mock_finalizer, mock_reviser,
                         mock_global]:
                mock.side_effect = passthrough
            mock_pptx.return_value.generate.return_value = None

            # Reset singleton for fresh compile
            import app.agent.graph as graph_mod
            graph_mod._compiled_graph = None
            graph = get_compiled_graph()
            initial = create_initial_state(
                project_id="g-test", spec=sample_spec, user_input="",
            )
            initial["pages"]["page-01"] = PageState(
                page_id="page-01", page_type=PageType.CONTENT,
                title="t", status=PageStatus.PENDING,
            )
            initial["pages"]["page-02"] = PageState(
                page_id="page-02", page_type=PageType.CONTENT,
                title="t", status=PageStatus.PENDING,
            )
            initial["pages"]["page-01"].mark_completed()

            result = graph.invoke(initial)
            assert result is not None
