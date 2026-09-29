"""Structured LLM caller with unified retry and validation logic."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from .json_utils import extract_json_from_text, JSONParseError
from .errors import (
    ContractError,
    SchemaValidationError,
    SemanticValidationError,
    LLMParsingError,
    MaxRetriesExceededError,
)
from .schemas import (
    ReviewResult,
    ReviewStatus,
    ReviewIssue,
    ReviewDimensions,
    IssueSeverity,
    IssueCategory,
    IssueOwner,
)

T = TypeVar("T")


@dataclass
class LLMCallResult:
    """Result of an LLM call."""

    success: bool
    data: Any = None
    raw_response: str = ""
    error: Optional[str] = None
    attempt: int = 1
    validation_errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RetryContext:
    """Context for retry attempts."""

    max_retries: int = 3
    current_attempt: int = 0
    last_error: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)

    def should_retry(self) -> bool:
        """Check if should retry."""
        return self.current_attempt < self.max_retries

    def increment(self) -> "RetryContext":
        """Create new context with incremented attempt."""
        return RetryContext(
            max_retries=self.max_retries,
            current_attempt=self.current_attempt + 1,
            last_error=self.last_error,
            validation_errors=self.validation_errors.copy()
        )


class StructuredLLMCaller:
    """
    Unified LLM caller with structured output support.

    Features:
    - Automatic JSON extraction and parsing
    - Schema validation
    - Configurable retry strategies
    - Error categorization
    """

    def __init__(
        self,
        llm_client: Any,
        default_max_retries: int = 3,
        default_max_tokens: int = 4096,
    ):
        """
        Initialize the caller.

        Args:
            llm_client: LLM client with .generate(prompt, system, max_tokens) method
            default_max_retries: Default maximum retry attempts
            default_max_tokens: Default max tokens for generation
        """
        self.llm = llm_client
        self.default_max_retries = default_max_retries
        self.default_max_tokens = default_max_tokens

    def call(
        self,
        prompt: str,
        system: str = "",
        expected_type: Type[T] = None,
        contract_name: str = "unknown",
        max_retries: int = None,
        max_tokens: int = None,
        additional_validation: Callable[[Any], List[str]] = None,
        retry_on_validation_failure: bool = True,
    ) -> LLMCallResult:
        """
        Call LLM with structured output handling.

        Args:
            prompt: User prompt
            system: System prompt
            expected_type: Pydantic model to validate against
            contract_name: Name for error messages
            max_retries: Maximum retry attempts (uses default if None)
            max_tokens: Max tokens for generation
            additional_validation: Optional extra validation function
            retry_on_validation_failure: Whether to retry on validation failure

        Returns:
            LLMCallResult with success status and parsed data
        """
        max_retries = max_retries or self.default_max_retries
        max_tokens = max_tokens or self.default_max_tokens

        context = RetryContext(max_retries=max_retries)

        while context.should_retry():
            context = context.increment()

            # Make the LLM call
            try:
                raw_response = self.llm.generate(
                    prompt=prompt,
                    system=system,
                    max_tokens=max_tokens
                )

                # Extract JSON
                json_text = extract_json_from_text(raw_response)

                # Parse JSON
                try:
                    data = json.loads(json_text)
                except json.JSONDecodeError as e:
                    context.last_error = f"JSON解析失败: {e}"
                    context.validation_errors.append(str(e))
                    continue

                # Validate against schema
                validation_errors = []
                if expected_type is not None:
                    validation_errors = self._validate_schema(data, expected_type)

                # Additional validation
                if additional_validation and callable(additional_validation):
                    extra_errors = additional_validation(data)
                    validation_errors.extend(extra_errors)

                if validation_errors:
                    context.last_error = "; ".join(validation_errors)
                    context.validation_errors = validation_errors
                    if retry_on_validation_failure:
                        # Modify prompt to include error feedback
                        continue
                    else:
                        return LLMCallResult(
                            success=False,
                            raw_response=raw_response,
                            error=context.last_error,
                            attempt=context.current_attempt,
                            validation_errors=validation_errors,
                        )

                # Success
                # If we have a Pydantic model, instantiate it
                if expected_type is not None and hasattr(expected_type, "model_validate"):
                    try:
                        validated_data = expected_type.model_validate(data)
                    except Exception as e:
                        return LLMCallResult(
                            success=False,
                            raw_response=raw_response,
                            error=f"模型验证失败: {e}",
                            attempt=context.current_attempt,
                        )
                    return LLMCallResult(
                        success=True,
                        data=validated_data,
                        raw_response=raw_response,
                        attempt=context.current_attempt,
                    )

                return LLMCallResult(
                    success=True,
                    data=data,
                    raw_response=raw_response,
                    attempt=context.current_attempt,
                )

            except Exception as e:
                context.last_error = str(e)
                if not context.should_retry():
                    return LLMCallResult(
                        success=False,
                        error=str(e),
                        attempt=context.current_attempt,
                    )

        # Max retries exceeded
        return LLMCallResult(
            success=False,
            error=f"超过最大重试次数({max_retries}): {context.last_error}",
            attempt=context.current_attempt,
            validation_errors=context.validation_errors,
        )

    def _validate_schema(self, data: Any, expected_type: Type[T]) -> List[str]:
        """
        Validate data against expected type.

        Args:
            data: Data to validate
            expected_type: Expected Pydantic model

        Returns:
            List of validation error messages
        """
        errors = []

        if not hasattr(expected_type, "model_validate"):
            return errors

        try:
            expected_type.model_validate(data)
        except Exception as e:
            errors.append(f"Schema验证失败: {e}")

        return errors

    def call_for_review(
        self,
        prompt: str,
        system: str = "",
        iteration: int = 1,
        previous_issues: List[ReviewIssue] = None,
    ) -> LLMCallResult:
        """
        Call LLM specifically for review/evaluation.

        Args:
            prompt: User prompt (usually includes image)
            system: System prompt
            iteration: Current iteration number
            previous_issues: Previous review issues for context

        Returns:
            LLMCallResult with ReviewResult
        """
        # Add iteration context to system prompt
        system_with_context = system
        if previous_issues:
            issues_str = "\n".join([
                f"- {issue.issue_id}: {issue.description} (severity: {issue.severity.value}, owner: {issue.owner.value})"
                for issue in previous_issues
            ])
            system_with_context = f"""{system}

## 上一轮评审发现的问题（供参考）:
{issues_str}

请特别关注这些问题是否已解决。
"""

        result = self.call(
            prompt=prompt,
            system=system_with_context,
            expected_type=ReviewResult,
            contract_name="review_result",
            max_retries=3,
        )

        return result


# Prompt templates for common operations
CRITIC_PROMPT_TEMPLATE = """你是专业的PPT视觉评审专家。请评估以下幻灯片页面的视觉质量。

## 当前页面信息
- 页面类型: {page_type}
- 标题: {title}
- 内容摘要: {content_summary}
- 布局类型: {layout_type}

## 画布信息
- 宽度: {canvas_width}px
- 高度: {canvas_height}px
- 宽高比: {aspect_ratio}

## 设计规则
- 最小正文字号: {min_font_size}
- 最大内容密度: {max_density}
- 安全边距: {safe_margin}px

## 评审维度（每项0-10分）
1. alignment（对齐）- 元素对齐、一致性
2. balance（平衡）- 视觉平衡、重量感分布
3. readability（可读性）- 字体大小、对比度、行距
4. hierarchy（层级）- 标题、正文、强调的层次关系
5. density（密度）- 信息密度是否合适（不过于拥挤或空旷）
6. consistency（一致性）- 与整体风格的一致性

## 输出要求
请输出JSON格式的评审结果：
{{
    "status": "approved|needs_revision|blocked|failed",
    "score": 85-100为通过，低于85需要调整，
    "dimensions": {{
        "alignment": 0-10,
        "balance": 0-10,
        "readability": 0-10,
        "hierarchy": 0-10,
        "density": 0-10,
        "consistency": 0-10
    }},
    "issues": [
        {{
            "issue_id": "issue-001",
            "category": "alignment|whitespace|density|hierarchy|font_size|contrast|overflow|overlap|balance|consistency",
            "severity": "low|medium|high|critical",
            "target": "content_1, title等元素名",
            "description": "问题描述",
            "suggested_action": "具体修改建议",
            "owner": "layout|content"
        }}
    ],
    "next_action": "revise_layout|revise_content|approve|blocked|failed"
}}

## 判断标准
- 评分>=85且无高严重性问题：通过(approved)
- 评分<85或有中等问题：需要调整(needs_revision)
- 渲染失败或无法判断：阻塞(blocked)
- 严重问题导致无法继续：失败(failed)

请直接输出JSON，不要其他文字。
"""

REVISION_PLANNER_PROMPT_TEMPLATE = """你是布局修订规划师。请根据评审意见生成具体的修订操作。

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
- move: 移动元素 {target: "元素名", changes: {{x: 新x, y: 新y}}}
- resize: 调整大小 {target: "元素名", changes: {{w: 新宽度, h: 新高度, x: 新x, y: 新y}}}
- change_font_size: 调整字号 {target: "元素名", changes: {{font_size: 新字号}}}
- change_font: 更换字体 {target: "元素名", changes: {{font: 新字体}}}
- change_color: 调整颜色 {target: "元素名", changes: {{color: [r,g,b]}}}
- change_layout: 更换布局 {changes: {{layout_type: 新布局类型}}}
- reduce_spacing: 减小间距
- increase_spacing: 增加间距
- hide_optional_element: 隐藏可选元素

## 输出要求
请输出JSON格式的修订计划：
{{
    "operations": [
        {{
            "op": "操作类型",
            "target": "目标元素名",
            "changes": {{...}}
        }}
    ],
    "reason": "修订原因说明",
    "expected_improvement": "预期改进效果"
}}

请直接输出JSON，不要其他文字。
"""
