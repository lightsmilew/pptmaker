"""Repair geometry using measured templates, without another LLM call."""

from copy import deepcopy
from typing import Any, Dict, List

from ..state import AgentState
from ...tools.slide_scene import template_layout, get_theme
from ...tools.slide_quality import review_scene


def revision_planner_node(state: AgentState) -> AgentState:
    page_id = state.get("current_page_id")
    page = state.get("pages", {}).get(page_id)
    if not page or page.review_status != "needs_revision":
        return state
    state["workflow"].current_node = "revision_planner"
    page.status = "revising"
    state["layout_retry_count"] = state.get("layout_retry_count", 0) + 1
    plan = _generate_revision_plan(page, page.review_issues, state["project"].spec.get("style", "商务简约"))
    page.layout_json = _apply_revision_operations(page.layout_json, plan["operations"])
    page.layout_type = page.layout_json["layout_type"]
    return state


def _generate_revision_plan(page: Any, issues: List[Dict[str, Any]], style="商务简约") -> Dict[str, Any]:
    count = max(len(getattr(page, "key_points", [])), len(getattr(page, "bullet_points", [])))
    page_type = getattr(page, "page_type", "content")
    page_type = getattr(page_type, "value", page_type)
    current = getattr(page, "layout_json", {}) or {}
    # Wider regions help a crowded three-column layout. Canonical geometry also
    # repairs accidental overlaps and elements outside the canvas.
    candidates = [template_layout(page_type, count, bool(getattr(page, "subtitle", "")), suggested,
                                 family=get_theme(style)["family"], density=current.get("content_density", "balanced"))
                  for suggested in ("two_column", "title_content")]
    # Measure candidate geometry with the actual text, rather than repeating the
    # same template that just overflowed. Preserve content and native evidence.
    def quality(layout):
        if not hasattr(page, "to_dict"):
            return 0
        data = page.to_dict()
        data["layout"]["layout_json"] = layout
        result = review_scene(data, style)
        return result["score"]
    layout = max(candidates, key=quality)
    return {"operations": [{"op": "change_layout", "changes": {"layout": layout}}],
            "reason": "使用经过测量的模板修复布局", "expected_improvement": "恢复边界、间距与阅读顺序"}


def _apply_revision_operations(layout_json: Dict[str, Any], operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    layout = deepcopy(layout_json or {})
    for operation in operations:
        changes = operation.get("changes") or {}
        if operation.get("op") == "change_layout" and isinstance(changes.get("layout"), dict):
            layout = deepcopy(changes["layout"])
        elif operation.get("op") in ("move", "resize"):
            for placeholder in layout.get("placeholders", []):
                if placeholder.get("name") == operation.get("target"):
                    placeholder.update({key: value for key, value in changes.items()
                                        if key in ("x", "y", "w", "h")})
    return layout


def generate_revision_plan(page_id: str, layout_json: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Standalone local repair plan for a saved layout."""
    from types import SimpleNamespace
    page = SimpleNamespace(page_id=page_id, layout_json=layout_json)
    return _generate_revision_plan(page, issues)
