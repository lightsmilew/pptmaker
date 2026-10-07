"""Preview renderer using the same measured text and geometry as PPTX export."""

import base64
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..state import AgentState
from ...models.page import PreviewInfo


# ------------------------------------------------------------------
# Standalone renderer (shares the slide scene with PPTXGenerator)
# ------------------------------------------------------------------

def render_preview(
    page_id: str,
    page_data: Dict[str, Any],
    layout_json: Dict[str, Any],
    master_json: Dict[str, Any],
    project_id: str,
    iteration: int = 1,
    spec: Optional[Dict[str, Any]] = None,
    *,
    dpi: int = 120,
) -> str:
    """
    Render a page as a PNG from the shared scene. Native PowerPoint chart axes
    and table styling may differ from the lightweight preview renderer.

    Args:
        page_id: Page identifier
        page_data: Dict with title, subtitle, key_points, bullet_points,
                   chart_data, table_data, speaker_notes
        layout_json: Designer's layout JSON (list of placeholders)
        master_json: Designer's master JSON (colors, fonts, background)
        project_id: Project identifier (for storage path)
        iteration:  Current iteration (for filename)
        spec:       Project spec (for theme override, mirrors PPTX export)
        dpi:        Legacy compatibility argument; scenes use a fixed 120 DPI.

    Returns:
        Absolute path to the generated PNG file.
    """
    from ...config import settings
    from ...tools.slide_scene import build_scene, get_theme, render_scene_png
    data = {**page_data, "page_id": page_id,
            "style_config": {"master": master_json or {}, "layouts": [layout_json or {}]}}
    scene = build_scene(data, get_theme((spec or {}).get("style", "商务简约")))
    path = (Path(settings.storage_path) / "previews" / project_id / page_id / f"iteration-{iteration:02d}.png").resolve()
    return render_scene_png(scene, path)


# ------------------------------------------------------------------
# Node wrapper
# ------------------------------------------------------------------

def preview_renderer_node(state: AgentState) -> AgentState:
    """
    Render a preview image for the current page using the shared slide scene.
    """
    page_id = state.get("current_page_id")
    if not page_id:
        return state

    page = state["pages"].get(page_id)
    if not page:
        return state

    state["workflow"].current_node = "preview_renderer"
    page.status = "rendering"

    try:
        spec = state["project"].spec or {}
        preview_path = render_preview(
            page_id=page_id,
            page_data={
                "page_type":    page.page_type.value,
                "title":        page.title        or "",
                "subtitle":     page.subtitle     or "",
                "key_points":   page.key_points   or [],
                "bullet_points": page.bullet_points or [],
                "chart_data":   page.chart_data,
                "table_data":   page.table_data,
            },
            layout_json=page.layout_json,
            master_json=page.master_json,
            project_id=state["project"].project_id,
            iteration=page.iteration,
            spec=spec,
        )

        page.preview = PreviewInfo(
            image_path=preview_path,
            width=1600,
            height=900,
            rendered_at=datetime.now(),
        )
        state["pages"][page_id] = page

    except Exception as e:
        page.status = "failed"
        page.error = f"预览渲染失败: {str(e)}"
        state["errors"].append({
            "error_id": f"err-{len(state['errors']) + 1}",
            "node": "preview_renderer",
            "message": str(e),
            "severity": "medium",
        })

    return state


def render_preview_base64(
    page_id: str,
    page_data: Dict[str, Any],
    layout_json: Dict[str, Any],
    master_json: Dict[str, Any],
    project_id: str,
    iteration: int = 1,
    *,
    dpi: int = 150,
) -> str:
    """
    Render a page preview and return it as a base64-encoded PNG string.

    Args:
        Same as ``render_preview``.

    Returns:
        Base64-encoded PNG image (no data URI prefix).
    """
    path = render_preview(
        page_id=page_id,
        page_data=page_data,
        layout_json=layout_json,
        master_json=master_json,
        project_id=project_id,
        iteration=iteration,
        dpi=dpi,
    )
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
