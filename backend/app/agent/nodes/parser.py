"""Parser node - extracts project requirements from user input."""

import json
import re
from typing import Any, Dict, List, Optional

from ..state import AgentState
from ...llm import get_llm_client
from ...contracts.json_utils import extract_json_from_text


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
4. style: 风格要求（如：简约专业、商务正式、学术报告、科技感等）
5. needs_cover: 是否需要封面
6. needs_toc: 是否需要目录
7. needs_summary: 是否需要总结页
8. needs_chart: 是否需要图表
9. notes: 特殊要求备注

## 输出格式
请输出标准JSON格式：
{{
    "topic": "主题名称",
    "audience": "目标受众描述",
    "page_count": 8,
    "style": "风格描述",
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
        uploaded_files_content=uploaded_files_text
    )

    # Call LLM
    try:
        llm = get_llm_client()
        response = llm.generate(prompt=prompt, system="", max_tokens=327680)

        # Parse response
        json_text = extract_json_from_text(response)
        spec_data = json.loads(json_text)

        # Update project spec
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
        uploaded_files_content=uploaded_files_text
    )

    llm = get_llm_client()
    response = llm.generate(prompt=prompt, system="", max_tokens=327680)

    json_text = extract_json_from_text(response)
    return json.loads(json_text)
