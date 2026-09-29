"""Revision planner - converts critic feedback to actionable operations."""

import json
from typing import Any, Dict, List, Optional

from ..state import AgentState
from ...llm import get_llm_client
from ...contracts.json_utils import extract_json_from_text


REVISION_PLANNER_PROMPT = """你是专业的布局修订规划师。请根据评审意见生成具体的修订操作。

## 评审结果
状态: {status}
评分: {score}
问题列表:
{issues_list}

## 当前布局信息
布局ID: {layout_id}
布局类型: {layout_type}
占位符列表:
{placeholders}

## 可用的修订操作
- move: 移动元素 {target: "元素名", changes: {x: 新x, y: 新y}}
- resize: 调整大小 {target: "元素名", changes: {w: 新宽度, h: 新高度, x: 新x, y: 新y}}
- change_font_size: 调整字号 {target: "元素名", changes: {font_size: 新字号}}
- change_font: 更换字体 {target: "元素名", changes: {font: 新字体}}
- change_color: 调整颜色 {target: "元素名", changes: {color: [r,g,b]}}
- change_layout: 更换布局 {changes: {layout_type: 新布局类型}}
- reduce_spacing: 减小间距
- increase_spacing: 增加间距
- hide_optional_element: 隐藏可选元素 {target: "元素名"}

## 输出要求
请输出JSON格式的修订计划：
{{
    "operations": [
        {{
            "op": "resize",
            "target": "content",
            "changes": {{"h": 5.5}}
        }}
    ],
    "reason": "修订原因说明",
    "expected_improvement": "预期改进效果"
}}

请直接输出JSON，不要其他文字。"""


def revision_planner_node(state: AgentState) -> AgentState:
    """
    Generate revision plan from critic feedback.

    This node:
    - Takes critic review results
    - Converts issues to actionable operations
    - Updates page with revision plan
    """
    page_id = state.get("current_page_id")
    if not page_id:
        return state

    page = state["pages"].get(page_id)
    if not page:
        return state

    # Check if revision is needed
    if page.review_status != "needs_revision":
        return state

    state["workflow"].current_node = "revision_planner"
    page.status = "revising"

    # Increment layout retry count
    state["layout_retry_count"] = state.get("layout_retry_count", 0) + 1

    try:
        # Generate revision plan
        revision_plan = _generate_revision_plan(
            page=page,
            issues=page.review_issues,
        )

        # Store revision plan in page (for now, just update iteration)
        page.iteration += 1

        state["pages"][page_id] = page

    except Exception as e:
        state["errors"].append({
            "error_id": f"err-{len(state['errors']) + 1}",
            "node": "revision_planner",
            "message": f"生成修订计划失败: {str(e)}",
            "severity": "medium"
        })

    return state


def _generate_revision_plan(
    page: Any,
    issues: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate revision plan from issues."""
    # Format issues
    issues_list = []
    for issue in issues:
        issues_list.append(
            f"- {issue.get('description', '')} "
            f"(severity: {issue.get('severity', 'unknown')}, "
            f"target: {issue.get('target', 'unknown')})"
        )
    issues_text = "\n".join(issues_list) if issues_list else "（无问题）"

    # Format placeholders
    placeholders_text = ""
    if page.layout_json:
        for p in page.layout_json.get("placeholders", []):
            placeholders_text += (
                f"- {p.get('name')}: type={p.get('type')}, "
                f"x={p.get('x')}, y={p.get('y')}, "
                f"w={p.get('w')}, h={p.get('h')}\n"
            )

    # Build prompt
    prompt = REVISION_PLANNER_PROMPT.format(
        status=page.review_status,
        score=page.review_score or 0,
        issues_list=issues_text,
        layout_id=page.layout_json.get("layout_id", "unknown") if page.layout_json else "unknown",
        layout_type=page.layout_type,
        placeholders=placeholders_text or "（无布局信息）",
    )

    # Call LLM
    llm = get_llm_client()
    response = llm.generate(prompt=prompt, system="", max_tokens=327680)

    # Parse response
    json_text = extract_json_from_text(response)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        # Return empty plan on failure
        return {"operations": [], "reason": "解析失败", "expected_improvement": ""}


def _apply_revision_operations(
    layout_json: Dict[str, Any],
    operations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Apply revision operations to layout.

    This function applies the revision plan to the layout JSON,
    modifying coordinates, sizes, fonts, etc.
    """
    if not layout_json or not operations:
        return layout_json

    # Deep copy to avoid modifying original
    new_layout = json.loads(json.dumps(layout_json))

    # Create placeholder lookup
    placeholders = {p["name"]: p for p in new_layout.get("placeholders", [])}

    for op in operations:
        op_type = op.get("op")
        target = op.get("target")
        changes = op.get("changes", {})

        if target not in placeholders:
            continue

        p = placeholders[target]

        if op_type == "move":
            if "x" in changes:
                p["x"] = changes["x"]
            if "y" in changes:
                p["y"] = changes["y"]

        elif op_type == "resize":
            if "x" in changes:
                p["x"] = changes["x"]
            if "y" in changes:
                p["y"] = changes["y"]
            if "w" in changes:
                p["w"] = changes["w"]
            if "h" in changes:
                p["h"] = changes["h"]

        elif op_type == "change_font_size":
            # Would need to update master or add inline style
            if "font_size" in changes:
                # For simplicity, just note the change
                # In real implementation, would update master or add style field
                pass

        elif op_type == "change_layout":
            # Would need to completely replace layout
            if "layout_type" in changes:
                # Mark for complete layout regeneration
                new_layout["_replacement_needed"] = True
                new_layout["_new_layout_type"] = changes["layout_type"]

    return new_layout


def generate_revision_plan(
    page_id: str,
    layout_json: Dict[str, Any],
    issues: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Standalone function to generate revision plan.

    Args:
        page_id: Page identifier
        layout_json: Current layout configuration
        issues: List of review issues

    Returns:
        Revision plan dict
    """
    class PageObj:
        pass

    page = PageObj()
    page.page_id = page_id
    page.layout_json = layout_json
    page.review_status = "needs_revision"
    page.review_score = 0

    return _generate_revision_plan(page, issues)
