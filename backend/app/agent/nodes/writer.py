"""Writer node - generates page content using unified contract."""

import json
from typing import Any, Dict, List, Optional

from ..state import AgentState
from ...llm import get_llm_client
from ...contracts.json_utils import extract_json_from_text
from ...contracts.structured_llm import StructuredLLMCaller


WRITER_SYSTEM = """你只负责输入最后一个page对象指定的这一页，不是整份PPT。
reference是整篇参考材料，其中的页码和制作指令不能覆盖当前page的type、title和points。
将当前页大纲写成清晰、准确、适合演示的内容。只返回紧凑JSON对象。
格式：{"items":[["短标题","解释"]]}；需要讲稿时可加notes。
每页2至5组，每个标题不超过16个汉字，每个解释不超过45个汉字。
保留原文的具体对象、结论与必要证据。不编造数据、来源或事实。不要口号、emoji或重复标题。
图表或表格页只写1至2组重点解释。当前page.type为chart且来源提供真实数值时，必须加chart_data:{"title":"","data":{"labels":[],"values":[]}}，不要输出table_data。
表格页可以加table_data:{"headers":[],"rows":[[]]}，最多4列5行，仅整理来源中已有的比较信息。
无法形成图表时用文本解释。无需输出标题、副标题、配色、坐标、null或空字段。"""


def writer_node(state: AgentState) -> AgentState:
    """
    Generate content for the current page.

    This node:
    - Takes page outline
    - Generates detailed content using LLM
    - Uses unified JSON contract for validation
    - Updates page state
    """
    page_id = state.get("current_page_id")
    if not page_id:
        return state

    page = state["pages"].get(page_id)
    if not page:
        return state

    state["workflow"].current_node = "writer"
    page.status = "writing"

    # Find outline for this page
    outline_item = None
    for item in state.get("outline", []):
        if item.get("page_id") == page_id:
            outline_item = item
            break

    if not outline_item:
        page.status = "failed"
        page.error = "未找到页面大纲"
        return state

    spec = state["project"].spec
    topic = spec.get("topic", "未命名主题")
    user_input = state.get("user_input", "") or spec.get("source_summary", "")

    # Covers and navigation reuse the approved outline; no expansion call is needed.
    if page.page_type.value in ("cover", "thankyou", "toc"):
        page.title = outline_item.get("page_title", page.title)
        page.subtitle = outline_item.get("subtitle", "")
        page.key_points = ((outline_item.get("key_points") or [item.get("page_title", "") for item in state.get("outline", [])
                            if item.get("page_type") not in ("cover", "toc", "thankyou")]
                           ) if page.page_type.value == "toc" else [])
        page.bullet_points = []
        page.speaker_notes = ""
        return state

    try:
        content_data = _generate_page_content(
            page_id=page_id,
            page_type=page.page_type.value,
            page_title=outline_item.get("page_title", ""),
            subtitle=outline_item.get("subtitle", ""),
            topic=topic,
            key_points=outline_item.get("key_points", []),
            user_input=user_input,
            feedback=page.review_issues,
            include_notes=bool(spec.get("speaker_notes", False)),
            content_density=spec.get("content_density", "balanced"),
        )

        # Update page state
        page.title = content_data.get("title", page.title)
        page.subtitle = content_data.get("subtitle", "")
        page.key_points = content_data.get("key_points", [])
        page.bullet_points = content_data.get("bullet_points", [])
        page.speaker_notes = content_data.get("speaker_notes", "")
        page.chart_data = content_data.get("chart_data")
        page.table_data = content_data.get("table_data")

        state["pages"][page_id] = page

    except Exception as e:
        page.status = "failed"
        page.error = f"内容生成失败: {str(e)}"
        state["errors"].append({
            "error_id": f"err-{len(state['errors']) + 1}",
            "node": "writer",
            "message": str(e),
            "severity": "medium"
        })

    return state


def _generate_page_content(
    page_id: str,
    page_type: str,
    page_title: str,
    subtitle: str,
    topic: str,
    key_points: List[str],
    user_input: str = "",
    feedback: Optional[List[Dict]] = None,
    include_notes: bool = False,
    content_density: str = "balanced",
) -> Dict[str, Any]:
    """Generate page content using LLM with structured output."""
    # Put stable source before page-specific data to preserve a reusable prefix.
    from ..context import page_source
    relevant = page_source(user_input, page_title, key_points)
    shared = {"topic": topic, "source": user_input if relevant == user_input else user_input[:500]}
    # Keep the density instruction in the stable prefix across pages.
    shared["density"] = {"airy":"每页2至3组，解释最多25字", "balanced":"每页2至4组，解释最多40字",
                         "compact":"每页3至5组，解释最多45字"}.get(content_density, "每页2至4组，解释最多40字")
    page_request = {"type": page_type, "title": page_title, "points": key_points}
    if relevant != user_input:
        page_request["source_passages"] = relevant
    if feedback:
        page_request["fix"] = [{"problem": issue.get("description", ""),
                                 "action": issue.get("suggested_action", "")} for issue in feedback[:3]]
    if include_notes:
        page_request["notes"] = "附80字以内讲稿"
    prompt = json.dumps({"reference":shared}, ensure_ascii=False, separators=(",", ":")) + "\n" + json.dumps(
        {"page":page_request}, ensure_ascii=False, separators=(",", ":"))
    llm = get_llm_client("writer")
    response = llm.generate(prompt=prompt, system=WRITER_SYSTEM,
                            max_tokens=1400 if page_type in ("chart", "table") else 700 if content_density == "airy" else 1000,
                            temperature=0.35, json_object=True, cache=not feedback)
    data = json.loads(extract_json_from_text(response))
    if not isinstance(data, dict):
        raise ValueError("响应不是JSON对象")
    if "items" in data:
        items = data["items"]
        if not isinstance(items, list) or not 1 <= len(items) <= 12:
            raise ValueError("items必须包含1至12组内容")
        if not all(isinstance(item, list) and len(item) == 2 and all(isinstance(v,str) for v in item)
                   for item in items):
            raise ValueError("items每项必须是[标题,解释]两个字符串")
        limit = {"airy":3,"balanced":4,"compact":5}.get(content_density,4)
        if len(items) > limit:
            # Models sometimes expand every outline point despite the density
            # instruction. Merge adjacent groups without dropping their facts.
            items = [[" · ".join(row[0] for row in items[len(items)*i//limit:len(items)*(i+1)//limit]),
                      "；".join(row[1] for row in items[len(items)*i//limit:len(items)*(i+1)//limit])]
                     for i in range(limit)]
        data = {"title": page_title, "subtitle": subtitle,
                "key_points": [item[0] for item in items],
                "bullet_points": [item[1] for item in items],
                "speaker_notes": data.get("notes", ""),
                **{key: data[key] for key in ("chart_data", "table_data") if key in data}}
    # Keep compatibility with previously stored/full-contract responses.
    for key in ("title", "subtitle", "speaker_notes"):
        if not isinstance(data.get(key), str):
            raise ValueError(f"字段 {key} 必须是字符串")
    for key in ("key_points", "bullet_points"):
        if not isinstance(data.get(key), list) or not all(isinstance(v, str) for v in data[key]):
            raise ValueError(f"字段 {key} 必须是字符串数组")
    if not include_notes:
        data["speaker_notes"] = ""
    return data


def generate_page_content(
    page_id: str,
    page_type: str,
    page_title: str,
    subtitle: str,
    topic: str,
    key_points: List[str],
    user_input: str = "",
) -> Dict[str, Any]:
    """
    Standalone function to generate page content.

    Args:
        page_id: Page identifier
        page_type: Type of page (cover, toc, content, etc.)
        page_title: Title for the page
        subtitle: Subtitle
        topic: Overall topic
        key_points: Outline key points
        user_input: Original user requirement text (optional)

    Returns:
        Generated content dict
    """
    return _generate_page_content(
        page_id=page_id,
        page_type=page_type,
        page_title=page_title,
        subtitle=subtitle,
        topic=topic,
        key_points=key_points,
        user_input=user_input,
    )
