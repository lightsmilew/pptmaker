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
编排方式: {layout_mode}；内容密度: {content_density}
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
        "key_points": ["核心要点1（直接来自用户输入）", "核心要点2"],
        "suggest_layout": "建议的布局类型"
    }},
    ...
]

## 布局类型参考
- auto: 一般内容页，由系统选择多样版式；不要所有页面使用同一种结构
- comparison: 需要比较两个对象时使用左右双栏
- timeline: 适合流程、时间顺序、步骤说明
- cards_grid: 适合短小、并列的模块
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
7. 每页的key_points应该是大纲性质的，不要写完整句子。目录页列2至8个章节主题
8. 确保页数与要求一致。subtitle、page_purpose可省略，系统会补齐；不要重复解释字段
9. 整篇大纲必须紧扣用户原始输入，不要输出与用户主题无关的通用模板

请直接输出JSON，不要其他文字。"""

PLANNER_SYSTEM = """你是严格的 JSON API。你的回复必须满足以下契约：
1. 回复只能是一个 JSON 数组，首字符必须是 [，末字符必须是 ]。
2. 严禁输出 Markdown、代码围栏、解释、前后缀文字或 JSON 对象包装。
3. 数组中的每一项必须是 JSON 对象，禁止字符串、数字或 null。
4. 每项必须包含且仅使用这些字段：page_id、page_type、page_title、subtitle、page_purpose、key_points、suggest_layout。
5. page_id 是 page-01 形式的字符串；page_type 必须是 cover、toc、content、chart、table、conclusion、reference、thankyou 之一。
6. key_points 必须是字符串数组；没有要点时返回 []。
7. 输出页数必须严格等于用户要求的页数。
输出前先在内部校验 JSON，校验失败时重新生成；不要输出校验过程。"""


def planning_system(spec):
    if not spec.get('auto_images', False):
        return PLANNER_SYSTEM
    from ...tools.photo_library import planner_catalog
    return PLANNER_SYSTEM.replace('suggest_layout。', 'suggest_layout、可选的 image_id。') + '''
## 自动配图
可在适合的封面、内容、结论或致谢页增加 image_id（下面图库中的精确 ID）；无关时省略。
按本页要表达的主题与图片实际描绘的对象匹配，不要仅凭分类选图，不要假定图片就是用户提及的真实地点、人物或产品。
全篇最多一半页面配图（奇数向上取整），同一张图只用一次。密集内容、目录、图表、表格、对比和流程页不要配图。
图库是主题示意素材；无需输出来源、图片说明、提示词或图片 URL。
配图和制作格式要求属于版式元数据，不要把“配图说明”“真实办公场景配图”等制作指令写成 key_points 或正文论点。
''' + planner_catalog()


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
    notes_value = (spec.get("notes") or "").strip()

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
        layout_mode=spec.get("layout_mode", "auto"), content_density=spec.get("content_density", "balanced"),
        needs_cover=spec.get("needs_cover", True),
        needs_toc=spec.get("needs_toc", True),
        needs_summary=spec.get("needs_summary", True),
        needs_chart=spec.get("needs_chart", False),
        notes=notes_value,
        user_input=user_input or "（用户未提供额外说明）",
        uploaded_files_content=uploaded_files_content,
    )

    try:
        llm = get_llm_client("planner")
        response = None
        last_error = ""
        for attempt in range(2):
            retry_prompt = prompt if attempt == 0 else (
                prompt + "\n\n上一轮输出未通过本地格式校验：" + last_error +
                "。请重新输出完整紧凑JSON数组，不要解释。"
            )
            response = llm.generate(prompt=retry_prompt, system=planning_system(spec), max_tokens=max(2200, page_count * 250))
            try:
                json_text = extract_json_from_text(response)
                outline_data = json.loads(json_text)
                if isinstance(outline_data, dict) and isinstance(outline_data.get("pages"), list):
                    outline_data = outline_data["pages"]
                if not isinstance(outline_data, list) or not all(isinstance(item, dict) for item in outline_data):
                    raise ValueError("顶层必须是对象数组")
                required = ("page_id", "page_type", "page_title", "subtitle", "page_purpose", "key_points", "suggest_layout")
                for index, item in enumerate(outline_data, 1):
                    item.setdefault("subtitle", "")
                    item.setdefault("page_purpose", "")
                    missing = [key for key in required if key not in item]
                    if missing: raise ValueError(f"第 {index} 页缺少字段: {', '.join(missing)}")
                break
            except Exception as exc:
                last_error = str(exc)
        else:
            raise ValueError(f"大纲格式连续校验失败: {last_error}")

        if not isinstance(outline_data, list):
            raise ValueError("大纲响应必须是 JSON 数组")
        if not all(isinstance(item, dict) for item in outline_data):
            raise ValueError("大纲数组中的每一项必须是 JSON 对象")
        required = ("page_id", "page_type", "page_title", "subtitle", "page_purpose", "key_points", "suggest_layout")
        for index, item in enumerate(outline_data, 1):
            missing = [key for key in required if key not in item]
            if missing:
                raise ValueError(f"第 {index} 页大纲缺少字段: {', '.join(missing)}")
            if not isinstance(item["key_points"], list) or not all(isinstance(x, str) for x in item["key_points"]):
                raise ValueError(f"第 {index} 页 key_points 必须是字符串数组")

        from ...tools.photo_library import assign_images
        assign_images(outline_data, spec.get('auto_images', False))
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
                    image_id=page_info.get("image_id"),
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

    notes_value = (spec.get("notes") or "").strip()

    prompt = PLANNER_PROMPT.format(
        topic=spec.get("topic", "未命名主题"),
        audience=spec.get("audience", "通用受众"),
        page_count=page_count,
        style=spec.get("style", "简约专业"),
        layout_mode=spec.get("layout_mode", "auto"), content_density=spec.get("content_density", "balanced"),
        needs_cover=spec.get("needs_cover", True),
        needs_toc=spec.get("needs_toc", True),
        needs_summary=spec.get("needs_summary", True),
        needs_chart=spec.get("needs_chart", False),
        notes=notes_value,
        user_input=user_input or "（用户未提供额外说明）",
        uploaded_files_content=uploaded_files_content,
    )

    llm = get_llm_client("planner")
    response = llm.generate(prompt=prompt, system=planning_system(spec), max_tokens=max(2200, page_count * 250))

    json_text = extract_json_from_text(response)
    outline_data = json.loads(json_text)

    if isinstance(outline_data, dict) and isinstance(outline_data.get("pages"), list):
        outline_data = outline_data["pages"]
    if not isinstance(outline_data, list):
        raise ValueError("大纲响应必须是 JSON 数组")
    if not all(isinstance(item, dict) for item in outline_data):
        raise ValueError("大纲数组中的每一项必须是 JSON 对象")

    for item in outline_data:
        item.setdefault("subtitle", "")
        item.setdefault("page_purpose", "")

    from ...tools.photo_library import assign_images
    return assign_images(outline_data, spec.get('auto_images', False))
