"""Review and error models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentError(BaseModel):
    """Agent error record."""

    error_id: str
    node: str  # Which node raised the error
    message: str
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    resolved: bool = False
    resolution: Optional[str] = None


class ReviewStatus(str, Enum):
    """Review status."""

    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    BLOCKED = "blocked"
    FAILED = "failed"


class IssueSeverity(str, Enum):
    """Issue severity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueCategory(str, Enum):
    """Issue category."""

    ALIGNMENT = "alignment"
    WHITESPACE = "whitespace"
    DENSITY = "density"
    HIERARCHY = "hierarchy"
    FONT_SIZE = "font_size"
    CONTRAST = "contrast"
    OVERFLOW = "overflow"
    OVERLAP = "overlap"
    BALANCE = "balance"
    CONSISTENCY = "consistency"
    CONTENT = "content"
    LAYOUT = "layout"


class IssueOwner(str, Enum):
    """Who should handle the issue."""

    LAYOUT = "layout"
    CONTENT = "content"


class ReviewIssue(BaseModel):
    """Individual review issue."""

    issue_id: str
    category: IssueCategory
    severity: IssueSeverity
    target: str = ""
    description: str
    suggested_action: Optional[str] = None
    owner: IssueOwner = IssueOwner.LAYOUT


class ReviewDimensions(BaseModel):
    """Review scoring dimensions."""

    alignment: int = Field(ge=0, le=10, default=5)
    balance: int = Field(ge=0, le=10, default=5)
    readability: int = Field(ge=0, le=10, default=5)
    hierarchy: int = Field(ge=0, le=10, default=5)
    density: int = Field(ge=0, le=10, default=5)
    consistency: int = Field(ge=0, le=10, default=5)

    def overall_score(self) -> float:
        """Calculate overall score."""
        total = (
            self.alignment
            + self.balance
            + self.readability
            + self.hierarchy
            + self.density
            + self.consistency
        )
        return (total / 6) * 10  # Scale to 100


class GlobalReviewResult(BaseModel):
    """Global review result across all pages."""

    status: ReviewStatus
    score: float = Field(ge=0, le=100)
    page_scores: Dict[str, float] = Field(default_factory=dict)
    consistency_issues: List[ReviewIssue] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    affected_pages: List[str] = Field(default_factory=list)

    def has_critical_issues(self) -> bool:
        """Check if there are critical consistency issues."""
        return any(
            issue.severity == IssueSeverity.CRITICAL
            for issue in self.consistency_issues
        )


class PageReviewInput(BaseModel):
    """Input for page review."""

    page_id: str
    image_path: str
    page_data: Dict[str, Any]
    canvas_info: Dict[str, Any] = Field(default_factory=lambda: {
        "width": 1600,
        "height": 900,
        "aspect_ratio": "16:9"
    })
    design_rules: Dict[str, Any] = Field(default_factory=lambda: {
        "min_body_font_size": 14,
        "max_text_density": 0.65,
        "safe_margin": 40
    })
    previous_review: Optional[Dict[str, Any]] = None
    iteration: int = 1


class GlobalReviewInput(BaseModel):
    """Input for global review."""

    project_id: str
    page_summaries: List[Dict[str, Any]]
    thumbnail_paths: List[str]
    theme_info: Dict[str, Any]
    page_order: List[str]
