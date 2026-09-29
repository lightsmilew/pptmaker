"""Validators for contract schemas."""

from typing import Any, Dict, List, Optional, Tuple

from .schemas import (
    PageContent,
    LayoutSpec,
    ReviewResult,
    RevisionPlan,
    ReviewStatus,
    IssueSeverity,
    PlaceholderSpec,
    MasterLayout,
)
from .errors import (
    SchemaValidationError,
    SemanticValidationError,
)


# Canvas dimensions (standard PPT 16:9)
CANVAS_WIDTH = 13.333  # inches
CANVAS_HEIGHT = 7.5   # inches


def validate_page_content(content: PageContent) -> List[str]:
    """
    Validate page content.

    Args:
        content: PageContent to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Title validation
    if not content.title or len(content.title.strip()) < 2:
        errors.append("标题缺失或过短")

    # Content length check
    total_length = sum(len(p) for p in content.key_points + content.bullet_points)
    if total_length > 500:
        errors.append("内容过长，建议精简要点")

    # Key points count
    if len(content.key_points) == 0:
        errors.append("缺少核心要点")
    elif len(content.key_points) > 6:
        errors.append("要点过多，建议控制在3-5个")

    # Bullet points should not be empty if key_points exist
    if content.key_points and not content.bullet_points:
        errors.append("缺少详细要点说明")

    return errors


def validate_layout_spec(layout: LayoutSpec, canvas_width: float = CANVAS_WIDTH,
                         canvas_height: float = CANVAS_HEIGHT) -> List[str]:
    """
    Validate layout specification.

    Args:
        layout: LayoutSpec to validate
        canvas_width: Canvas width in inches
        canvas_height: Canvas height in inches

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    placeholder_names = set()

    # Must have at least a title placeholder
    has_title = any(p.type == "title" for p in layout.placeholders)
    if not has_title:
        errors.append("布局必须包含标题占位符")

    # Validate each placeholder
    for p in layout.placeholders:
        # Check name uniqueness
        if p.name in placeholder_names:
            errors.append(f"占位符名称重复: {p.name}")
        placeholder_names.add(p.name)

        # Check bounds
        if p.x < 0 or p.y < 0:
            errors.append(f"占位符 {p.name} 坐标不能为负")
        if p.w <= 0 or p.h <= 0:
            errors.append(f"占位符 {p.name} 宽高必须为正")

        # Check if extends beyond canvas
        if p.x + p.w > canvas_width:
            errors.append(f"占位符 {p.name} 超出画布右边界")
        if p.y + p.h > canvas_height:
            errors.append(f"占位符 {p.name} 超出画布下边界")

    # Valid placeholder types
    valid_types = {"title", "subtitle", "text", "chart", "table", "accent", "caption", "toc"}
    for p in layout.placeholders:
        if p.type not in valid_types:
            errors.append(f"非法占位符类型: {p.type}")

    return errors


def validate_master_layout(master: MasterLayout) -> List[str]:
    """
    Validate master layout configuration.

    Args:
        master: MasterLayout to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Validate color scheme
    color_scheme = master.color_scheme
    for name, value in color_scheme.model_dump().items():
        if not isinstance(value, list) or len(value) != 3:
            errors.append(f"颜色配置 {name} 必须是RGB数组")
            continue
        for v in value:
            if not isinstance(v, int) or v < 0 or v > 255:
                errors.append(f"颜色 {name} 的RGB值必须在0-255之间")

    # Validate font scheme
    font_scheme = master.font_scheme
    if not font_scheme.title_font or not font_scheme.title_font.strip():
        errors.append("标题字体未设置")
    if not font_scheme.body_font or not font_scheme.body_font.strip():
        errors.append("正文字体未设置")
    if font_scheme.title_size < 8 or font_scheme.title_size > 72:
        errors.append("标题字号应在8-72之间")
    if font_scheme.body_size < 8 or font_scheme.body_size > 48:
        errors.append("正文字号应在8-48之间")

    return errors


def validate_review_result(review: ReviewResult) -> List[str]:
    """
    Validate review result.

    Args:
        review: ReviewResult to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check score range
    if review.score < 0 or review.score > 100:
        errors.append(f"评分必须在0-100之间，当前: {review.score}")

    # Validate dimensions
    dimensions = review.dimensions
    for field in ["alignment", "balance", "readability", "hierarchy", "density", "consistency"]:
        value = getattr(dimensions, field, None)
        if value is not None and (value < 0 or value > 10):
            errors.append(f"维度 {field} 必须在0-10之间")

    # Validate issue IDs are unique
    issue_ids = [issue.issue_id for issue in review.issues]
    if len(issue_ids) != len(set(issue_ids)):
        errors.append("问题ID必须唯一")

    return errors


def validate_revision_plan(plan: RevisionPlan) -> List[str]:
    """
    Validate revision plan.

    Args:
        plan: RevisionPlan to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not plan.operations:
        errors.append("修订计划不能为空")

    valid_ops = {
        "move", "resize", "change_font_size", "change_font",
        "change_color", "change_layout", "split_content",
        "merge_content", "reduce_spacing", "increase_spacing",
        "hide_optional_element"
    }

    for op in plan.operations:
        if op.op.value not in valid_ops:
            errors.append(f"非法操作类型: {op.op.value}")
        if not op.target:
            errors.append("操作目标不能为空")
        if not op.changes:
            errors.append(f"操作 {op.op.value} 必须包含变更内容")

    return errors


def semantic_validate_layout_content(
    layout: LayoutSpec,
    content: PageContent
) -> List[str]:
    """
    Semantic validation: check if layout matches content requirements.

    Args:
        layout: LayoutSpec to validate
        content: PageContent to validate against

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Content pages must have content placeholders
    if content.key_points or content.bullet_points:
        has_content = any(
            p.type in ("text", "content", "content_1", "content_2", "toc")
            for p in layout.placeholders
        )
        if not has_content:
            errors.append("内容页缺少文本内容占位符")

    # Chart pages should have chart placeholder only if there's real chart data
    if content.chart_data:
        has_chart = any(p.type == "chart" for p in layout.placeholders)
        if not has_chart:
            errors.append("图表数据页缺少图表占位符")

    # Table pages should have table placeholder
    if content.table_data:
        has_table = any(p.type == "table" for p in layout.placeholders)
        if not has_table:
            errors.append("表格数据页缺少表格占位符")

    return errors


def semantic_validate_canvas_bounds(
    placeholders: List[PlaceholderSpec],
    canvas_width: float = CANVAS_WIDTH,
    canvas_height: float = CANVAS_HEIGHT,
    safe_margin: float = 0.2
) -> List[str]:
    """
    Validate that placeholders fit within safe canvas bounds.

    Args:
        placeholders: List of placeholders to validate
        canvas_width: Canvas width in inches
        canvas_height: Canvas height in inches
        safe_margin: Minimum margin from edges in inches

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    for p in placeholders:
        name = p.name

        # Check minimum margin
        if p.x < safe_margin:
            errors.append(f"占位符 {name} 距离左边缘太近")
        if p.y < safe_margin:
            errors.append(f"占位符 {name} 距离上边缘太近")
        if p.x + p.w > canvas_width - safe_margin:
            errors.append(f"占位符 {name} 距离右边缘太近")
        if p.y + p.h > canvas_height - safe_margin:
            errors.append(f"占位符 {name} 距离下边缘太近")

        # Check for zero-area placeholders (except hidden elements)
        if p.w < 0.1 or p.h < 0.1:
            errors.append(f"占位符 {name} 面积太小")

    return errors


def should_pass_review(review: ReviewResult) -> Tuple[bool, str]:
    """
    Determine if a review should pass based on its result.

    Args:
        review: ReviewResult to evaluate

    Returns:
        Tuple of (should_pass, reason)
    """
    # Critical status always fails
    if review.status == ReviewStatus.FAILED:
        return False, "渲染失败"

    if review.status == ReviewStatus.BLOCKED:
        return False, "评审被阻塞"

    # High severity issues always fail
    if review.has_high_severity_issues():
        return False, "存在高严重性问题"

    # Overflow or overlap always fails
    if review.has_overflow_or_overlap():
        return False, "存在内容溢出或元素重叠"

    # Score threshold
    if review.score < 85:
        return False, f"评分({review.score:.0f})低于阈值(85)"

    # Passed all checks
    return True, "评审通过"


def get_revision_priority(issues: List) -> str:
    """
    Determine what type of revision is needed based on issues.

    Args:
        issues: List of ReviewIssue objects

    Returns:
        "layout", "content", or "both"
    """
    layout_issues = 0
    content_issues = 0

    for issue in issues:
        if hasattr(issue, "owner"):
            if issue.owner.value == "layout":
                layout_issues += 1
            elif issue.owner.value == "content":
                content_issues += 1

    if layout_issues > 0 and content_issues > 0:
        return "both"
    elif layout_issues > content_issues:
        return "layout"
    elif content_issues > 0:
        return "content"
    else:
        return "layout"  # Default to layout if unclear
