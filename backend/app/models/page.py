"""Page state model."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .iteration import IterationRecord


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


class PreviewInfo(BaseModel):
    """Preview image information."""

    image_path: str
    width: int = 1600
    height: int = 900
    rendered_at: datetime = Field(default_factory=datetime.now)


class PageState(BaseModel):
    """Complete page state including content, layout, preview, and review history."""

    page_id: str
    page_type: PageType = PageType.CONTENT

    # Content
    title: str = ""
    subtitle: str = ""
    key_points: List[str] = Field(default_factory=list)
    bullet_points: List[str] = Field(default_factory=list)
    chart_data: Optional[Dict[str, Any]] = None
    table_data: Optional[Dict[str, Any]] = None
    speaker_notes: str = ""

    # Layout
    layout_type: str = "title_content"
    layout_json: Optional[Dict[str, Any]] = None
    master_json: Optional[Dict[str, Any]] = None

    # Preview
    preview: Optional[PreviewInfo] = None

    # Review
    review_status: Optional[str] = None
    review_score: Optional[float] = None
    review_issues: List[Dict[str, Any]] = Field(default_factory=list)
    review_suggestions: List[str] = Field(default_factory=list)

    # Iteration
    iteration: int = 1
    max_iterations: int = 4

    # Status
    status: PageStatus = PageStatus.PENDING
    error: Optional[str] = None

    # History
    iterations: List[IterationRecord] = Field(default_factory=list)

    def is_approved(self) -> bool:
        return self.review_status == "approved"

    def needs_revision(self) -> bool:
        return self.review_status == "needs_revision"

    def is_completed(self) -> bool:
        return self.status == PageStatus.COMPLETED

    def can_retry(self) -> bool:
        return self.iteration < self.max_iterations and self.status != PageStatus.COMPLETED

    def increment_iteration(self) -> None:
        self.iteration += 1

    def mark_completed(self) -> None:
        self.status = PageStatus.COMPLETED
        self.review_status = "approved"

    def mark_failed(self, error: str) -> None:
        self.status = PageStatus.FAILED
        self.error = error

    def get_latest_layout_id(self) -> Optional[str]:
        if self.iterations:
            return self.iterations[-1].output_layout_id
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_id": self.page_id,
            "page_type": self.page_type.value,
            "content": {
                "title": self.title,
                "subtitle": self.subtitle,
                "key_points": self.key_points,
                "bullet_points": self.bullet_points,
                "chart_data": self.chart_data,
                "table_data": self.table_data,
                "speaker_notes": self.speaker_notes,
            },
            "layout": {
                "layout_type": self.layout_type,
                "layout_json": self.layout_json,
                "master_json": self.master_json,
            },
            "preview": self.preview.model_dump() if self.preview else None,
            "review": {
                "status": self.review_status,
                "score": self.review_score,
                "issues": self.review_issues,
                "suggestions": self.review_suggestions,
            },
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "status": self.status.value,
            "error": self.error,
        }
