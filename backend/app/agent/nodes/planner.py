"""Planner node - generates PPT outline."""

import json
from typing import Any, Dict, List, Optional

from ..state import AgentState
from ...llm import get_llm_client
from ...contracts.json_utils import extract_json_from_text


PLANNER_PROMPT = """你是一个专业的PPT大纲规划师。请根据项目需求和用户的原始输入，生成PPT的整体大纲。

## 项目需求
主题: {topic}
目标受众: {audience}
页数要求: {page_count}页
风格: {style}
需要封面: {needs_cover}
需要目录: {needs_toc}
需要总结: {needs_summary}
需要图表: {needs_chart}
特殊备注: {notes}

## 用户原始输入（核心需求来源，必须严格围绕这些内容规划）
{user_input}

## 上传文件内容（如果有，已自动从附件中提取关键片段）
{uploaded_files_content}

## 任务
请严格围绕「用户原始输入」中描述的主题、对比对象、分析维度（类型/功能/结构/评价等）和具体内容要求来规划每一页。
- 每页的 page_title、subtitle、page_purpose、key_points 必须直接服务于用户输入的主题
- 如果用户输入明确点出了要分析的对象（例如具体测试名称、品牌名、模型等），key_points 必须涵盖这些对象
- key_points 应当是用户在原始输入中要求覆盖的具体小标题或论点，而不是泛化的“介绍”“背景”“优势”“劣势”等空话
- 如果用户要求对比两类事物，则需要安排专门的对比页，并在 key_points 中列出对比维度

## 输出要求
请输出JSON数组格式，每个元素代表一页：
[
    {{
        "page_id": "page-01",
        "page_type": "cover|toc|content|chart|table|conclusion|reference|thankyou",
        "page_title": "页面标题（必须与用户输入主题强相关）",
        "subtitle": "副标题（可选）",
        "page_purpose": "本页的作用和目的",
        "key_points": ["核心要点1（直接来自用户输入）", "核心要点2"],
        "suggest_layout": "建议的布局类型"
    }},
    ...
]

## 布局类型参考
- 标题正文: 适合一般内容页
- 左右双栏: 适合对比、分类内容
- 上下分区: 适合流程、步骤说明
- 三列要点: 适合并列内容
- 数据图表: 适合需要图表的页面
- 编号目录: 适合目录页
- 结论重点: 适合总结页

## 注意事项
1. 封面页使用cover类型，标题与用户输入主题一致
2. 目录页使用toc类型
3. 图表页使用chart类型，表格/矩阵类内容使用table类型
4. 总结页使用conclusion类型
5. 内容页使用content类型
6. 最后一页使用thankyou类型
7. 每页的key_points应该是大纲性质的，不要写完整句子
8. 确保页数与要求一致
9. 整篇大纲必须紧扣用户原始输入，不要输出与用户主题无关的通用模板

请直接输出JSON，不要其他文字。"""


def planner_node(state: AgentState) -> AgentState:
    """
    Generate PPT outline.

    This node:
    - Takes parsed project spec
    - Generates page-by-page outline
    - Determines page types and order
    - Provides initial layout suggestions
    """
    state["project"].status = "planning"
    state["workflow"].current_node = "planner"

    spec = state["project"].spec
    page_count = state["project"].page_count

    user_input = state.get("user_input", "")
    uploaded_files = state.get("uploaded_files", []) or []

    # If notes is empty, fall back to user_input so the planner still has the
    # original requirement as explicit context.
    notes_value = (spec.get("notes") or "").strip() or user_input

    files_content = []
    for file_path in uploaded_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                files_content.append(f.read()[:2000])
        except Exception:
            pass
    uploaded_files_content = (
        "\n\n".join(files_content) if files_content else "无上传文件"
    )

    # Generate prompt
    prompt = PLANNER_PROMPT.format(
        topic=spec.get("topic", "未命名主题"),
        audience=spec.get("audience", "通用受众"),
        page_count=page_count,
        style=spec.get("style", "简约专业"),
        needs_cover=spec.get("needs_cover", True),
        needs_toc=spec.get("needs_toc", True),
        needs_summary=spec.get("needs_summary", True),
        needs_chart=spec.get("needs_chart", False),
        notes=notes_value,
        user_input=user_input or "（用户未提供额外说明）",
        uploaded_files_content=uploaded_files_content,
    )

    try:
        llm = get_llm_client()
        response = llm.generate(prompt=prompt, system="", max_tokens=327680)

        # Parse outline
        json_text = extract_json_from_text(response)
        outline_data = json.loads(json_text)

        # Ensure it's a list
        if isinstance(outline_data, dict) and "pages" in outline_data:
            outline_data = outline_data["pages"]

        # Update state
        state["outline"] = outline_data

        # Initialize page states
        for page_info in outline_data:
            page_id = page_info.get("page_id")
            if page_id:
                from ...models.page import PageState, PageType
                page_type_str = page_info.get("page_type", "content")
                try:
                    page_type = PageType(page_type_str)
                except ValueError:
                    page_type = PageType.CONTENT

                state["pages"][page_id] = PageState(
                    page_id=page_id,
                    page_type=page_type,
                    title=page_info.get("page_title", ""),
                    subtitle=page_info.get("subtitle", ""),
                    key_points=page_info.get("key_points", []),
                    layout_type=page_info.get("suggest_layout", "标题正文"),
                )

        # Set first page as current
        if outline_data:
            state["current_page_id"] = outline_data[0].get("page_id")

    except Exception as e:
        state["errors"].append({
            "error_id": f"err-{len(state['errors']) + 1}",
            "node": "planner",
            "message": f"生成大纲失败: {str(e)}",
            "severity": "high"
        })
        state["project"].status = "failed"

    return state


def generate_outline(
    spec: Dict[str, Any],
    page_count: int = None,
    user_input: str = "",
    uploaded_files: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Standalone function to generate outline.

    Args:
        spec: Project specification
        page_count: Override page count
        user_input: Original user requirement text
        uploaded_files: Paths to uploaded files whose contents are excerpted
            into the prompt for additional context.

    Returns:
        List of outline items
    """
    page_count = page_count or spec.get("page_count", 8)
    uploaded_files = uploaded_files or []

    files_content = []
    for file_path in uploaded_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                files_content.append(f.read()[:2000])
        except Exception:
            pass
    uploaded_files_content = (
        "\n\n".join(files_content) if files_content else "无上传文件"
    )

    notes_value = (spec.get("notes") or "").strip() or user_input

    prompt = PLANNER_PROMPT.format(
        topic=spec.get("topic", "未命名主题"),
        audience=spec.get("audience", "通用受众"),
        page_count=page_count,
        style=spec.get("style", "简约专业"),
        needs_cover=spec.get("needs_cover", True),
        needs_toc=spec.get("needs_toc", True),
        needs_summary=spec.get("needs_summary", True),
        needs_chart=spec.get("needs_chart", False),
        notes=notes_value,
        user_input=user_input or "（用户未提供额外说明）",
        uploaded_files_content=uploaded_files_content,
    )

    llm = get_llm_client()
    response = llm.generate(prompt=prompt, system="", max_tokens=327680)

    json_text = extract_json_from_text(response)
    outline_data = json.loads(json_text)

    if isinstance(outline_data, dict) and "pages" in outline_data:
        outline_data = outline_data["pages"]

    return outline_data
