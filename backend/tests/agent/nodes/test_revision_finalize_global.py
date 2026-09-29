"""Tests for revision_planner, finalizer, and global_reviewer nodes."""

import json
import pytest

from app.agent.nodes.revision_planner import revision_planner_node
from app.agent.nodes.finalizer import finalizer_node, finalize_page
from app.agent.nodes.global_reviewer import global_reviewer_node, perform_global_review
from app.agent.state import create_initial_state
from app.models.page import PageState, PageType, PageStatus


@pytest.fixture
def state_with_pages(sample_spec):
    """State with multiple pages."""
    state = create_initial_state(
        project_id="test-001",
        spec=sample_spec,
        user_input="Test",
    )
    state["pages"]["page-01"] = PageState(
        page_id="page-01",
        page_type=PageType.COVER,
        status=PageStatus.COMPLETED,
        review_status="approved",
    )
    state["pages"]["page-02"] = PageState(
        page_id="page-02",
        page_type=PageType.CONTENT,
        status=PageStatus.REVIEWING,
        review_status="needs_revision",
        review_issues=[{
            "issue_id": "i1",
            "category": "alignment",
            "severity": "medium",
            "owner": "layout",
            "description": "misaligned",
        }],
        review_score=70,
    )
    return state


class TestRevisionPlannerNode:
    """Tests for revision_planner_node."""

    def test_revision_for_needs_revision(self, state_with_pages):
        """Revision planner generates plan for needs_revision."""
        state_with_pages["current_page_id"] = "page-02"

        # No mock needed - just test that it doesn't crash
        result_state = revision_planner_node(state_with_pages)
        # Should increment layout retry count
        assert result_state["layout_retry_count"] >= 1

    def test_revision_skipped_for_approved(self, state_with_pages):
        """Revision planner skips approved pages."""
        state_with_pages["current_page_id"] = "page-01"

        result_state = revision_planner_node(state_with_pages)
        # Should not modify state
        assert result_state["pages"]["page-01"].status == PageStatus.COMPLETED


class TestFinalizerNode:
    """Tests for finalizer_node."""

    def test_finalize_approved_page(self, sample_spec):
        """Finalizer marks approved page as completed."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        page = PageState(
            page_id="page-01",
            page_type=PageType.COVER,
            status=PageStatus.REVIEWING,
            review_status="approved",
        )
        state["pages"]["page-01"] = page
        state["current_page_id"] = "page-01"

        result_state = finalizer_node(state)
        assert result_state["pages"]["page-01"].status == PageStatus.COMPLETED
        assert "page-01" in result_state["workflow"].completed_pages

    def test_finalize_moves_to_next(self, sample_spec):
        """Finalizer moves to next page."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.COVER,
            status=PageStatus.PENDING,
            review_status="approved",
        )
        state["pages"]["page-02"] = PageState(
            page_id="page-02",
            page_type=PageType.CONTENT,
            status=PageStatus.PENDING,
        )
        state["current_page_id"] = "page-01"

        result_state = finalizer_node(state)
        # Should move to page-02
        assert result_state["current_page_id"] == "page-02"

    def test_finalize_no_more_pages(self, sample_spec):
        """Finalizer handles no more pages."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.COVER,
            status=PageStatus.PENDING,
            review_status="approved",
        )
        state["current_page_id"] = "page-01"

        result_state = finalizer_node(state)
        # No more pages
        assert result_state["current_page_id"] is None


class TestFinalizePageFunction:
    """Tests for standalone finalize_page function."""

    def test_finalize_page_standalone(self, sample_spec):
        """Standalone finalize_page returns dict."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.COVER,
            review_status="approved",
        )
        state["pages"]["page-02"] = PageState(
            page_id="page-02",
            page_type=PageType.CONTENT,
        )

        result = finalize_page("page-01", state)
        assert result["status"] == "completed"
        assert result["next_page_id"] == "page-02"

    def test_finalize_page_not_found(self, sample_spec):
        """Finalize non-existent page returns error."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        result = finalize_page("nonexistent", state)
        assert "error" in result


class TestGlobalReviewerNode:
    """Tests for global_reviewer_node."""

    def test_global_review_with_mock(self, mock_llm_with_responses, sample_spec):
        """Global reviewer checks consistency."""
        client = mock_llm_with_responses([{
            "status": "approved",
            "score": 88,
            "affected_pages": [],
            "consistency_issues": [],
            "recommendations": [],
        }])

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.COVER,
            status=PageStatus.COMPLETED,
            review_status="approved",
        )
        state["pages"]["page-02"] = PageState(
            page_id="page-02",
            page_type=PageType.CONTENT,
            status=PageStatus.COMPLETED,
            review_status="approved",
        )

        result_state = global_reviewer_node(state)
        assert result_state["global_review"] is not None
        assert result_state["global_review"]["status"] == "approved"

    def test_global_review_with_revision_needed(self, mock_llm_with_responses, sample_spec):
        """Global reviewer marks affected pages."""
        client = mock_llm_with_responses([{
            "status": "global_revision_required",
            "score": 65,
            "affected_pages": ["page-02"],
            "consistency_issues": [{
                "issue_id": "c1",
                "category": "consistency",
                "severity": "medium",
                "description": "inconsistent style",
            }],
            "recommendations": ["Use consistent fonts"],
        }])

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        state["pages"]["page-01"] = PageState(
            page_id="page-01",
            page_type=PageType.COVER,
            status=PageStatus.COMPLETED,
            review_status="approved",
        )
        state["pages"]["page-02"] = PageState(
            page_id="page-02",
            page_type=PageType.CONTENT,
            status=PageStatus.COMPLETED,
            review_status="approved",
        )

        result_state = global_reviewer_node(state)
        # Affected page should be marked
        assert result_state["pages"]["page-02"].review_status == "needs_revision"


class TestPerformGlobalReviewFunction:
    """Tests for standalone perform_global_review function."""

    def test_perform_global_review(self, mock_llm_with_responses):
        """Standalone global review function."""
        client = mock_llm_with_responses([{
            "status": "approved",
            "score": 90,
            "affected_pages": [],
            "consistency_issues": [],
            "recommendations": [],
        }])

        result = perform_global_review(
            project_id="p1",
            pages={"page-01": {"title": "t1"}},
            topic="Test",
            style="professional",
        )
        assert result["status"] == "approved"
        assert result["score"] == 90
