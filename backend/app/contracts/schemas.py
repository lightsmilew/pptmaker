"""Pydantic schemas for contract validation."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Preview Info (re-exported for compatibility)
class PreviewInfo(BaseModel):
    """Preview image information."""

    image_path: str
    width: int = 1600
    height: int = 900
    rendered_at: datetime = Field(default_factory=datetime.now)


# Enums
class ReviewStatus(str, Enum):
    """Review status enumeration."""

    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    BLOCKED = "blocked"
    FAILED = "failed"


class IssueSeverity(str, Enum):
    """Issue severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueCategory(str, Enum):
    """Issue categories for classification."""

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


class RevisionOperationType(str, Enum):
    """Types of revision operations."""

    MOVE = "move"
    RESIZE = "resize"
    CHANGE_FONT_SIZE = "change_font_size"
    CHANGE_FONT = "change_font"
    CHANGE_COLOR = "change_color"
    CHANGE_LAYOUT = "change_layout"
    SPLIT_CONTENT = "split_content"
    MERGE_CONTENT = "merge_content"
    REDUCE_SPACING = "reduce_spacing"
    INCREASE_SPACING = "increase_spacing"
    HIDE_OPTIONAL_ELEMENT = "hide_optional_element"


class PageStatus(str, Enum):
    """Page generation status."""

    PENDING = "pending"
    WRITING = "writing"
    DESIGNING = "designing"
    RENDERING = "rendering"
    REVIEWING = "reviewing"
    REVISING = "revising"
    COMPLETED = "completed"
    FAILED = "failed"


class PageType(str, Enum):
    """Page type enumeration."""

    COVER = "cover"
    TOC = "toc"
    CONTENT = "content"
    CHART = "chart"
    TABLE = "table"
    CONCLUSION = "conclusion"
    REFERENCE = "reference"
    THANKYOU = "thankyou"


class LayoutType(str, Enum):
    """Layout type enumeration."""

    TITLE_CONTENT = "title_content"
    TWO_COLUMN = "two_column"
    THREE_COLUMN = "three_column"
    IMAGE_TEXT = "image_text"
    CHART_CONTENT = "chart_content"
    TIMELINE = "timeline"
    STEPS = "steps"
    COMPARISON = "comparison"
    TOC = "toc"
    COVER = "cover"
    CONCLUSION = "conclusion"
    MINIMAL = "minimal"
    LEFT_RAIL = "left_rail"
    STACKED_ROWS = "stacked_rows"
    CARDS_GRID = "cards_grid"
    STATEMENT = "statement"


# Basic Schemas
class RGBColor(BaseModel):
    """RGB color representation."""

    rgb: List[int] = Field(default_factory=lambda: [0, 0, 0])

    @field_validator("rgb")
    @classmethod
    def validate_rgb(cls, v: List[int]) -> List[int]:
        if len(v) != 3:
            raise ValueError("RGB must have 3 values")
        for val in v:
            if not 0 <= val <= 255:
                raise ValueError("RGB values must be 0-255")
        return v


class FontScheme(BaseModel):
    """Font scheme configuration."""

    title_font: str = "Microsoft YaHei"
    body_font: str = "Microsoft YaHei"
    title_size: int = 32
    body_size: int = 16


class ColorScheme(BaseModel):
    """Color scheme configuration."""

    primary: List[int] = Field(default_factory=lambda: [30, 58, 138])
    secondary: List[int] = Field(default_factory=lambda: [59, 130, 246])
    accent: List[int] = Field(default_factory=lambda: [99, 102, 241])
    text: List[int] = Field(default_factory=lambda: [30, 41, 59])
    light_text: List[int] = Field(default_factory=lambda: [255, 255, 255])


class BackgroundConfig(BaseModel):
    """Background configuration."""

    type: str = "solid"
    rgb: List[int] = Field(default_factory=lambda: [255, 255, 255])


class LogoConfig(BaseModel):
    """Logo configuration."""

    enable: bool = False


class MasterLayout(BaseModel):
    """Master slide layout configuration."""

    background: BackgroundConfig = Field(default_factory=BackgroundConfig)
    logo: LogoConfig = Field(default_factory=LogoConfig)
    color_scheme: ColorScheme = Field(default_factory=ColorScheme)
    font_scheme: FontScheme = Field(default_factory=FontScheme)


# Placeholder Schema
class PlaceholderSpec(BaseModel):
    """Placeholder specification for layout."""

    name: str
    type: Literal["title", "subtitle", "text", "chart", "table", "accent", "caption", "toc"]
    x: float = Field(ge=0, le=13.333)
    y: float = Field(ge=0, le=7.5)
    w: float = Field(gt=0, le=13.333)
    h: float = Field(gt=0, le=7.5)

    @field_validator("x", "y", "w", "h")
    @classmethod
    def validate_dimensions(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Dimensions cannot be negative")
        return v


# Layout Schema
class LayoutSpec(BaseModel):
    """Complete layout specification."""

    layout_id: str
    layout_type: LayoutType
    placeholders: List[PlaceholderSpec]

    def get_placeholder(self, name: str) -> Optional[PlaceholderSpec]:
        """Get placeholder by name."""
        for p in self.placeholders:
            if p.name == name:
                return p
        return None


# Content Schema
class PageContent(BaseModel):
    """Page content specification."""

    title: str = ""
    subtitle: str = ""
    key_points: List[str] = Field(default_factory=list)
    bullet_points: List[str] = Field(default_factory=list)
    chart_data: Optional[Dict[str, Any]] = None
    table_data: Optional[Dict[str, Any]] = None
    speaker_notes: str = ""

    @field_validator("key_points", "bullet_points")
    @classmethod
    def validate_lists(cls, v: List[str]) -> List[str]:
        return [str(item).strip() for item in v if item]


# Review Schemas
class ReviewIssue(BaseModel):
    """Individual review issue."""

    issue_id: str
    category: IssueCategory
    severity: IssueSeverity
    target: str = ""  # Element name or "global"
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
        return (self.alignment + self.balance + self.readability +
                self.hierarchy + self.density + self.consistency) / 6


class ReviewResult(BaseModel):
    """Complete review result."""

    status: ReviewStatus
    score: float = Field(ge=0, le=100, default=0)
    dimensions: ReviewDimensions = Field(default_factory=ReviewDimensions)
    issues: List[ReviewIssue] = Field(default_factory=list)
    next_action: Literal["revise_layout", "revise_content", "approve", "blocked", "failed"] = "approve"

    def has_high_severity_issues(self) -> bool:
        """Check if there are high severity issues."""
        return any(issue.severity in (IssueSeverity.HIGH, IssueSeverity.CRITICAL)
                   for issue in self.issues)

    def has_overflow_or_overlap(self) -> bool:
        """Check for overflow or overlap issues."""
        overflow_categories = {IssueCategory.OVERFLOW, IssueCategory.OVERLAP}
        return any(issue.category in overflow_categories for issue in self.issues)

    def get_layout_issues(self) -> List[ReviewIssue]:
        """Get layout-related issues."""
        return [issue for issue in self.issues if issue.owner == IssueOwner.LAYOUT]

    def get_content_issues(self) -> List[ReviewIssue]:
        """Get content-related issues."""
        return [issue for issue in self.issues if issue.owner == IssueOwner.CONTENT]


# Revision Schemas
class RevisionOperation(BaseModel):
    """Single revision operation."""

    op: RevisionOperationType
    target: str  # Element name
    changes: Dict[str, Any] = Field(default_factory=dict)


class RevisionPlan(BaseModel):
    """Complete revision plan."""

    operations: List[RevisionOperation] = Field(default_factory=list)
    reason: str = ""
    expected_improvement: Optional[str] = None


# Project Schemas
class ProjectSpec(BaseModel):
    """Project specification."""

    topic: str = ""
    audience: str = "通用受众"
    page_count: int = Field(ge=1, le=50, default=8)
    style: str = "简约专业"
    needs_cover: bool = True
    needs_toc: bool = True
    needs_summary: bool = True
    needs_chart: bool = False
    notes: str = ""


class OutlineItem(BaseModel):
    """Single outline item for a page."""

    page_id: str
    page_type: PageType
    page_title: str
    subtitle: str = ""
    page_purpose: str = ""
    key_points: List[str] = Field(default_factory=list)
    suggest_layout: str = "标题正文"


# Page State Schema
class PageState(BaseModel):
    """Complete page state."""

    page_id: str
    page_type: PageType
    content: PageContent = Field(default_factory=PageContent)
    layout: Optional[LayoutSpec] = None
    master: MasterLayout = Field(default_factory=MasterLayout)
    preview: Optional[Dict[str, Any]] = None  # {"image_path": str, "width": int, "height": int, "rendered_at": str}
    review: Optional[ReviewResult] = None
    iteration: int = 1
    status: PageStatus = PageStatus.PENDING


# Iteration Record
class IterationRecord(BaseModel):
    """Record of a single iteration for a page."""

    iteration: int
    page_id: str
    input_layout_id: Optional[str] = None
    preview_path: Optional[str] = None
    critic_result: Optional[Dict[str, Any]] = None
    revision_operations: List[RevisionOperation] = Field(default_factory=list)
    output_layout_id: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None

    def duration_seconds(self) -> Optional[float]:
        """Calculate iteration duration."""
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


# Design Rules
class DesignRules(BaseModel):
    """Design rules for critic."""

    min_body_font_size: int = 14
    max_text_density: float = 0.65  # Max 65% of canvas filled
    safe_margin: float = 40  # pixels
    min_contrast_ratio: float = 3.0


# Canvas Info
class CanvasInfo(BaseModel):
    """Canvas information for critic."""

    width: int = 1600
    height: int = 900
    aspect_ratio: str = "16:9"


# Critic Input
class CriticInput(BaseModel):
    """Input for image critic."""

    page_id: str
    page_type: PageType
    title: str
    content_summary: str
    layout_type: str
    canvas: CanvasInfo = Field(default_factory=CanvasInfo)
    design_rules: DesignRules = Field(default_factory=DesignRules)
    previous_review: Optional[ReviewResult] = None
    iteration: int = 1
