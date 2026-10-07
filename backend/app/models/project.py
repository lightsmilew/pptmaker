"""Project state model."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    """Project status enumeration."""

    IDLE = "idle"
    PARSING = "parsing"
    PARSED = "parsed"
    EDITING = "editing"
    PLANNING = "planning"
    PLANNED = "planned"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectState(BaseModel):
    """Project-level state."""

    project_id: str
    spec: Dict[str, Any] = Field(default_factory=dict)
    theme: Dict[str, Any] = Field(default_factory=dict)
    page_count: int = 8
    status: ProjectStatus = ProjectStatus.IDLE
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class WorkflowState(BaseModel):
    """Workflow execution state."""

    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.IDLE
    current_node: Optional[str] = None
    current_page_id: Optional[str] = None
    total_pages: int = 0
    completed_pages: List[str] = Field(default_factory=list)
    failed_pages: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)

    def progress_percentage(self) -> float:
        if self.total_pages == 0:
            return 0.0
        return (len(self.completed_pages) / self.total_pages) * 100

    def add_completed_page(self, page_id: str) -> None:
        if page_id not in self.completed_pages:
            self.completed_pages.append(page_id)

    def add_failed_page(self, page_id: str, error: str) -> None:
        if page_id not in self.failed_pages:
            self.failed_pages.append(page_id)
            self.errors.append({"page_id": page_id, "error": error})
