"""Tests for contracts/schemas.py."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.contracts.schemas import (
    PageContent,
    LayoutSpec,
    PlaceholderSpec,
    ReviewResult,
    ReviewIssue,
    ReviewDimensions,
    RevisionPlan,
    RevisionOperation,
    ProjectSpec,
    OutlineItem,
    PageState,
    MasterLayout,
    IterationRecord,
    ReviewStatus,
    IssueSeverity,
    IssueCategory,
    IssueOwner,
    PageStatus,
    PageType,
    LayoutType,
    RevisionOperationType,
)


class TestPageContent:
    """Tests for PageContent schema."""

    def test_create_minimal(self):
        """Create PageContent with minimal fields."""
        content = PageContent(title="Test")
        assert content.title == "Test"
        assert content.subtitle == ""
        assert content.key_points == []
        assert content.bullet_points == []
        assert content.speaker_notes == ""

    def test_create_full(self):
        """Create PageContent with all fields."""
        content = PageContent(
            title="Title",
            subtitle="Subtitle",
            key_points=["kp1", "kp2"],
            bullet_points=["bp1", "bp2"],
            speaker_notes="Notes",
        )
        assert content.title == "Title"
        assert len(content.key_points) == 2

    def test_strip_whitespace_in_lists(self):
        """Whitespace is stripped from list items."""
        content = PageContent(
            title="t",
            key_points=["  kp1  ", "kp2"],
            bullet_points=["bp1"],
        )
        assert content.key_points == ["kp1", "kp2"]


class TestPlaceholderSpec:
    """Tests for PlaceholderSpec schema."""

    def test_create_valid(self):
        """Create valid placeholder."""
        p = PlaceholderSpec(
            name="title",
            type="title",
            x=1.0,
            y=1.0,
            w=10.0,
            h=2.0,
        )
        assert p.name == "title"

    def test_invalid_dimensions(self):
        """Invalid dimensions raise error."""
        with pytest.raises(PydanticValidationError):
            PlaceholderSpec(
                name="title",
                type="title",
                x=-1.0,  # Negative
                y=1.0,
                w=10.0,
                h=2.0,
            )

    def test_zero_width_invalid(self):
        """Zero width is invalid."""
        with pytest.raises(PydanticValidationError):
            PlaceholderSpec(
                name="title",
                type="title",
                x=0.0,
                y=0.0,
                w=0.0,  # Must be > 0
                h=1.0,
            )


class TestLayoutSpec:
    """Tests for LayoutSpec schema."""

    def test_create_with_placeholders(self):
        """Create LayoutSpec with placeholders."""
        layout = LayoutSpec(
            layout_id="content",
            layout_type=LayoutType.TITLE_CONTENT,
            placeholders=[
                PlaceholderSpec(name="title", type="title", x=1, y=1, w=10, h=1),
                PlaceholderSpec(name="content", type="text", x=1, y=3, w=10, h=4),
            ],
        )
        assert layout.layout_id == "content"
        assert len(layout.placeholders) == 2

    def test_get_placeholder(self):
        """Get placeholder by name."""
        layout = LayoutSpec(
            layout_id="content",
            layout_type=LayoutType.TITLE_CONTENT,
            placeholders=[
                PlaceholderSpec(name="title", type="title", x=1, y=1, w=10, h=1),
            ],
        )
        assert layout.get_placeholder("title") is not None
        assert layout.get_placeholder("missing") is None


class TestColorScheme:
    """Tests for ColorScheme schema."""

    def test_create_color_scheme(self):
        """Create color scheme with valid values."""
        from app.contracts.schemas import ColorScheme

        cs = ColorScheme(
            primary=[20, 40, 80],
            secondary=[80, 100, 140],
            accent=[60, 120, 180],
            text=[30, 30, 30],
            light_text=[255, 255, 255],
        )
        assert cs.primary == [20, 40, 80]

    def test_invalid_color_value(self):
        """Invalid color value raises error."""
        from app.contracts.schemas import RGBColor

        with pytest.raises(PydanticValidationError):
            RGBColor(rgb=[300, 40, 80])  # Out of range

    def test_wrong_rgb_length(self):
        """RGB must have 3 values."""
        from app.contracts.schemas import RGBColor

        with pytest.raises(PydanticValidationError):
            RGBColor(rgb=[20, 40])  # Only 2 values


class TestReviewResult:
    """Tests for ReviewResult schema."""

    def test_create_approved(self):
        """Create approved review result."""
        result = ReviewResult(
            status=ReviewStatus.APPROVED,
            score=88,
            dimensions=ReviewDimensions(
                alignment=9, balance=8, readability=9,
                hierarchy=8, density=9, consistency=9
            ),
            issues=[],
        )
        assert result.status == ReviewStatus.APPROVED
        assert result.score == 88

    def test_score_range(self):
        """Score must be 0-100."""
        with pytest.raises(PydanticValidationError):
            ReviewResult(status=ReviewStatus.APPROVED, score=150)

        with pytest.raises(PydanticValidationError):
            ReviewResult(status=ReviewStatus.APPROVED, score=-10)

    def test_has_high_severity_issues(self):
        """Detect high severity issues."""
        result = ReviewResult(
            status=ReviewStatus.NEEDS_REVISION,
            score=60,
            issues=[
                ReviewIssue(
                    issue_id="i1",
                    category=IssueCategory.OVERFLOW,
                    severity=IssueSeverity.HIGH,
                    description="overflow",
                )
            ],
        )
        assert result.has_high_severity_issues() is True

    def test_has_overflow_or_overlap(self):
        """Detect overflow/overlap issues."""
        result = ReviewResult(
            status=ReviewStatus.NEEDS_REVISION,
            score=70,
            issues=[
                ReviewIssue(
                    issue_id="i1",
                    category=IssueCategory.OVERFLOW,
                    severity=IssueSeverity.MEDIUM,
                    description="overflow",
                )
            ],
        )
        assert result.has_overflow_or_overlap() is True

    def test_get_layout_issues(self):
        """Separate layout vs content issues."""
        result = ReviewResult(
            status=ReviewStatus.NEEDS_REVISION,
            score=70,
            issues=[
                ReviewIssue(
                    issue_id="i1",
                    category=IssueCategory.ALIGNMENT,
                    severity=IssueSeverity.MEDIUM,
                    owner=IssueOwner.LAYOUT,
                    description="alignment",
                ),
                ReviewIssue(
                    issue_id="i2",
                    category=IssueCategory.CONTENT,
                    severity=IssueSeverity.MEDIUM,
                    owner=IssueOwner.CONTENT,
                    description="content",
                ),
            ],
        )
        layout_issues = result.get_layout_issues()
        content_issues = result.get_content_issues()
        assert len(layout_issues) == 1
        assert len(content_issues) == 1


class TestRevisionPlan:
    """Tests for RevisionPlan schema."""

    def test_create_with_operations(self):
        """Create revision plan with operations."""
        plan = RevisionPlan(
            operations=[
                RevisionOperation(
                    op=RevisionOperationType.RESIZE,
                    target="content",
                    changes={"w": 10, "h": 5},
                ),
            ],
            reason="Test",
        )
        assert len(plan.operations) == 1
        assert plan.operations[0].op == RevisionOperationType.RESIZE

    def test_empty_operations(self):
        """Empty operations allowed (will be flagged by validator)."""
        plan = RevisionPlan(operations=[])
        assert plan.operations == []


class TestPageState:
    """Tests for PageState schema."""

    def test_create_minimal(self):
        """Create page state with minimal fields."""
        # Note: contracts.PageState requires page_type
        page = PageState(page_id="page-01", page_type=PageType.CONTENT)
        assert page.page_id == "page-01"
        assert page.page_type == PageType.CONTENT
        assert page.status == PageStatus.PENDING
        assert page.iteration == 1

    def test_create_with_content(self):
        """Create page with content."""
        page = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            content=PageContent(
                title="Test",
                key_points=["a", "b"],
                bullet_points=["c", "d"],
            ),
        )
        assert page.page_id == "page-01"
        assert page.content.title == "Test"
        assert len(page.content.key_points) == 2


class TestIterationRecord:
    """Tests for IterationRecord schema."""

    def test_create_basic(self):
        """Create iteration record."""
        record = IterationRecord(iteration=1, page_id="page-01")
        assert record.iteration == 1
        assert record.page_id == "page-01"

    def test_duration(self):
        """Calculate duration when finished."""
        from datetime import datetime, timedelta

        start = datetime.now()
        end = start + timedelta(seconds=10)

        record = IterationRecord(
            iteration=1,
            page_id="page-01",
            started_at=start,
            finished_at=end,
        )
        assert record.duration_seconds() == 10.0

    def test_duration_when_not_finished(self):
        """Duration is None when not finished."""
        record = IterationRecord(iteration=1, page_id="page-01")
        assert record.duration_seconds() is None


class TestOutlineItem:
    """Tests for OutlineItem schema."""

    def test_create(self):
        """Create outline item."""
        item = OutlineItem(
            page_id="page-01",
            page_type=PageType.CONTENT,
            page_title="Test",
            key_points=["a", "b"],
        )
        assert item.page_title == "Test"
        assert len(item.key_points) == 2
