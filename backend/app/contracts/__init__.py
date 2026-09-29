"""Contracts module - unified JSON handling and validation."""

from .json_utils import parse_llm_json, extract_json_from_text, JSONParseError
from .errors import (
    ContractError,
    ValidationError,
    SchemaValidationError,
    SemanticValidationError,
    JSONValidationError,
)
from .schemas import (
    PageContent,
    LayoutSpec,
    PlaceholderSpec,
    ReviewResult,
    RevisionPlan,
    RevisionOperation,
    ReviewIssue,
    ProjectSpec,
    OutlineItem,
)
from .validators import (
    validate_page_content,
    validate_layout_spec,
    validate_review_result,
    validate_revision_plan,
)
from .structured_llm import StructuredLLMCaller, LLMCallResult

__all__ = [
    # JSON utilities
    "parse_llm_json",
    "extract_json_from_text",
    "JSONParseError",
    # Errors
    "ContractError",
    "ValidationError",
    "SchemaValidationError",
    "SemanticValidationError",
    "JSONValidationError",
    # Schemas
    "PageContent",
    "LayoutSpec",
    "PlaceholderSpec",
    "ReviewResult",
    "RevisionPlan",
    "RevisionOperation",
    "ReviewIssue",
    "ProjectSpec",
    "OutlineItem",
    # Validators
    "validate_page_content",
    "validate_layout_spec",
    "validate_review_result",
    "validate_revision_plan",
    # Structured LLM
    "StructuredLLMCaller",
    "LLMCallResult",
]
