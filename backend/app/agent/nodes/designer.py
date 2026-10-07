"""Designer node: choose and validate a measured template without an LLM call."""

from typing import Any, Dict, List

from ..state import AgentState


def designer_node(state: AgentState) -> AgentState:
    """
    Design layout for the current page.

    This node:
    - Takes page content and outline
    - Chooses layout geometry from measured templates
    - Validates layout against constraints
    - Updates page state
    """
    page_id = state.get("current_page_id")
    if not page_id:
        return state

    page = state["pages"].get(page_id)
    if not page:
        return state

    state["workflow"].current_node = "designer"
    page.status = "designing"

    spec = state["project"].spec
    style = spec.get("style", "简约专业")

    # Generate layout
    try:
        layout_data = _generate_layout_config(
            page_id=page_id,
            page_type=page.page_type.value,
            title=page.title,
            subtitle=page.subtitle,
            num_points=max(len(page.key_points), len(page.bullet_points)),
            content_summary=_get_content_summary(page),
            style=style,
        )

        # Retain the planner's semantic layout choice (e.g. a comparison).
        from ...tools.slide_scene import template_layout
        suggested = next((item.get("suggest_layout", "") for item in state.get("outline", [])
                          if item.get("page_id") == page_id), "")
        layout_data["layouts"] = [template_layout(page.page_type.value,
            max(len(page.key_points), len(page.bullet_points)), bool(page.subtitle), suggested)]
        layout_data["layout_type"] = layout_data["layouts"][0]["layout_type"]
        _validate_layout_data(layout_data, page)

        # Update page state
        page.layout_type = layout_data.get("layout_type", page.layout_type)
        page.layout_json = layout_data.get("layouts", [{}])[0] if layout_data.get("layouts") else None
        page.master_json = layout_data.get("master")

        state["pages"][page_id] = page

    except Exception as e:
        page.status = "failed"
        page.error = f"布局生成失败: {str(e)}"
        state["errors"].append({
            "error_id": f"err-{len(state['errors']) + 1}",
            "node": "designer",
            "message": str(e),
            "severity": "medium"
        })

    return state


def _generate_layout_config(
    page_id: str,
    page_type: str,
    title: str,
    subtitle: str,
    num_points: int,
    content_summary: str,
    style: str,
) -> Dict[str, Any]:
    """Build a local theme and layout configuration."""
    from ...tools.slide_scene import get_theme, template_layout, rgb
    theme = get_theme(style)
    # Stable templates replace a full LLM master/geometry response per page.
    layout = template_layout(page_type, num_points, bool(subtitle))
    master = {
        "background": {"type": "solid", "rgb": list(rgb(theme["background"]))},
        "color_scheme": {name: list(rgb(theme.get(name, theme["primary"])))
                         for name in ("primary", "secondary", "accent", "text")},
        "font_scheme": {"title_font": "Microsoft YaHei", "body_font": "Microsoft YaHei",
                        "title_size": 30, "body_size": 18},
    }
    master["color_scheme"]["light_text"] = [255, 255, 255]
    return {"theme_name": style, "master": master, "layouts": [layout],
            "layout_type": layout["layout_type"]}


def _get_content_summary(page) -> str:
    """Get content summary for prompt."""
    summary_parts = []

    if page.key_points:
        summary_parts.append("要点: " + ", ".join(page.key_points[:3]))

    if page.bullet_points:
        bullet_text = ". ".join(page.bullet_points[:2])
        if bullet_text:
            summary_parts.append("说明: " + bullet_text[:100])

    return "\n".join(summary_parts) or "（无详细内容）"


def _validate_layout_data(layout_data: Dict[str, Any], page) -> None:
    """Validate generated layout data."""
    if not isinstance(layout_data, dict):
        raise ValueError("布局配置必须是JSON对象")

    if "master" not in layout_data:
        raise ValueError("布局配置缺少 master")

    if "layouts" not in layout_data or not layout_data["layouts"]:
        raise ValueError("布局配置缺少 layouts")

    # Validate master
    master = layout_data["master"]
    color_scheme = master.get("color_scheme", {})

    for color_name in ["primary", "secondary", "accent", "text", "light_text"]:
        color_value = color_scheme.get(color_name)
        if not isinstance(color_value, list) or len(color_value) != 3:
            raise ValueError(f"颜色配置 {color_name} 必须是RGB数组")
        for v in color_value:
            if not isinstance(v, int) or v < 0 or v > 255:
                raise ValueError(f"颜色 {color_name} 的RGB值必须在0-255之间")

    # Validate layouts
    for layout in layout_data["layouts"]:
        placeholders = layout.get("placeholders", [])

        # Must have title
        if not any(p.get("type") == "title" for p in placeholders):
            raise ValueError("每个布局必须包含标题占位符")

        # Validate coordinates
        for p in placeholders:
            x, y = p.get("x", 0), p.get("y", 0)
            w, h = p.get("w", 0), p.get("h", 0)

            if x < 0 or y < 0 or w <= 0 or h <= 0:
                raise ValueError(f"占位符 {p.get('name')} 坐标/尺寸无效")

            if x + w > 13.333 or y + h > 7.5:
                raise ValueError(f"占位符 {p.get('name')} 超出画布边界")

        # Detect text-on-text overlap. Two text placeholders that share more
        # than 25% of their bounding box will visually collide, so we
        # reject them here so the designer is forced to fix it.
        text_boxes = [
            (
                p.get("name"),
                float(p.get("x", 0)),
                float(p.get("y", 0)),
                float(p.get("w", 0)),
                float(p.get("h", 0)),
            )
            for p in placeholders
            if p.get("type") == "text"
        ]
        for i in range(len(text_boxes)):
            for j in range(i + 1, len(text_boxes)):
                n1, x1, y1, w1, h1 = text_boxes[i]
                n2, x2, y2, w2, h2 = text_boxes[j]
                ix = max(0.0, min(x1 + w1, x2 + w2) - max(x1, x2))
                iy = max(0.0, min(y1 + h1, y2 + h2) - max(y1, y2))
                overlap = ix * iy
                if overlap <= 0:
                    continue
                smaller_area = min(w1 * h1, w2 * h2) or 1.0
                if overlap / smaller_area > 0.25:
                    raise ValueError(
                        f"文本占位符 {n1} 与 {n2} 视觉重叠面积过大，需要调整坐标或换布局"
                    )


def generate_layout(
    page_id: str,
    page_type: str,
    title: str,
    subtitle: str,
    key_points: List[str],
    bullet_points: List[str],
    style: str = "简约专业",
) -> Dict[str, Any]:
    """
    Standalone function to generate layout.

    Args:
        page_id: Page identifier
        page_type: Type of page
        title: Page title
        subtitle: Subtitle
        key_points: Key points
        bullet_points: Bullet points
        style: Overall style

    Returns:
        Generated layout configuration
    """
    page = type('obj', (object,), {
        'key_points': key_points,
        'bullet_points': bullet_points,
        'title': title,
        'subtitle': subtitle,
        'page_type': type('obj', (object,), {'value': page_type})()
    })()

    layout_data = _generate_layout_config(
        page_id=page_id,
        page_type=page_type,
        title=title,
        subtitle=subtitle,
        num_points=max(len(key_points), len(bullet_points)),
        content_summary=_get_content_summary(page),
        style=style,
    )

    _validate_layout_data(layout_data, page)

    return layout_data
