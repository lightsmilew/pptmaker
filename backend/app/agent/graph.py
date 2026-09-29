"""LangGraph workflow for parallel PPT page generation."""

import os
from typing import Literal, Dict, Any, List, Optional
from langgraph.graph import StateGraph, END

from . import nodes as _nodes
from .state import (
    AgentState,
    get_next_pending_page,
    all_pages_completed,
)
from ..tools.pptx_generator import PPTXGenerator


def create_ppt_agent_graph() -> StateGraph:
    """
    Create the PPT generation workflow graph.

    Flow:
    START -> parse_input -> plan_outline -> prepare_pages
                                            |
                                            v
                       write -> design -> render -> critic -> route
                                                              |
                                  +-----------+-----------+---+
                                  |           |           |   |
                              revise_    revise_    approve blocked/failed
                              layout    content               |
                                  |           |               |
                                  +---loop----+               v
                                                     finalize_page
                                                              |
                                                       next_page or global_review
                                                              v
                                                       global_review
                                                              v
                                                       render_pptx -> END
    """
    graph = StateGraph(AgentState)

    # Core nodes
    graph.add_node("parse_input", parse_input_node)
    graph.add_node("plan_outline", plan_outline_node)
    graph.add_node("prepare_pages", prepare_pages_node)

    # Page processing
    graph.add_node("write_page", write_page_node)
    graph.add_node("design_layout", design_layout_node)
    graph.add_node("render_preview", render_preview_node)
    graph.add_node("critic_review", critic_review_node)

    # Revision
    graph.add_node("revise_layout", revise_layout_node)
    graph.add_node("revise_content", revise_content_node)

    # Finalization
    graph.add_node("finalize_page", finalize_page_node)
    graph.add_node("global_review", global_review_node)

    # Output
    graph.add_node("render_pptx", render_pptx_node)
    graph.add_node("handle_error", handle_error_node)

    # Entry point
    graph.set_entry_point("parse_input")

    # Main flow
    graph.add_edge("parse_input", "plan_outline")
    graph.add_edge("plan_outline", "prepare_pages")

    # Per-page pipeline
    graph.add_edge("prepare_pages", "write_page")
    graph.add_edge("write_page", "design_layout")
    graph.add_edge("design_layout", "render_preview")
    graph.add_edge("render_preview", "critic_review")

    # Review routing
    graph.add_conditional_edges(
        "critic_review",
        route_page_review,
        {
            "revise_layout": "revise_layout",
            "revise_content": "revise_content",
            "approve": "finalize_page",
            "blocked": "handle_error",
            "failed": "handle_error",
        },
    )

    # Revision loops
    graph.add_edge("revise_layout", "design_layout")
    graph.add_edge("revise_content", "write_page")

    # After finalization, decide next page or global review
    graph.add_conditional_edges(
        "finalize_page",
        route_after_finalize,
        {
            "next_page": "write_page",
            "global_review": "global_review",
        },
    )

    graph.add_edge("global_review", "render_pptx")
    graph.add_edge("render_pptx", END)

    return graph


# ================== Routing functions ==================

def route_page_review(state: AgentState) -> Literal[
    "revise_layout", "revise_content", "approve", "blocked", "failed"
]:
    """Decide next step after critic review based on review outcome."""
    page_id = state.get("current_page_id")
    if not page_id:
        return "failed"

    page = state.get("pages", {}).get(page_id)
    if not page:
        return "failed"

    review_status = page.review_status
    if not review_status:
        return "failed"

    if review_status == "approved":
        return "approve"

    if review_status in ("blocked", "failed"):
        return review_status

    if review_status == "needs_revision":
        # Iteration limit reached - accept current state.
        critic_iteration = state.get("critic_iteration", 0)
        if critic_iteration >= 4:
            return "approve"

        # Pick revision path based on majority issue ownership.
        issues = page.review_issues or []
        layout_issues = sum(1 for i in issues if i.get("owner") == "layout")
        content_issues = sum(1 for i in issues if i.get("owner") == "content")
        return "revise_layout" if layout_issues >= content_issues else "revise_content"

    return "failed"


def route_after_finalize(state: AgentState) -> Literal["next_page", "global_review"]:
    """Decide whether to process the next pending page or move to global review."""
    next_page = get_next_pending_page(state)
    if next_page:
        state["current_page_id"] = next_page
        return "next_page"
    return "global_review"


# ================== Node wrappers ==================

def parse_input_node(state: AgentState) -> AgentState:
    state["workflow"].current_node = "parse_input"
    return _nodes.parser_node(state)


def plan_outline_node(state: AgentState) -> AgentState:
    state["workflow"].current_node = "plan_outline"
    return _nodes.planner_node(state)


def prepare_pages_node(state: AgentState) -> AgentState:
    """Initialize page states from outline and select the first page to process."""
    next_page = get_next_pending_page(state)
    if next_page:
        state["current_page_id"] = next_page
    state["workflow"].current_node = "prepare_pages"
    state["workflow"].status = "running"
    return state


def write_page_node(state: AgentState) -> AgentState:
    state["workflow"].current_node = "write_page"
    return _nodes.writer_node(state)


def design_layout_node(state: AgentState) -> AgentState:
    state["workflow"].current_node = "design_layout"
    return _nodes.designer_node(state)


def render_preview_node(state: AgentState) -> AgentState:
    state["workflow"].current_node = "render_preview"
    return _nodes.preview_renderer_node(state)


def critic_review_node(state: AgentState) -> AgentState:
    state["critic_iteration"] = state.get("critic_iteration", 0) + 1
    page_id = state.get("current_page_id")
    if page_id:
        page = state["pages"].get(page_id)
        if page:
            page.iteration = state["critic_iteration"]
    state["workflow"].current_node = "critic_review"
    return _nodes.critic_node(state)


def revise_layout_node(state: AgentState) -> AgentState:
    state["workflow"].current_node = "revise_layout"
    return _nodes.revision_planner_node(state)


def revise_content_node(state: AgentState) -> AgentState:
    state["workflow"].current_node = "revise_content"
    state["content_retry_count"] = state.get("content_retry_count", 0) + 1
    return _nodes.writer_node(state)


def finalize_page_node(state: AgentState) -> AgentState:
    state["workflow"].current_node = "finalize_page"
    return _nodes.finalizer_node(state)


def global_review_node(state: AgentState) -> AgentState:
    state["workflow"].current_node = "global_review"
    return _nodes.global_reviewer_node(state)


def render_pptx_node(state: AgentState) -> AgentState:
    """Render the final PPTX file and update the project status."""
    state["workflow"].current_node = "render_pptx"

    try:
        from ..config import settings
        from ..storage.memory import template_kb

        os.makedirs(settings.storage_path, exist_ok=True)
        filename = f"{state['project'].project_id}.pptx"
        filepath = os.path.join(settings.storage_path, filename)

        spec = state["project"].spec or {}
        style = spec.get("style", "简约商务")
        theme = template_kb.get_template(style)

        # Pages state is dict[page_id, PageState]
        page_dicts = [
            p.to_dict() if hasattr(p, "to_dict") else p
            for p in state["pages"].values()
        ]

        PPTXGenerator().generate(
            pages=page_dicts,
            output_path=filepath,
            title=spec.get("topic", "PPT演示文稿"),
            theme=theme,
        )
        state["output_pptx_path"] = filepath
        state["project"].status = "completed"
    except Exception as e:
        from ..models.review import AgentError

        state["errors"].append(AgentError(
            error_id=f"err-{len(state['errors']) + 1}",
            node="render_pptx",
            message=f"PPTX渲染失败: {str(e)}",
            severity="high",
        ))
        state["project"].status = "failed"

    return state


def handle_error_node(state: AgentState) -> AgentState:
    """Mark the project and the offending page as failed."""
    state["project"].status = "failed"
    state["workflow"].status = "failed"

    page_id = state.get("current_page_id")
    if page_id:
        page = state["pages"].get(page_id)
        if page:
            page.status = "failed"

    return state


# ================== Compilation ==================

_compiled_graph = None


def get_compiled_graph() -> Any:
    """Get the singleton compiled graph instance."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = create_ppt_agent_graph().compile()
    return _compiled_graph


def compile_graph() -> Any:
    """Create a fresh compiled graph (mostly for tests)."""
    return create_ppt_agent_graph().compile()
