"""Tests for models/project.py."""

import pytest
from datetime import datetime

from app.models.project import (
    ProjectState,
    ProjectStatus,
    WorkflowState,
    WorkflowStatus,
)


class TestProjectState:
    """Tests for ProjectState."""

    def test_create_minimal(self):
        """Create with minimal fields."""
        project = ProjectState(project_id="test-001")
        assert project.project_id == "test-001"
        assert project.status == ProjectStatus.IDLE
        assert project.page_count == 8

    def test_create_with_spec(self):
        """Create with spec data."""
        spec = {"topic": "Test", "page_count": 5}
        project = ProjectState(
            project_id="test-001",
            spec=spec,
            page_count=5,
        )
        assert project.spec == spec
        assert project.page_count == 5

    def test_timestamps_auto_set(self):
        """Timestamps are set automatically."""
        project = ProjectState(project_id="test-001")
        assert isinstance(project.created_at, datetime)
        assert isinstance(project.updated_at, datetime)


class TestWorkflowState:
    """Tests for WorkflowState."""

    def test_create_minimal(self):
        """Create with minimal fields."""
        wf = WorkflowState(workflow_id="wf-001", total_pages=8)
        assert wf.workflow_id == "wf-001"
        assert wf.total_pages == 8
        assert wf.status == WorkflowStatus.IDLE
        assert wf.completed_pages == []
        assert wf.failed_pages == []

    def test_progress_percentage(self):
        """Calculate progress percentage."""
        wf = WorkflowState(workflow_id="wf-001", total_pages=10)
        assert wf.progress_percentage() == 0.0

        wf.add_completed_page("p1")
        assert wf.progress_percentage() == 10.0

        wf.add_completed_page("p2")
        assert wf.progress_percentage() == 20.0

    def test_progress_with_zero_total(self):
        """Progress is 0 when total is 0."""
        wf = WorkflowState(workflow_id="wf-001", total_pages=0)
        assert wf.progress_percentage() == 0.0

    def test_add_completed_page(self):
        """Add page to completed."""
        wf = WorkflowState(workflow_id="wf-001", total_pages=5)
        wf.add_completed_page("p1")
        assert "p1" in wf.completed_pages

        # Adding again should not duplicate
        wf.add_completed_page("p1")
        assert wf.completed_pages.count("p1") == 1

    def test_add_failed_page(self):
        """Add page to failed."""
        wf = WorkflowState(workflow_id="wf-001", total_pages=5)
        wf.add_failed_page("p1", "Test error")
        assert "p1" in wf.failed_pages
        assert len(wf.errors) == 1
        assert wf.errors[0]["page_id"] == "p1"
        assert wf.errors[0]["error"] == "Test error"
