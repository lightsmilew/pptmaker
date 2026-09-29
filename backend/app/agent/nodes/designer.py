"""Designer node - generates layout specification using unified contract."""

import json
from typing import Any, Dict, List, Optional

from ..state import AgentState
from ...llm import get_llm_client
from ...contracts.json_utils import extract_json_from_text
from ...contracts.validators import validate_layout_spec, semantic_validate_layout_content
from ...contracts.schemas import LayoutSpec, MasterLayout


DESIGNER_PROMPT = """你是专业的PPT视觉设计师。请根据页面内容设计一个现代、简约、可渲染的 PowerPoint 页面布局，并**只输出一个 JSON 对象**，不要任何解释文字或 Markdown 围栏。

## 规则（必须遵守）
1. 整段回复必须是一个合法 JSON 对象，第一字符是 `{{`，最后一字符是 `}}`。
2. 禁止使用 Markdown 代码块（不要 ``` 或 ```json）。
3. 禁止在 JSON 之前或之后写任何文字、注释、说明、客套话。
4. 占位符坐标必须严格落在 0–13.333 (x/w) 与 0–7.5 (y/h) 英寸内。
5. x/y/w/h 使用英寸（标准 16:9 幻灯片尺寸：宽 13.333 英寸，高 7.5 英寸）。
6. 至少包含一个 type 为 title 的占位符；正文页必须有 type 为 text 的占位符。
7. 避免 placeholder 之间的重叠：同一类型的 text 占位符 x/w 范围应明显不重叠。
8. 标题文字不要超过 30 个汉字或 60 个英文字符，避免与正文争抢空间。
9. 当 key_points / bullet_points 超过 5 条时，建议换为 two_column 或 three_column 布局。
10. 不要使用 emoji。
11. 字段类型严格匹配 schema，缺失字段会被系统判定为生成失败。

## 页面信息
- 页面ID: {page_id}
- 页面类型: {page_type}
- 标题: {title}
- 副标题: {subtitle}
- 要点数量: {num_points}

## 内容摘要
{content_summary}

## 主题风格
{style_info}

## 输出 schema（严格遵守）
{{"theme_name":string,"master":object,"layouts":[object]}}

## 示例输出
{{"theme_name":"简洁专业","master":{{"background":{{"type":"solid","rgb":[255,255,255]}},"color_scheme":{{"primary":[20,40,80],"secondary":[80,100,140],"accent":[60,120,180],"text":[30,30,30],"light_text":[255,255,255]}},"font_scheme":{{"title_font":"Microsoft YaHei","body_font":"Microsoft YaHei","title_size":32,"body_size":16}}}},"layouts":[{{"layout_id":"content","layout_type":"title_content","placeholders":[{{"name":"title","type":"title","x":0.8,"y":0.4,"w":11.7,"h":0.8}},{{"name":"content","type":"text","x":1.0,"y":1.6,"w":11.2,"h":5.2}}]}}]}}"""


# Layout presets for common configurations
LAYOUT_PRESETS = {
    "title_content": [
        ("title", "title", 0.8, 0.4, 11.7, 0.8),
        ("content", "text", 1, 1.6, 11.2, 5.2),
    ],
    "two_column": [
        ("title", "title", 0.8, 0.4, 11.7, 0.8),
        ("content_1", "text", 0.9, 1.6, 5.3, 5.1),
        ("content_2", "text", 7, 1.6, 5.3, 5.1),
    ],
    "three_column": [
        ("title", "title", 0.8, 0.4, 11.7, 0.8),
        ("content_1", "text", 0.9, 1.8, 3.7, 4.7),
        ("content_2", "text", 4.9, 1.8, 3.7, 4.7),
        ("content_3", "text", 8.9, 1.8, 3.5, 4.7),
    ],
    "cover": [
        ("title", "title", 1, 1.7, 11.2, 1.2),
        ("subtitle", "text", 1, 3.1, 10, 0.7),
    ],
    "toc": [
        ("title", "title", 0.8, 0.45, 11.5, 0.7),
        ("content", "text", 1, 1.5, 11, 4.8),
    ],
    "chart_content": [
        ("title", "title", 0.8, 0.4, 11.7, 0.8),
        ("chart", "chart", 1, 1.6, 7.3, 4.9),
        ("content", "text", 8.7, 1.8, 3.7, 4.6),
    ],
    "conclusion": [
        ("title", "title", 0.8, 0.4, 11.7, 0.8),
        ("content", "text", 1, 1.6, 11, 4.8),
    ],
}


def designer_node(state: AgentState) -> AgentState:
    """
    Design layout for the current page.

    This node:
    - Takes page content and outline
    - Generates layout configuration using LLM
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
            num_points=len(page.key_points) + len(page.bullet_points),
            content_summary=_get_content_summary(page),
            style=style,
        )

        # Validate layout
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
    """Generate layout configuration using LLM."""
    prompt = DESIGNER_PROMPT.format(
        page_id=page_id,
        page_type=page_type,
        title=title,
        subtitle=subtitle or "（无）",
        num_points=num_points,
        content_summary=content_summary,
        style_info=style,
    )

    llm = get_llm_client()
    response = llm.generate(prompt=prompt, system="", max_tokens=327680)

    json_text = extract_json_from_text(response)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析失败: {e}")


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
    from ...contracts.schemas import PageContent

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
        num_points=len(key_points) + len(bullet_points),
        content_summary=_get_content_summary(page),
        style=style,
    )

    _validate_layout_data(layout_data, page)

    return layout_data
