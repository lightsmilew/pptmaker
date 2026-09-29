"""Writer node - generates page content using unified contract."""

import json
from typing import Any, Dict, List, Optional

from ..state import AgentState
from ...llm import get_llm_client
from ...contracts.json_utils import extract_json_from_text
from ...contracts.structured_llm import StructuredLLMCaller


WRITER_PROMPT = """你是一个专业的PPT内容撰写师。请把页面大纲扩写成可直接放进幻灯片的讲解内容，并**只输出一个 JSON 对象**，不要任何解释文字或 Markdown 围栏。

## 规则（必须遵守）
1. 整段回复必须是一个合法 JSON 对象，第一字符是 `{{`，最后一字符是 `}}`。
2. 禁止使用 Markdown 代码块（不要 ``` 或 ```json）。
3. 禁止在 JSON 之前或之后写任何文字、注释、说明、客套话。
4. 字段类型必须严格匹配下面的 schema，缺失字段会被系统判定为生成失败。
5. key_points 是经过润色的页面结论，保留大纲结构但不要逐字复制。
6. bullet_points 是对 key_points 的解释性正文，每条补充原因、构成、例子、影响或评价。
7. 每条 bullet_points 控制在 50 字以内，适合 8-10 分钟演示的单页讲解。
8. 不要编造用户没有提供的数字、来源或事实；缺少证据时使用定性表述。
9. 只生成当前页内容，不改变页面主题和事实范围。
10. 如果用户原始输入包含明确对象（如 TOEFL/IELTS/GRE 等具体测试名），key_points 必须直接包含这些对象的对应分析。

## 当前页信息
- 页面ID: {page_id}
- 页面类型: {page_type}
- 页面标题: {page_title}
- 副标题: {subtitle}
- 主题: {topic}

## 大纲要点（写作依据）
{key_points}

## 用户原始输入
{user_input}

## 输出 schema（严格遵守）
{{"title":string,"subtitle":string,"key_points":string[],"bullet_points":string[],"speaker_notes":string}}

## 示例输出
{{"title":"TOEFL 学术定位","subtitle":"面向北美高校的语言能力测试","key_points":["学术导向","机考形式","四技能覆盖"],"bullet_points":["TOEFL 服务北美高校申请，强调学术英语能力。","采用 iBT 机考形式，整合听说读写四项。","评分逻辑以学术场景任务为核心。"],"speaker_notes":"本页强调 TOEFL 的学术定位与机考结构。"}}"""


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
    user_input = state.get("user_input", "")

    # Generate content
    try:
        content_data = _generate_page_content(
            page_id=page_id,
            page_type=page.page_type.value,
            page_title=outline_item.get("page_title", ""),
            subtitle=outline_item.get("subtitle", ""),
            topic=topic,
            key_points=outline_item.get("key_points", []),
            user_input=user_input,
        )

        # Update page state
        page.title = content_data.get("title", page.title)
        page.subtitle = content_data.get("subtitle", "")
        page.key_points = content_data.get("key_points", [])
        page.bullet_points = content_data.get("bullet_points", [])
        page.speaker_notes = content_data.get("speaker_notes", "")

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
) -> Dict[str, Any]:
    """Generate page content using LLM with structured output."""
    key_points_text = "\n".join([f"- {kp}" for kp in key_points]) if key_points else "（无大纲要点）"

    prompt = WRITER_PROMPT.format(
        page_id=page_id,
        page_type=page_type,
        page_title=page_title,
        subtitle=subtitle or "（无）",
        topic=topic,
        key_points=key_points_text,
        user_input=user_input or "（无额外上下文）",
    )

    llm = get_llm_client()
    response = llm.generate(prompt=prompt, system="", max_tokens=327680)

    # Extract and parse JSON
    json_text = extract_json_from_text(response)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析失败: {e}")

    # Basic validation
    if not isinstance(data, dict):
        raise ValueError("响应不是JSON对象")

    # Ensure required fields
    data.setdefault("title", page_title)
    data.setdefault("key_points", key_points)
    data.setdefault("bullet_points", [])
    data.setdefault("speaker_notes", "")

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
