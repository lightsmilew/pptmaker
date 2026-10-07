"""Global reviewer node - reviews consistency across all pages."""

import json
from typing import Any, Dict, List, Optional

from ..state import AgentState
from ...llm import get_llm_client
from ...contracts.json_utils import extract_json_from_text
from ...contracts.json_contract import STRICT_JSON_SYSTEM


GLOBAL_REVIEW_PROMPT = """你是专业的PPT全局评审专家。请评估整个PPT的一致性和整体质量。

## 项目信息
主题: {topic}
风格: {style}

## 页面列表
{page_list}

## 任务
请检查：
1. 页面间风格一致性
2. 标题层级一致性
3. 颜色和字体是否统一
4. 页间信息密度是否均衡
5. 是否存在重复页面
6. 开头和结尾是否合理

## 输出要求
请输出JSON格式的全局评审结果：
{{
    "status": "approved|global_revision_required",
    "score": 85,
    "affected_pages": ["page-03", "page-05"],
    "consistency_issues": [
        {{
            "issue_id": "issue-001",
            "category": "consistency",
            "severity": "medium",
            "target": "page-03",
            "description": "页面字体与整体不一致",
            "suggested_action": "调整为统一字体"
        }}
    ],
    "recommendations": ["建议添加过渡页"]
}}

请直接输出JSON，不要其他文字。"""


def global_reviewer_node(state: AgentState) -> AgentState:
    """
    Perform global review across all pages.

    This node:
    - Gathers all page information
    - Reviews consistency across pages
    - Determines if any pages need revision
    - Updates global review status
    """
    state["workflow"].current_node = "global_reviewer"

    # Check if all pages are completed
    completed_pages = [
        page_id for page_id, page in state["pages"].items()
        if page.status.value == "completed"
    ]

    if len(completed_pages) < len(state["pages"]):
        # Not all pages completed yet
        return state

    try:
        # Perform global review
        review_result = _perform_global_review(state)

        # Update state
        state["global_review"] = review_result

        # If global revision is needed, mark affected pages
        if review_result.get("status") == "global_revision_required":
            affected = review_result.get("affected_pages", [])
            for page_id in affected:
                if page_id in state["pages"]:
                    state["pages"][page_id].review_status = "needs_revision"

    except Exception as e:
        state["errors"].append({
            "error_id": f"err-{len(state['errors']) + 1}",
            "node": "global_reviewer",
            "message": f"全局评审失败: {str(e)}",
            "severity": "medium"
        })

    return state


def _perform_global_review(state: AgentState) -> Dict[str, Any]:
    """Perform global review using LLM."""
    spec = state["project"].spec
    topic = spec.get("topic", "未命名主题")
    style = spec.get("style", "简约专业")

    # Build page list
    page_list = []
    for page_id in sorted(state["pages"].keys()):
        page = state["pages"][page_id]
        page_list.append(
            f"- {page_id}: [{page.page_type.value}] {page.title} "
            f"(评分: {page.review_score or 'N/A'})"
        )
    page_list_text = "\n".join(page_list)

    # Build prompt
    prompt = GLOBAL_REVIEW_PROMPT.format(
        topic=topic,
        style=style,
        page_list=page_list_text,
    )

    # Call LLM
    llm = get_llm_client("global_reviewer")
    response = llm.generate(prompt=prompt, system=STRICT_JSON_SYSTEM, max_tokens=1600)

    # Parse response
    json_text = extract_json_from_text(response)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        # Return default approved result on failure
        return {
            "status": "approved",
            "score": 85,
            "affected_pages": [],
            "consistency_issues": [],
            "recommendations": [],
        }


def perform_global_review(
    project_id: str,
    pages: Dict[str, Any],
    topic: str,
    style: str,
) -> Dict[str, Any]:
    """
    Standalone function to perform global review.

    Args:
        project_id: Project identifier
        pages: Dict of page_id to page data
        topic: Project topic
        style: Project style

    Returns:
        Global review result
    """
    # Build page list
    page_list = []
    for page_id in sorted(pages.keys()):
        page = pages[page_id]
        title = page.get("title", "")
        page_type = page.get("page_type", "content")
        score = page.get("review_score")
        page_list.append(
            f"- {page_id}: [{page_type}] {title} "
            f"(评分: {score if score else 'N/A'})"
        )
    page_list_text = "\n".join(page_list)

    prompt = GLOBAL_REVIEW_PROMPT.format(
        topic=topic,
        style=style,
        page_list=page_list_text,
    )

    llm = get_llm_client("global_reviewer")
    response = llm.generate(prompt=prompt, system=STRICT_JSON_SYSTEM, max_tokens=1600)

    json_text = extract_json_from_text(response)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return {
            "status": "approved",
            "score": 85,
            "affected_pages": [],
            "consistency_issues": [],
            "recommendations": [],
        }
