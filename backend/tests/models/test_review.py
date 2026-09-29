"""Tests for models/review.py."""

import pytest
from datetime import datetime

from app.models.review import (
    AgentError,
    ErrorSeverity,
    ReviewStatus,
    IssueSeverity,
    IssueCategory,
    IssueOwner,
    ReviewIssue,
    ReviewDimensions,
    GlobalReviewResult,
    PageReviewInput,
    GlobalReviewInput,
)


class TestAgentError:
    """Tests for AgentError."""

    def test_create_minimal(self):
        """Create with minimal fields."""
        err = AgentError(
            error_id="err-001",
            node="writer",
            message="Test error",
        )
        assert err.error_id == "err-001"
        assert err.node == "writer"
        assert err.message == "Test error"
        assert err.severity == ErrorSeverity.MEDIUM
        assert err.resolved is False


class TestReviewIssue:
    """Tests for ReviewIssue."""

    def test_create(self):
        """Create review issue."""
        issue = ReviewIssue(
            issue_id="i1",
            category=IssueCategory.ALIGNMENT,
            severity=IssueSeverity.HIGH,
            target="content",
            description="test",
        )
        assert issue.owner == IssueOwner.LAYOUT  # Default


class TestReviewDimensions:
    """Tests for ReviewDimensions."""

    def test_default_values(self):
        """Default values are 5."""
        dims = ReviewDimensions()
        assert dims.alignment == 5
        assert dims.balance == 5

    def test_overall_score(self):
        """Calculate overall score."""
        dims = ReviewDimensions(
            alignment=8, balance=8, readability=8,
            hierarchy=8, density=8, consistency=8
        )
        # Average * 10 = 80
        assert dims.overall_score() == 80.0


class TestGlobalReviewResult:
    """Tests for GlobalReviewResult."""

    def test_create(self):
        """Create global review result."""
        result = GlobalReviewResult(
            status=ReviewStatus.APPROVED,
            score=88,
        )
        assert result.status == ReviewStatus.APPROVED
        assert result.score == 88
        assert result.has_critical_issues() is False

    def test_with_critical_issues(self):
        """With critical issues."""
        result = GlobalReviewResult(
            status=ReviewStatus.NEEDS_REVISION,
            score=60,
            consistency_issues=[
                ReviewIssue(
                    issue_id="c1",
                    category=IssueCategory.CONSISTENCY,
                    severity=IssueSeverity.CRITICAL,
                    description="critical issue",
                )
            ],
        )
        assert result.has_critical_issues() is True


class TestPageReviewInput:
    """Tests for PageReviewInput."""

    def test_create(self):
        """Create page review input."""
        inp = PageReviewInput(
            page_id="page-01",
            image_path="/path/to/img.png",
            page_data={"title": "test"},
        )
        assert inp.page_id == "page-01"
        assert inp.iteration == 1
        assert inp.canvas_info is not None
        assert inp.design_rules is not None
