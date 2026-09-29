"""Tests for agent/state.py."""

import pytest
from datetime import datetime

from app.agent.state import (
    AgentState,
    create_initial_state,
    state_to_project,
    get_current_page,
    get_next_pending_page,
    get_completed_pages,
    all_pages_completed,
    reset_retry_counters,
    increment_critic_iteration,
)
from app.models.project import ProjectState, ProjectStatus
from app.models.page import PageState, PageStatus, PageType


@pytest.fixture
def initial_state(sample_spec):
    """Create a basic initial state."""
    return create_initial_state(
        project_id="test-proj-001",
        spec=sample_spec,
        user_input="Test input",
        page_count=4,
    )


class TestCreateInitialState:
    """Tests for create_initial_state."""

    def test_create_basic(self, sample_spec):
        """Create initial state with required params."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
        )
        assert state["project"].project_id == "test-001"
        assert state["workflow"].total_pages == sample_spec["page_count"]
        assert state["pages"] == {}
        assert state["current_page_id"] is None
        assert state["errors"] == []

    def test_create_with_user_input(self, sample_spec):
        """Create with user input."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="My PPT about Python",
        )
        assert state["user_input"] == "My PPT about Python"

    def test_create_with_uploaded_files(self, sample_spec):
        """Create with uploaded files."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            uploaded_files=["file1.txt", "file2.md"],
        )
        assert state["uploaded_files"] == ["file1.txt", "file2.md"]

    def test_retry_counters_initialized(self, sample_spec):
        """All retry counters start at 0."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
        )
        assert state["content_retry_count"] == 0
        assert state["layout_retry_count"] == 0
        assert state["critic_iteration"] == 0
        assert state["json_retry_count"] == 0


class TestStateToProject:
    """Tests for state_to_project."""

    def test_basic_conversion(self, initial_state):
        """Convert state to project dict."""
        project_dict = state_to_project(initial_state)
        assert project_dict["id"] == "test-proj-001"
        assert project_dict["spec"] == initial_state["project"].spec
        assert project_dict["user_input"] == "Test input"
        assert project_dict["pages"] == []


class TestPageNavigation:
    """Tests for page navigation helpers."""

    def test_get_current_page_none(self, initial_state):
        """Get current page when not set."""
        assert get_current_page(initial_state) is None

    def test_get_current_page(self, initial_state):
        """Get current page when set."""
        page = PageState(page_id="page-01")
        initial_state["pages"]["page-01"] = page
        initial_state["current_page_id"] = "page-01"
        assert get_current_page(initial_state) == page

    def test_get_next_pending_page(self, initial_state):
        """Find next pending page."""
        page1 = PageState(page_id="page-01", status=PageStatus.COMPLETED)
        page2 = PageState(page_id="page-02", status=PageStatus.PENDING)
        page3 = PageState(page_id="page-03", status=PageStatus.PENDING)

        initial_state["pages"]["page-01"] = page1
        initial_state["pages"]["page-02"] = page2
        initial_state["pages"]["page-03"] = page3

        next_page = get_next_pending_page(initial_state)
        assert next_page == "page-02"

    def test_get_next_pending_no_pages(self, initial_state):
        """No pending pages returns None."""
        assert get_next_pending_page(initial_state) is None

    def test_get_completed_pages(self, initial_state):
        """Get list of completed pages."""
        page1 = PageState(page_id="page-01", status=PageStatus.COMPLETED)
        page2 = PageState(page_id="page-02", status=PageStatus.PENDING)
        page3 = PageState(page_id="page-03", status=PageStatus.COMPLETED)

        initial_state["pages"]["page-01"] = page1
        initial_state["pages"]["page-02"] = page2
        initial_state["pages"]["page-03"] = page3

        completed = get_completed_pages(initial_state)
        assert set(completed) == {"page-01", "page-03"}

    def test_all_pages_completed(self, initial_state):
        """Check if all pages are completed."""
        assert all_pages_completed(initial_state) is False  # Empty

        page1 = PageState(page_id="page-01", status=PageStatus.COMPLETED)
        initial_state["pages"]["page-01"] = page1
        assert all_pages_completed(initial_state) is True


class TestRetryCounters:
    """Tests for retry counter helpers."""

    def test_reset_retry_counters(self, initial_state):
        """Reset all counters."""
        initial_state["content_retry_count"] = 3
        initial_state["layout_retry_count"] = 2
        initial_state["critic_iteration"] = 1
        initial_state["json_retry_count"] = 5

        reset_retry_counters(initial_state)

        assert initial_state["content_retry_count"] == 0
        assert initial_state["layout_retry_count"] == 0
        assert initial_state["critic_iteration"] == 0
        assert initial_state["json_retry_count"] == 0

    def test_increment_critic_iteration(self, initial_state):
        """Increment critic iteration."""
        page = PageState(page_id="page-01")
        initial_state["pages"]["page-01"] = page
        initial_state["current_page_id"] = "page-01"

        increment_critic_iteration(initial_state)
        assert initial_state["critic_iteration"] == 1
        assert page.iteration == 1

        increment_critic_iteration(initial_state)
        assert initial_state["critic_iteration"] == 2
        assert page.iteration == 2
