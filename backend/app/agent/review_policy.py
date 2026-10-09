"""Separate review advice from failures to produce a usable page."""

import os
from ..models.page import PageStatus


def repair_limit():
    """The setting counts adjustments, not the initial review."""
    return max(1, min(4, int(os.getenv("PPT_MAX_REVIEW_ROUNDS", "2"))))


def has_page_artifacts(page):
    return bool(page.preview and page.layout_json and
                (page.title or page.key_points or page.bullet_points or page.chart_data or page.table_data))


def can_finalize(page):
    return page.status != PageStatus.FAILED and (
        page.review_status == "approved" or
        (page.review_status in {"needs_revision", "blocked", "failed"} and has_page_artifacts(page)))
