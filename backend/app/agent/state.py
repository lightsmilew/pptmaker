"""Unified Agent state definition for PPTMaker."""

from typing import Any, Dict, List, Optional, TypedDict

from ..models.project import ProjectState, WorkflowState
from ..models.page import PageState
from ..models.review import GlobalReviewResult, AgentError


class AgentState(TypedDict):
    """
    Unified state for the PPTMaker Agent.

    Structure:
    - project: Project-level information
    - workflow: Workflow execution state
    - pages: Dict of page_id -> PageState
    - current_page_id: Current page being processed
    - global_review: Global review result
    - errors: List of errors encountered
    """

    # Project level
    project: ProjectState
    user_input: str
    uploaded_files: List[Dict[str, Any]]

    # Workflow
    workflow: WorkflowState

    # Pages - dict for O(1) access
    pages: Dict[str, PageState]
    current_page_id: Optional[str]
    outline: List[Dict[str, Any]]

    # Global review
    global_review: Optional[GlobalReviewResult]

    # Error tracking
    errors: List[AgentError]

    # Retry counters (per-category)
    content_retry_count: int
    layout_retry_count: int
    critic_iteration: int
    json_retry_count: int

    # Output
    output_pptx_path: Optional[str]


def create_initial_state(
    project_id: str,
    spec: Dict[str, Any],
    user_input: str = "",
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
    page_count: Optional[int] = None,
) -> AgentState:
    """Create initial agent state."""
    if page_count is None:
        page_count = spec.get("page_count", 8) if isinstance(spec, dict) else 8

    return AgentState(
        project=ProjectState(
            project_id=project_id,
            spec=spec,
            page_count=page_count,
        ),
        user_input=user_input,
        uploaded_files=uploaded_files or [],
        workflow=WorkflowState(
            workflow_id=f"wf-{project_id}",
            total_pages=page_count,
        ),
        pages={},
        current_page_id=None,
        outline=[],
        global_review=None,
        errors=[],
        content_retry_count=0,
        layout_retry_count=0,
        critic_iteration=0,
        json_retry_count=0,
        output_pptx_path=None,
    )


def state_to_project(state: AgentState) -> Dict[str, Any]:
    """Convert agent state to a JSON-safe project dict."""
    project_obj = state["project"]
    if hasattr(project_obj, "status") and hasattr(project_obj.status, "value"):
        status_value = project_obj.status.value
    else:
        status_value = str(getattr(project_obj, "status", "idle"))

    workflow_obj = state.get("workflow")
    workflow_dump = (
        workflow_obj.model_dump() if workflow_obj is not None
        and hasattr(workflow_obj, "model_dump") else {}
    )

    errors = state.get("errors") or []
    last_error = errors[-1].message if errors else None

    global_review = state.get("global_review")
    if global_review is not None and hasattr(global_review, "model_dump"):
        global_review = global_review.model_dump()

    pages_obj = state.get("pages") or {}
    pages_list = [
        page.to_dict() if hasattr(page, "to_dict") else page
        for page in pages_obj.values()
    ]

    project_id = getattr(project_obj, "project_id", "")
    spec = getattr(project_obj, "spec", {})
    created_at = getattr(project_obj, "created_at", None)
    updated_at = getattr(project_obj, "updated_at", None)

    return {
        "id": project_id,
        "spec": spec,
        "user_input": state.get("user_input", ""),
        "uploaded_files": state.get("uploaded_files", []),
        "status": status_value,
        "current_step": (workflow_obj.current_node if workflow_obj is not None and hasattr(workflow_obj, "current_node") else "") or "",
        "progress": _compute_progress(state),
        "error": last_error,
        "pages": pages_list,
        "outline": state.get("outline", []),
        "global_review": global_review,
        "workflow": workflow_dump,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def _compute_progress(state: AgentState) -> float:
    """Compute overall project progress as a 0-100 percentage."""
    pages = state.get("pages") or {}
    total = state["workflow"].total_pages or len(pages) or 1
    completed = sum(
        1 for p in pages.values()
        if p.status.value in ("completed", "failed")
    )
    return round((completed / total) * 100, 1)


def get_current_page(state: AgentState) -> Optional[PageState]:
    """Get the page currently being processed, if any."""
    if state["current_page_id"]:
        return state["pages"].get(state["current_page_id"])
    return None


def get_next_pending_page(state: AgentState) -> Optional[str]:
    """Get the next page ID that still needs work."""
    for page_id, page in state["pages"].items():
        if page.status.value in ("pending", "failed"):
            return page_id
    return None


def get_completed_pages(state: AgentState) -> List[str]:
    """Return all completed page IDs."""
    return [
        page_id for page_id, page in state["pages"].items()
        if page.status.value == "completed"
    ]


def all_pages_completed(state: AgentState) -> bool:
    """Return True if every page has been completed."""
    if not state["pages"]:
        return False
    return all(
        page.status.value == "completed"
        for page in state["pages"].values()
    )


def reset_retry_counters(state: AgentState) -> None:
    """Reset all retry counters (used between pages)."""
    state["content_retry_count"] = 0
    state["layout_retry_count"] = 0
    state["critic_iteration"] = 0
    state["json_retry_count"] = 0


def increment_critic_iteration(state: AgentState) -> None:
    """Increment the critic iteration counter for the current page."""
    state["critic_iteration"] += 1
    page = get_current_page(state)
    if page:
        page.iteration = state["critic_iteration"]
