"""Parser node - extracts project requirements from user input."""

import json
import re
from typing import Any, Dict, List, Optional

from ..state import AgentState
from ...llm import get_llm_client
from ...contracts.json_utils import extract_json_from_text
from ...contracts.json_contract import STRICT_JSON_SYSTEM
from ...tools.design_catalog import STYLE_DEFINITIONS, STYLE_NAMES


PARSER_PROMPT = """你是一个专业的PPT需求解析专家。请从用户的输入中提取PPT制作所需的关键信息。

## 用户输入
{user_input}

## 上传文件内容（如果有）
{uploaded_files_content}

## 任务
请分析用户需求，提取以下信息并以JSON格式输出：

1. topic: PPT主题（必填）
2. audience: 目标受众
3. page_count: 建议页数（1-50）
4. style: 根据内容、受众、语气，从下列主题中选择一个最合适的名称，必须逐字使用目录名称：
{style_catalog}
5. needs_cover: 是否需要封面
6. needs_toc: 是否需要目录
7. needs_summary: 是否需要总结页
8. needs_chart: 是否需要图表
9. notes: 特殊要求备注
10. style_reason: 用一句话解释所选主题与内容的关系（不超过80字）

## 输出格式
请输出标准JSON格式：
{{
    "topic": "主题名称",
    "audience": "目标受众描述",
    "page_count": 8,
    "style": "商务简约",
    "style_reason": "适合清晰专业的业务表达",
    "needs_cover": true,
    "needs_toc": true,
    "needs_summary": true,
    "needs_chart": false,
    "notes": "特殊要求或备注"
}}

请直接输出JSON，不要其他文字。"""


def parser_node(state: AgentState) -> AgentState:
    """
    Parse user input and extract project requirements.

    This node:
    - Reads user input and uploaded files
    - Uses LLM to extract structured requirements
    - Updates project spec in state
    """
    state["project"].status = "parsing"
    state["workflow"].current_node = "parser"
    state["workflow"].status = "running"

    user_input = state.get("user_input", "")
    uploaded_files = state.get("uploaded_files", [])

    # Read uploaded file contents
    files_content = []
    for file_path in uploaded_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                files_content.append(f"文件: {file_path}\n内容:\n{content[:2000]}")  # Limit size
        except Exception:
            pass

    uploaded_files_text = "\n\n".join(files_content) if files_content else "无上传文件"

    # Generate prompt
    prompt = PARSER_PROMPT.format(
        user_input=user_input,
        uploaded_files_content=uploaded_files_text,
        style_catalog="；".join(f"{s[0]}（{s[2]}）" for s in STYLE_DEFINITIONS),
    )

    # Call LLM
    try:
        llm = get_llm_client("parser")
        response = llm.generate(prompt=prompt, system=STRICT_JSON_SYSTEM, max_tokens=650, json_object=True)

        # Parse response
        json_text = extract_json_from_text(response)
        spec_data = json.loads(json_text)
        required = {"topic": str, "audience": str, "page_count": int, "style": str,
                    "needs_cover": bool, "needs_toc": bool, "needs_summary": bool,
                    "needs_chart": bool, "notes": str}
        for key, expected in required.items():
            if key not in spec_data or not isinstance(spec_data[key], expected):
                raise ValueError(f"需求解析结果字段无效: {key}")
        if not 1 <= spec_data["page_count"] <= 50:
            raise ValueError("page_count 必须在 1 到 50 之间")

        # Update project spec
        # Keep the user's chosen visual direction through the graph path too.
        automatic = state["project"].spec.get("style", "自动") == "自动"
        reason = str(spec_data.pop("style_reason", ""))[:160]
        if automatic:
            valid = spec_data["style"] in STYLE_NAMES
            if not valid:
                spec_data["style"] = "商务简约"
                reason = "主题分析未返回有效选项，已使用商务简约。"
            state["style_selection"] = {"mode": "auto", "style": spec_data["style"], "reason": reason, "fallback": not valid}
        for key in ("style", "layout_mode", "content_density", "auto_images"):
            if key == "style" and automatic:
                continue
            if key in state["project"].spec:
                spec_data[key] = state["project"].spec[key]
        state["project"].spec = spec_data
        state["project"].page_count = spec_data.get("page_count", 8)

        # Update progress
        state["workflow"].started_at = state["workflow"].started_at

    except Exception as e:
        state["errors"].append({
            "error_id": f"err-{len(state['errors']) + 1}",
            "node": "parser",
            "message": f"解析用户输入失败: {str(e)}",
            "severity": "high"
        })
        state["project"].status = "failed"

    return state


def parse_input(user_input: str, uploaded_files: List[str] = None) -> Dict[str, Any]:
    """
    Standalone function to parse user input.

    Args:
        user_input: Raw user input text
        uploaded_files: List of uploaded file paths

    Returns:
        Parsed specification dict
    """
    uploaded_files = uploaded_files or []

    files_content = []
    for file_path in uploaded_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                files_content.append(f"文件: {file_path}\n内容:\n{content[:2000]}")
        except Exception:
            pass

    uploaded_files_text = "\n\n".join(files_content) if files_content else "无上传文件"

    prompt = PARSER_PROMPT.format(
        user_input=user_input,
        uploaded_files_content=uploaded_files_text,
        style_catalog="；".join(f"{s[0]}（{s[2]}）" for s in STYLE_DEFINITIONS),
    )

    llm = get_llm_client("parser")
    response = llm.generate(prompt=prompt, system=STRICT_JSON_SYSTEM, max_tokens=650, json_object=True)

    json_text = extract_json_from_text(response)
    return json.loads(json_text)
