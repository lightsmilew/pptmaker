"""Iteration tracking model."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IterationState(str, Enum):
    """Iteration state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LayoutChange(BaseModel):
    """Record of a single layout change."""

    change_type: str  # move, resize, change_font_size, etc.
    target: str  # Element name
    before: Dict[str, Any]
    after: Dict[str, Any]


class IterationRecord(BaseModel):
    """
    Record of a single iteration for a page.

    This enables:
    - Debugging: trace what happened in each iteration
    - Rollback: revert to previous state if needed
    - Comparison: compare before/after images
    - Analysis: understand why LLM makes certain decisions
    """

    iteration: int
    page_id: str

    # Input state
    input_layout_id: Optional[str] = None
    input_content_hash: Optional[str] = None

    # Rendering
    preview_path: Optional[str] = None
    render_time_ms: Optional[float] = None

    # Review
    critic_result: Optional[Dict[str, Any]] = None

    # Revision
    revision_operations: List[LayoutChange] = Field(default_factory=list)

    # Output state
    output_layout_id: Optional[str] = None
    output_content_hash: Optional[str] = None

    # Metadata
    state: IterationState = IterationState.PENDING
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

    def duration_seconds(self) -> Optional[float]:
        """Calculate iteration duration in seconds."""
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def is_improvement(self, previous_score: Optional[float]) -> bool:
        """Check if this iteration improved the score."""
        if not previous_score or not self.critic_result:
            return False
        current_score = self.critic_result.get("score", 0)
        return current_score > previous_score

    def has_same_issues(self, previous_issues: List[str]) -> bool:
        """Check if this iteration has the same issues as before."""
        if not self.critic_result:
            return False
        current_issues = [
            issue.get("description", "")
            for issue in self.critic_result.get("issues", [])
        ]
        return set(current_issues) == set(previous_issues)


class IterationHistory(BaseModel):
    """History of all iterations for a page."""

    page_id: str
    records: List[IterationRecord] = Field(default_factory=list)

    def add_record(self, record: IterationRecord) -> None:
        """Add a new iteration record."""
        self.records.append(record)

    def get_latest(self) -> Optional[IterationRecord]:
        """Get the latest iteration record."""
        if self.records:
            return self.records[-1]
        return None

    def get_best_iteration(self) -> Optional[IterationRecord]:
        """Get the iteration with the highest score."""
        best = None
        best_score = 0
        for record in self.records:
            if record.critic_result:
                score = record.critic_result.get("score", 0)
                if score > best_score:
                    best_score = score
                    best = record
        return best

    def should_stop(self, max_iterations: int = 4) -> tuple:
        """
        Determine if iterations should stop.

        Returns:
            (should_stop: bool, reason: str)
        """
        if len(self.records) >= max_iterations:
            return True, f"达到最大迭代次数({max_iterations})"

        if len(self.records) >= 2:
            last = self.records[-1]
            prev = self.records[-2]

            # Check if score didn't improve
            if last.critic_result and prev.critic_result:
                last_score = last.critic_result.get("score", 0)
                prev_score = prev.critic_result.get("score", 0)
                if last_score <= prev_score:
                    return True, "连续迭代评分未提升"

            # Check if same issues persist
            if last.has_same_issues([
                issue.get("description", "")
                for issue in prev.critic_result.get("issues", [])
            ] if prev.critic_result else []):
                return True, "连续迭代出现相同问题"

        return False, ""
