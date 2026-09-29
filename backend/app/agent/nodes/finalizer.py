"""Finalizer node - marks page as complete and moves to next."""

from typing import Any, Dict, List, Optional

from ...models.page import PageStatus
from ..state import AgentState
from ..state import (
    get_next_pending_page,
    get_completed_pages,
    all_pages_completed,
)


def finalizer_node(state: AgentState) -> AgentState:
    """
    Finalize current page and determine next action.

    This node:
    - Marks current page as completed if approved
    - Updates workflow state
    - Determines if we should proceed to next page or finish
    """
    page_id = state.get("current_page_id")
    if not page_id:
        return state

    page = state["pages"].get(page_id)
    if not page:
        return state

    state["workflow"].current_node = "finalizer"

    # Check if page is approved
    if page.review_status == "approved":
        page.status = PageStatus.COMPLETED
        state["pages"][page_id] = page
        state["workflow"].add_completed_page(page_id)

        # Reset iteration counter for next page
        state["critic_iteration"] = 0

    # Find next page to process
    next_page_id = get_next_pending_page(state)

    if next_page_id:
        # Move to next page
        state["current_page_id"] = next_page_id
    else:
        # All pages processed
        state["current_page_id"] = None

    return state


def finalize_page(page_id: str, state: AgentState) -> Dict[str, Any]:
    """
    Standalone function to finalize a page.

    Args:
        page_id: Page to finalize
        state: Current agent state

    Returns:
        Result dict with next page info
    """
    page = state["pages"].get(page_id)
    if not page:
        return {"error": "Page not found"}

    if page.review_status == "approved":
        page.status = PageStatus.COMPLETED
        state["pages"][page_id] = page
        state["workflow"].add_completed_page(page_id)

    # Determine next page
    next_page_id = get_next_pending_page(state)

    return {
        "page_id": page_id,
        "status": "completed",
        "next_page_id": next_page_id,
        "all_completed": all_pages_completed(state),
    }
