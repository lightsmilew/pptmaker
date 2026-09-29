"""Tests for models/iteration.py."""

import pytest
from datetime import datetime, timedelta

from app.models.iteration import (
    IterationRecord,
    IterationState,
    IterationHistory,
    LayoutChange,
)


class TestLayoutChange:
    """Tests for LayoutChange."""

    def test_create(self):
        """Create layout change."""
        change = LayoutChange(
            change_type="resize",
            target="content",
            before={"w": 10, "h": 5},
            after={"w": 11, "h": 5},
        )
        assert change.change_type == "resize"
        assert change.target == "content"
        assert change.before["w"] == 10


class TestIterationRecord:
    """Tests for IterationRecord."""

    def test_create_minimal(self):
        """Create with minimal fields."""
        record = IterationRecord(iteration=1, page_id="page-01")
        assert record.iteration == 1
        assert record.page_id == "page-01"
        assert record.state == IterationState.PENDING

    def test_duration_not_finished(self):
        """Duration is None when not finished."""
        record = IterationRecord(iteration=1, page_id="page-01")
        assert record.duration_seconds() is None

    def test_duration_finished(self):
        """Calculate duration when finished."""
        start = datetime.now()
        end = start + timedelta(seconds=5)
        record = IterationRecord(
            iteration=1,
            page_id="page-01",
            started_at=start,
            finished_at=end,
        )
        assert record.duration_seconds() == 5.0

    def test_is_improvement(self):
        """Test improvement detection."""
        record = IterationRecord(
            iteration=2,
            page_id="page-01",
            critic_result={"score": 85},
        )
        assert record.is_improvement(80) is True
        assert record.is_improvement(90) is False
        assert record.is_improvement(None) is False

    def test_has_same_issues(self):
        """Test same issues detection."""
        record = IterationRecord(
            iteration=2,
            page_id="page-01",
            critic_result={
                "issues": [
                    {"description": "overflow"},
                    {"description": "alignment"},
                ]
            },
        )
        assert record.has_same_issues(["alignment", "overflow"]) is True
        assert record.has_same_issues(["alignment"]) is False


class TestIterationHistory:
    """Tests for IterationHistory."""

    def test_create(self):
        """Create empty history."""
        history = IterationHistory(page_id="page-01")
        assert history.page_id == "page-01"
        assert history.records == []

    def test_add_record(self):
        """Add records."""
        history = IterationHistory(page_id="page-01")
        record1 = IterationRecord(iteration=1, page_id="page-01")
        record2 = IterationRecord(iteration=2, page_id="page-01")

        history.add_record(record1)
        history.add_record(record2)

        assert len(history.records) == 2

    def test_get_latest(self):
        """Get latest record."""
        history = IterationHistory(page_id="page-01")
        history.add_record(IterationRecord(iteration=1, page_id="page-01"))
        history.add_record(IterationRecord(iteration=2, page_id="page-01"))

        latest = history.get_latest()
        assert latest.iteration == 2

    def test_get_latest_empty(self):
        """Get latest when empty returns None."""
        history = IterationHistory(page_id="page-01")
        assert history.get_latest() is None

    def test_get_best_iteration(self):
        """Get iteration with highest score."""
        history = IterationHistory(page_id="page-01")
        history.add_record(IterationRecord(
            iteration=1, page_id="page-01",
            critic_result={"score": 70}
        ))
        history.add_record(IterationRecord(
            iteration=2, page_id="page-01",
            critic_result={"score": 85}
        ))
        history.add_record(IterationRecord(
            iteration=3, page_id="page-01",
            critic_result={"score": 80}
        ))

        best = history.get_best_iteration()
        assert best.iteration == 2

    def test_should_stop_max_iterations(self):
        """Stop when max iterations reached."""
        history = IterationHistory(page_id="page-01")
        for i in range(1, 5):
            history.add_record(IterationRecord(
                iteration=i, page_id="page-01",
                critic_result={"score": 70 + i}
            ))

        should_stop, reason = history.should_stop(max_iterations=4)
        assert should_stop is True
        assert "最大迭代" in reason

    def test_should_stop_no_improvement(self):
        """Stop when no improvement."""
        history = IterationHistory(page_id="page-01")
        history.add_record(IterationRecord(
            iteration=1, page_id="page-01",
            critic_result={"score": 70, "issues": [{"description": "i1"}]}
        ))
        history.add_record(IterationRecord(
            iteration=2, page_id="page-01",
            critic_result={"score": 70, "issues": [{"description": "i1"}]}
        ))

        should_stop, reason = history.should_stop()
        assert should_stop is True

    def test_should_continue(self):
        """Continue when still improving."""
        history = IterationHistory(page_id="page-01")
        history.add_record(IterationRecord(
            iteration=1, page_id="page-01",
            critic_result={"score": 70, "issues": [{"description": "i1"}]}
        ))
        history.add_record(IterationRecord(
            iteration=2, page_id="page-01",
            critic_result={"score": 85, "issues": []}
        ))

        should_stop, _ = history.should_stop()
        assert should_stop is False
