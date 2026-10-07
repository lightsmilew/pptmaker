"""Critic node - multi-modal image review for visual quality."""

import json
import os
import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..state import AgentState
from ...llm import get_llm_client
from ...contracts.json_utils import extract_json_from_text


CRITIC_PROMPT = """检查所附幻灯片的排版、可读性、溢出、对齐与信息层级。只返回紧凑JSON：
{"status":"approved|needs_revision|blocked|failed","score":0,"issues":[],"next_action":"approve|revise_layout|revise_content|blocked|failed"}。
issues最多3项，每项包含issue_id、category、severity、target、description、suggested_action、owner(layout或content)。
无法看到图片则blocked。不要编造检查结果。评分80以上且无严重问题才通过。"""


def critic_node(state: AgentState) -> AgentState:
    """
    Review the current page's visual quality.

    This node:
    - Reads the preview image
    - Analyzes visual quality using multi-modal LLM
    - Updates page review status
    - Determines if revision is needed
    """
    page_id = state.get("current_page_id")
    if not page_id:
        return state

    page = state["pages"].get(page_id)
    if not page:
        return state
    if page.status == "failed":
        page.review_status = "failed"
        return state

    state["workflow"].current_node = "critic"
    page.status = "reviewing"

    # Increment critic iteration
    state["critic_iteration"] = state.get("critic_iteration", 0) + 1
    page.iteration = state["critic_iteration"]

    try:
        mode = state["project"].spec.get("review_mode", os.getenv("PPT_REVIEW_MODE", "local"))
        if mode == "vision":
            review_result = _review_page_image(page, page.review_issues or None, page.iteration)
        else:
            from ...tools.slide_quality import review_scene
            review_result = review_scene(page.to_dict(), state["project"].spec.get("style", "商务简约"))
        page.review_method = review_result.get("review_method", "vision")

        # Update page state
        page.review_status = review_result.get("status")
        page.review_score = review_result.get("score", 0)
        page.review_issues = review_result.get("issues", [])
        page.review_suggestions = [
            issue.get("suggested_action", "")
            for issue in review_result.get("issues", [])
        ]

        state["pages"][page_id] = page

    except Exception as e:
        page.review_status = "blocked"
        page.review_score = 0
        page.error = f"评审异常: {str(e)}"
        state["errors"].append({
            "error_id": f"err-{len(state['errors']) + 1}",
            "node": "critic",
            "message": str(e),
            "severity": "low",
        })

    return state


def _review_page_image(
    page: Any,
    previous_review: Optional[List[Dict]] = None,
    iteration: int = 1,
) -> Dict[str, Any]:
    """Review page image using LLM."""
    # Read image and convert to base64
    image_base64 = None
    if page.preview and page.preview.image_path:
        image_path = Path(page.preview.image_path)
        if image_path.exists():
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")

    # Get content summary
    content_summary = _get_content_summary(page)

    # Get previous issues for context
    previous_issues_text = ""
    if previous_review:
        issues_list = "\n".join([
            f"- {issue.get('description', '')} (severity: {issue.get('severity', 'unknown')})"
            for issue in previous_review[:5]
        ])
        previous_issues_text = f"\n\n## 上一轮发现的问题\n{issues_list}\n请特别关注这些问题是否已解决。"

    # Build prompt
    prompt = f"""请分析以下PPT页面的视觉效果。

## 页面信息
- 标题: {page.title or '无标题'}
- 内容摘要: {content_summary}
- 布局类型: {page.layout_type}

{previous_issues_text}

请直接输出JSON格式的评审结果。"""

    # Call LLM
    llm = get_llm_client("critic")

    if not image_base64:
        return {"status": "blocked", "score": 0, "issues": [], "next_action": "blocked",
                "review_method": "vision", "error": "缺少可读取的预览图片"}
    response = llm.generate_with_image(prompt=prompt, image_base64=image_base64,
                                       system=CRITIC_PROMPT, max_tokens=650)

    # Parse response
    json_text = extract_json_from_text(response)

    try:
        result = json.loads(json_text)
        if not isinstance(result, dict):
            raise ValueError("复核结果必须是对象")
        if result.get("status") not in {"approved", "needs_revision", "blocked", "failed"}:
            raise ValueError("复核 status 无效")
        if not isinstance(result.get("score"), (int, float)) or not 0 <= result["score"] <= 100:
            raise ValueError("复核 score 必须是 0 到 100")
        if not isinstance(result.get("issues"), list):
            raise ValueError("复核 issues 必须是数组")
        return result
    except json.JSONDecodeError as exc:
        raise ValueError("图片评审返回无效JSON") from exc


def _get_content_summary(page: Any) -> str:
    """Get content summary for review prompt."""
    parts = []

    if page.key_points:
        parts.append("要点: " + ", ".join(page.key_points[:3]))

    if page.bullet_points:
        bullet_text = ". ".join(page.bullet_points[:2])
        if bullet_text:
            parts.append("说明: " + bullet_text[:100])

    return "\n".join(parts) or "（无详细内容）"


def review_page(
    page_id: str,
    page_data: Dict[str, Any],
    preview_path: str,
    layout_type: str,
    iteration: int = 1,
    previous_issues: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Standalone function to review a page.

    Args:
        page_id: Page identifier
        page_data: Page content data
        preview_path: Path to preview image
        layout_type: Layout type
        iteration: Current iteration
        previous_issues: Previous review issues

    Returns:
        Review result dict
    """
    class PageObj:
        pass

    page = PageObj()
    page.page_id = page_id
    page.title = page_data.get("title", "")
    page.key_points = page_data.get("key_points", [])
    page.bullet_points = page_data.get("bullet_points", [])
    page.layout_type = layout_type
    page.preview = type('obj', (object,), {'image_path': preview_path})()

    return _review_page_image(page, previous_issues, iteration)
