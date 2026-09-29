"""Tests for models/page.py."""

import pytest
from datetime import datetime

from app.models.page import (
    PageState,
    PageStatus,
    PageType,
    PreviewInfo,
)


class TestPreviewInfo:
    """Tests for PreviewInfo."""

    def test_create(self):
        """Create preview info."""
        info = PreviewInfo(image_path="/path/to/img.png")
        assert info.image_path == "/path/to/img.png"
        assert info.width == 1600
        assert info.height == 900
        assert isinstance(info.rendered_at, datetime)


class TestPageState:
    """Tests for PageState."""

    def test_create_minimal(self):
        """Create page state with minimal fields."""
        page = PageState(page_id="page-01")
        assert page.page_id == "page-01"
        assert page.page_type == PageType.CONTENT
        assert page.status == PageStatus.PENDING
        assert page.iteration == 1
        assert page.max_iterations == 4

    def test_create_with_content(self):
        """Create page with content."""
        page = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            title="Test",
            key_points=["a", "b"],
            bullet_points=["c", "d"],
        )
        assert page.title == "Test"
        assert len(page.key_points) == 2

    def test_status_methods(self):
        """Test status check methods."""
        page = PageState(page_id="page-01", review_status="approved", status=PageStatus.COMPLETED)
        assert page.is_approved() is True
        assert page.is_completed() is True
        assert page.needs_revision() is False

        page.review_status = "needs_revision"
        assert page.needs_revision() is True

    def test_can_retry(self):
        """Test can_retry logic."""
        page = PageState(page_id="page-01", iteration=2, max_iterations=4)
        assert page.can_retry() is True

        page.iteration = 5
        assert page.can_retry() is False

        page.iteration = 2
        page.status = PageStatus.COMPLETED
        assert page.can_retry() is False

    def test_increment_iteration(self):
        """Increment iteration count."""
        page = PageState(page_id="page-01", iteration=1)
        page.increment_iteration()
        assert page.iteration == 2
        page.increment_iteration()
        assert page.iteration == 3

    def test_mark_completed(self):
        """Mark page as completed."""
        page = PageState(page_id="page-01", status=PageStatus.REVIEWING)
        page.mark_completed()
        assert page.status == PageStatus.COMPLETED
        assert page.review_status == "approved"

    def test_mark_failed(self):
        """Mark page as failed."""
        page = PageState(page_id="page-01", status=PageStatus.REVIEWING)
        page.mark_failed("Test error")
        assert page.status == PageStatus.FAILED
        assert page.error == "Test error"

    def test_to_dict(self):
        """Convert to dict format."""
        page = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            title="Test",
            key_points=["a"],
            bullet_points=["b"],
        )
        data = page.to_dict()

        assert data["page_id"] == "page-01"
        assert data["page_type"] == "content"
        assert data["content"]["title"] == "Test"
        assert "layout" in data
        assert "iteration" in data
        assert "status" in data
