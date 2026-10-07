"""Bounded, content-free call telemetry. No prompts, responses or keys are logged."""

import logging
import uuid
from datetime import datetime, timezone
import threading
from collections import deque
from contextvars import ContextVar
from time import perf_counter

project_context = ContextVar("llm_project", default=None)
_records = deque(maxlen=2000)
_lock = threading.Lock()
logger = logging.getLogger("pptmaker.llm")


def record_call(**record):
    record.setdefault("call_id", uuid.uuid4().hex)
    record["created_at"] = datetime.now(timezone.utc).isoformat()
    record["project_id"] = project_context.get()
    with _lock:
        _records.append(record)
    logger.info("LLM %s", record)
    from ..storage.account_repository import account_repository
    account_repository().record_usage(record)


def usage_snapshot(project_id=None):
    with _lock:
        records = [dict(r) for r in _records if project_id is None or r["project_id"] == project_id]
    total = lambda key: sum(r.get(key, 0) or 0 for r in records)
    input_tokens = total("input_tokens")
    return {
        "window": "last_2000_calls_since_process_start",
        "calls": len(records), "input_tokens": input_tokens,
        "output_tokens": total("output_tokens"), "cached_input_tokens": total("cached_input_tokens"),
        "reasoning_tokens": total("reasoning_tokens"),
        "provider_cache_hit_rate": total("cached_input_tokens") / input_tokens if input_tokens else None,
        "response_cache_hits": sum(bool(r.get("response_cache_hit")) for r in records),
        "usage_reported_calls": sum(bool(r.get("usage_reported")) for r in records),
        "duration_ms": total("duration_ms"), "recent_calls": records[-100:],
    }


def run_project_step(function, state, project_id):
    """Run in asyncio.to_thread; scope telemetry to this project without leaking context."""
    token = project_context.set(project_id)
    started = perf_counter()
    try:
        return function(state)
    finally:
        logger.info("stage project=%s node=%s duration_ms=%.1f", project_id,
                    getattr(function, "__name__", type(function).__name__), (perf_counter() - started) * 1000)
        project_context.reset(token)
