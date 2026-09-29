"""Tests for contracts/validators.py."""

import pytest

from app.contracts.schemas import (
    PageContent,
    LayoutSpec,
    PlaceholderSpec,
    ReviewResult,
    ReviewIssue,
    ReviewDimensions,
    RevisionPlan,
    RevisionOperation,
    MasterLayout,
    ReviewStatus,
    IssueSeverity,
    IssueCategory,
    IssueOwner,
    RevisionOperationType,
    LayoutType,
)
from app.contracts.validators import (
    validate_page_content,
    validate_layout_spec,
    validate_master_layout,
    validate_review_result,
    validate_revision_plan,
    semantic_validate_layout_content,
    should_pass_review,
    get_revision_priority,
)


class TestValidatePageContent:
    """Tests for validate_page_content."""

    def test_valid_content(self):
        """Valid page content returns no errors."""
        content = PageContent(
            title="Valid Title",
            key_points=["kp1", "kp2", "kp3"],
            bullet_points=["bp1", "bp2"],
        )
        errors = validate_page_content(content)
        assert errors == []

    def test_short_title(self):
        """Short title is an error."""
        content = PageContent(title="a", bullet_points=["bp1"])
        errors = validate_page_content(content)
        assert any("标题" in e for e in errors)

    def test_too_many_key_points(self):
        """Too many key points is an error."""
        content = PageContent(
            title="Test",
            key_points=["a"] * 7,
            bullet_points=["bp1"],
        )
        errors = validate_page_content(content)
        assert any("要点过多" in e for e in errors)

    def test_content_too_long(self):
        """Very long content is an error."""
        long_text = "x" * 600
        content = PageContent(
            title="Test",
            key_points=[long_text],
            bullet_points=["bp"],
        )
        errors = validate_page_content(content)
        assert any("过长" in e for e in errors)


class TestValidateLayoutSpec:
    """Tests for validate_layout_spec."""

    def test_valid_layout(self):
        """Valid layout returns no errors."""
        layout = LayoutSpec(
            layout_id="content",
            layout_type=LayoutType.TITLE_CONTENT,
            placeholders=[
                PlaceholderSpec(name="title", type="title", x=1, y=1, w=10, h=1),
                PlaceholderSpec(name="content", type="text", x=1, y=3, w=10, h=4),
            ],
        )
        errors = validate_layout_spec(layout)
        assert errors == []

    def test_missing_title_placeholder(self):
        """Layout without title is invalid."""
        layout = LayoutSpec(
            layout_id="content",
            layout_type=LayoutType.TITLE_CONTENT,
            placeholders=[
                PlaceholderSpec(name="content", type="text", x=1, y=1, w=10, h=4),
            ],
        )
        errors = validate_layout_spec(layout)
        assert any("标题" in e for e in errors)

    def test_duplicate_placeholder_names(self):
        """Duplicate placeholder names are invalid."""
        layout = LayoutSpec(
            layout_id="content",
            layout_type=LayoutType.TITLE_CONTENT,
            placeholders=[
                PlaceholderSpec(name="title", type="title", x=1, y=1, w=5, h=1),
                PlaceholderSpec(name="title", type="text", x=1, y=3, w=5, h=4),
            ],
        )
        errors = validate_layout_spec(layout)
        assert any("重复" in e for e in errors)

    def test_placeholder_out_of_canvas(self):
        """Placeholder extending beyond canvas is invalid."""
        layout = LayoutSpec(
            layout_id="content",
            layout_type=LayoutType.TITLE_CONTENT,
            placeholders=[
                PlaceholderSpec(name="title", type="title", x=10, y=1, w=10, h=1),  # 10+10>13.333
            ],
        )
        errors = validate_layout_spec(layout, canvas_width=13.333, canvas_height=7.5)
        assert any("超出" in e for e in errors)


class TestValidateMasterLayout:
    """Tests for validate_master_layout."""

    def test_valid_master(self):
        """Valid master layout."""
        master = MasterLayout()
        errors = validate_master_layout(master)
        assert errors == []

    def test_invalid_color_value(self):
        """Invalid color value in master."""
        from app.contracts.schemas import ColorScheme

        master = MasterLayout(
            color_scheme=ColorScheme(
                primary=[300, 0, 0],  # Out of range
                secondary=[80, 100, 140],
                accent=[60, 120, 180],
                text=[30, 30, 30],
                light_text=[255, 255, 255],
            )
        )
        errors = validate_master_layout(master)
        assert any("颜色" in e for e in errors)

    def test_invalid_font_size(self):
        """Invalid font size."""
        from app.contracts.schemas import FontScheme

        master = MasterLayout(
            font_scheme=FontScheme(
                title_font="Arial",
                body_font="Arial",
                title_size=100,  # Out of range
                body_size=16,
            )
        )
        errors = validate_master_layout(master)
        assert any("字号" in e for e in errors)


class TestValidateReviewResult:
    """Tests for validate_review_result."""

    def test_valid_review(self):
        """Valid review result."""
        result = ReviewResult(
            status=ReviewStatus.APPROVED,
            score=88,
        )
        errors = validate_review_result(result)
        assert errors == []

    def test_invalid_score(self):
        """Score out of range."""
        with pytest.raises(Exception):
            ReviewResult(
                status=ReviewStatus.APPROVED,
                score=150,
            )

    def test_duplicate_issue_ids(self):
        """Duplicate issue IDs are invalid."""
        result = ReviewResult(
            status=ReviewStatus.NEEDS_REVISION,
            score=70,
            issues=[
                ReviewIssue(
                    issue_id="i1",
                    category=IssueCategory.ALIGNMENT,
                    severity=IssueSeverity.LOW,
                    description="issue 1",
                ),
                ReviewIssue(
                    issue_id="i1",  # Duplicate
                    category=IssueCategory.ALIGNMENT,
                    severity=IssueSeverity.LOW,
                    description="issue 2",
                ),
            ],
        )
        errors = validate_review_result(result)
        assert any("唯一" in e for e in errors)


class TestValidateRevisionPlan:
    """Tests for validate_revision_plan."""

    def test_valid_plan(self):
        """Valid revision plan."""
        plan = RevisionPlan(
            operations=[
                RevisionOperation(
                    op=RevisionOperationType.RESIZE,
                    target="content",
                    changes={"w": 10},
                ),
            ],
        )
        errors = validate_revision_plan(plan)
        assert errors == []

    def test_empty_operations(self):
        """Empty operations are invalid."""
        plan = RevisionPlan(operations=[])
        errors = validate_revision_plan(plan)
        assert any("不能为空" in e for e in errors)

    def test_invalid_op_type(self):
        """Invalid op type is rejected."""
        with pytest.raises(Exception):
            RevisionOperation(
                op="invalid_op",
                target="content",
                changes={},
            )


class TestSemanticValidateLayoutContent:
    """Tests for semantic_validate_layout_content."""

    def test_content_needs_text_placeholder(self):
        """Content page must have text placeholder."""
        layout = LayoutSpec(
            layout_id="content",
            layout_type=LayoutType.TITLE_CONTENT,
            placeholders=[
                PlaceholderSpec(name="title", type="title", x=1, y=1, w=10, h=1),
            ],
        )
        content = PageContent(
            title="Test",
            key_points=["kp1"],
            bullet_points=["bp1"],
        )
        errors = semantic_validate_layout_content(layout, content)
        assert any("文本内容占位符" in e for e in errors)

    def test_chart_layout_needs_chart_placeholder(self):
        """Chart data needs chart placeholder."""
        layout = LayoutSpec(
            layout_id="chart",
            layout_type=LayoutType.CHART_CONTENT,
            placeholders=[
                PlaceholderSpec(name="title", type="title", x=1, y=1, w=10, h=1),
                PlaceholderSpec(name="content", type="text", x=1, y=3, w=10, h=4),
            ],
        )
        content = PageContent(
            title="Test",
            chart_data={"type": "bar"},
        )
        errors = semantic_validate_layout_content(layout, content)
        assert any("图表占位符" in e for e in errors)


class TestShouldPassReview:
    """Tests for should_pass_review function."""

    def test_approved_passes(self):
        """Approved status passes."""
        result = ReviewResult(status=ReviewStatus.APPROVED, score=88)
        passed, _ = should_pass_review(result)
        assert passed is True

    def test_failed_never_passes(self):
        """Failed status never passes."""
        result = ReviewResult(status=ReviewStatus.FAILED, score=100)
        passed, _ = should_pass_review(result)
        assert passed is False

    def test_high_severity_fails(self):
        """High severity issue fails."""
        result = ReviewResult(
            status=ReviewStatus.NEEDS_REVISION,
            score=90,
            issues=[
                ReviewIssue(
                    issue_id="i1",
                    category=IssueCategory.OVERFLOW,
                    severity=IssueSeverity.HIGH,
                    description="overflow",
                )
            ],
        )
        passed, _ = should_pass_review(result)
        assert passed is False

    def test_low_score_fails(self):
        """Score below threshold fails."""
        result = ReviewResult(status=ReviewStatus.NEEDS_REVISION, score=70)
        passed, _ = should_pass_review(result)
        assert passed is False

    def test_overflow_fails_even_with_high_score(self):
        """Overflow fails even with high score."""
        result = ReviewResult(
            status=ReviewStatus.NEEDS_REVISION,
            score=92,
            issues=[
                ReviewIssue(
                    issue_id="i1",
                    category=IssueCategory.OVERFLOW,
                    severity=IssueSeverity.LOW,
                    description="minor overflow",
                )
            ],
        )
        passed, _ = should_pass_review(result)
        assert passed is False


class TestGetRevisionPriority:
    """Tests for get_revision_priority function."""

    def test_only_layout_issues(self):
        """Only layout issues returns 'layout'."""
        issues = [
            ReviewIssue(
                issue_id="i1",
                category=IssueCategory.ALIGNMENT,
                severity=IssueSeverity.MEDIUM,
                owner=IssueOwner.LAYOUT,
                description="alignment",
            )
        ]
        priority = get_revision_priority(issues)
        assert priority == "layout"

    def test_only_content_issues(self):
        """Only content issues returns 'content'."""
        issues = [
            ReviewIssue(
                issue_id="i1",
                category=IssueCategory.CONTENT,
                severity=IssueSeverity.MEDIUM,
                owner=IssueOwner.CONTENT,
                description="content",
            )
        ]
        priority = get_revision_priority(issues)
        assert priority == "content"

    def test_both_issues(self):
        """Both types returns 'both'."""
        issues = [
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
        ]
        priority = get_revision_priority(issues)
        assert priority == "both"
