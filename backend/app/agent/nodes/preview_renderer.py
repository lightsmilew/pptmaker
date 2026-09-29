"""Preview renderer - renders page preview images matching the PPTX generator output."""

import base64
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..state import AgentState
from ...contracts.schemas import PreviewInfo


# ------------------------------------------------------------------
# Standalone renderer (mirrors PPTXGenerator._render_style_config exactly)
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
    dpi: int = 150,
) -> str:
    """
    Render a page as a PNG using matplotlib, faithfully reproducing the
    PPTXGenerator._render_style_config layout logic so the preview
    image is identical to what will appear in the final PPTX.

    Args:
        page_id: Page identifier
        page_data: Dict with title, subtitle, key_points, bullet_points,
                   chart_data, table_data, speaker_notes
        layout_json: Designer's layout JSON (list of placeholders)
        master_json: Designer's master JSON (colors, fonts, background)
        project_id: Project identifier (for storage path)
        iteration:  Current iteration (for filename)
        spec:       Project spec (for theme override, mirrors PPTX export)
        dpi:        Resolution (default 150 for preview quality/speed balance)

    Returns:
        Absolute path to the generated PNG file.
    """
    import matplotlib
    matplotlib.use("Agg")           # non-GUI backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    # --- Canvas geometry ------------------------------------------------
    CANVAS_W_INCH = 13.333   # standard 16:9 slide
    CANVAS_H_INCH = 7.5

    fig = plt.figure(figsize=(CANVAS_W_INCH, CANVAS_H_INCH), dpi=dpi)
    ax  = fig.add_axes([0, 0, 1, 1])   # full-figure axes
    ax.set_xlim(0, CANVAS_W_INCH)
    ax.set_ylim(0, CANVAS_H_INCH)
    ax.axis("off")

    canvas: FigureCanvasAgg = fig.canvas

    # --- Resolve theme / master ----------------------------------------
    master = master_json or {}
    color_scheme = (master.get("color_scheme") or {}).copy()
    font_scheme  = (master.get("font_scheme")  or {}).copy()
    bg_rgb = master.get("background", {}).get("rgb", [255, 255, 255])

    def _parse_hex(value, fallback):
        v = str(value or fallback).lstrip("#")
        try:
            return [int(v[i:i+2], 16) for i in (0, 2, 4)]
        except (ValueError, IndexError):
            return fallback

    def _rgb(name, fallback):
        raw = color_scheme.get(name, fallback)
        if isinstance(raw, str):
            return _parse_hex(raw, fallback)
        return raw or fallback

    # --- Apply template theme override (identical to PPTXGenerator) ---
    # Load the template that will be used during PPTX export so the
    # preview matches the final output exactly.
    from ...storage.memory import template_kb
    _spec = spec or {}
    template_name = _spec.get("style", "简约商务")
    template = template_kb.get_template(template_name)

    def _override_color(key, fallback):
        """Resolve a color: prefer template hex, else master RGB/hex, else fallback."""
        # Template uses hex strings like "#2563EB"
        v = template.get(key)
        if v:
            return _parse_hex(v, fallback)
        # Fall back to master (already RGB list or hex string)
        raw = color_scheme.get(key)
        if raw:
            if isinstance(raw, str):
                return _parse_hex(raw, fallback)
            return raw
        return fallback

    bg_rgb    = _override_color("background", [255, 255, 255])
    title_clr = _override_color("primary",   [20, 40, 80])
    body_clr  = _override_color("text",      [30, 30, 30])
    # Accent uses master value (no template override for accent)
    accent_clr = _rgb("accent", [60, 120, 180])

    # Fonts: always use master_json defaults (typically Microsoft YaHei) so
    # Chinese characters render correctly.  Do NOT apply template font overrides —
    # some templates use Arial/Calibri/Inter which lack CJK glyphs.
    title_font = font_scheme.get("title_font", "Microsoft YaHei")
    body_font  = font_scheme.get("body_font",  "Microsoft YaHei")

    title_size = float(font_scheme.get("title_size", 28))
    body_size  = float(font_scheme.get("body_size",  18))

    # --- Background ------------------------------------------------------
    fig.patch.set_facecolor([c / 255 for c in bg_rgb])
    ax.set_facecolor([c / 255 for c in bg_rgb])

    # --- Left accent bar (mirrors PPTXGenerator accent strip) ------------
    bar_color = _parse_hex(template.get("primary", "#6366F1"), [99, 102, 241])
    rect = mpatches.Rectangle(
        (0.0, 0.0), 0.12, CANVAS_H_INCH,
        linewidth=0, facecolor=[c / 255 for c in bar_color],
        zorder=1,
    )
    ax.add_patch(rect)

    # --- Collect all text lines to render --------------------------------
    key_points  = page_data.get("key_points")   or []
    bullet_pts  = page_data.get("bullet_points") or []
    chart_data  = page_data.get("chart_data")
    table_data  = page_data.get("table_data")

    # Flatten all content into bullet lines
    all_lines: List[str] = []
    for kp in key_points:
        if kp and str(kp).strip():
            all_lines.append(str(kp))
    for bp in bullet_pts:
        if bp and str(bp).strip():
            all_lines.append("  " + str(bp))

    title_str = page_data.get("title",  "")
    subtitle_str = page_data.get("subtitle", "")

    # --- Placeholder layout ---------------------------------------------
    layouts   = layout_json.get("layouts", []) if layout_json else []
    layout   = layouts[0] if layouts else {"placeholders": []}
    placeholders = layout.get("placeholders", [])

    # Build (content_index)-grouped text columns.
    # Group 0 → first text placeholder, group 1 → second, etc.
    content_slots = [
        p for p in placeholders
        if p.get("type") == "text" and p.get("name") not in ("subtitle", "caption")
    ]
    num_cols = len(content_slots)

    if num_cols == 0:
        # No text slots — fall back to legacy single-column layout
        # that matches PPTXGenerator._add_content_elements fallback.
        num_cols = 1
        content_slots = [{"Name": "_auto", "type": "text",
                         "x": 0.7, "y": 1.8, "w": 11.5, "h": 5.5}]

    groups: List[List[str]] = [[] for _ in content_slots]
    for idx, line in enumerate(all_lines):
        groups[idx % num_cols].append(line)

    # Track whether any body text was actually drawn.
    rendered_body = False

    for ph in placeholders:
        kind  = ph.get("type",  "text")
        name  = ph.get("name",  kind)
        px, py, pw, phh = (
            float(ph.get("x", 0)),
            float(ph.get("y", 0)),
            float(ph.get("w", 0)),
            float(ph.get("h", 0)),
        )
        # Clamp to canvas.
        px  = max(0.0, min(px,  CANVAS_W_INCH - 0.1))
        py  = max(0.0, min(py,  CANVAS_H_INCH - 0.1))
        pw  = max(0.4, min(pw,  CANVAS_W_INCH - px))
        phh = max(0.3, min(phh, CANVAS_H_INCH - py))

        if kind == "accent":
            rect = mpatches.Rectangle(
                (px, py), pw, phh,
                linewidth=0, facecolor=[c / 255 for c in accent_clr],
                zorder=1,
            )
            ax.add_patch(rect)
            continue

        if kind == "chart" and chart_data:
            # Draw a simple bar-chart approximation from chart_data.
            data  = chart_data.get("data", {})
            labels = data.get("labels", [])
            values = data.get("values", [])
            if labels and values and len(labels) == len(values):
                max_val = max(values) if values else 1
                bar_w  = pw / (len(labels) + 0.5)
                for i, (lbl, val) in enumerate(zip(labels, values)):
                    bx = px + i * bar_w + bar_w * 0.1
                    bh = (val / max_val) * phh * 0.8
                    bar = mpatches.Rectangle(
                        (bx, py + phh * 0.1), bar_w * 0.8, bh,
                        facecolor=[c / 255 for c in accent_clr], alpha=0.7,
                        zorder=2,
                    )
                    ax.add_patch(bar)
                    ax.text(
                        bx + bar_w * 0.4, py + phh * 0.1 + bh + phh * 0.02,
                        lbl, fontsize=body_size * 0.6, ha="center",
                        color=[c / 255 for c in body_clr],
                        fontname=body_font, zorder=3,
                    )
                rendered_body = True
                continue

        if kind == "table" and table_data:
            # Draw a grid table from table_data.
            headers = table_data.get("headers", [])
            rows     = table_data.get("rows", [])
            all_rows = [headers] + rows
            if headers and all_rows:
                n_cols  = len(headers)
                col_w   = pw / n_cols
                row_h   = min(phh / (len(all_rows) + 0.5), 0.35)
                # Header row
                for ci, hdr in enumerate(headers):
                    ax.text(
                        px + ci * col_w + col_w / 2,
                        py + phh - row_h * 0.5,
                        str(hdr),
                        fontsize=max(14, min(body_size, 20)), ha="center", va="center",
                        fontname=title_font,
                        color=[c / 255 for c in title_clr], zorder=3,
                    )
                # Divider
                ax.plot(
                    [px, px + pw], [py + phh - row_h, py + phh - row_h],
                    color=[c / 255 for c in title_clr], linewidth=1.5, zorder=3,
                )
                # Data rows
                for ri, row in enumerate(rows[:int(phh / row_h) - 1]):
                    ry = py + phh - (ri + 2) * row_h
                    for ci, cell in enumerate(row[:n_cols]):
                        ax.text(
                            px + ci * col_w + col_w / 2,
                            ry + row_h / 2,
                            str(cell),
                            fontsize=max(14, min(body_size, 20)), ha="center", va="center",
                            fontname=body_font,
                            color=[c / 255 for c in body_clr], zorder=3,
                        )
                rendered_body = True
                continue

        # Text / content slot
        if kind in ("chart", "table") and not rendered_body:
            # Unsupported evidence type — fall through to raw bullets
            pass

        if kind == "title":
            value = title_str
            fclr = title_clr
            fsz  = max(24, min(title_size, 44))
            fbold = True
            faln  = "left"
        elif name == "subtitle":
            value = subtitle_str
            fclr = body_clr
            fsz  = body_size * 0.9
            fbold = False
            faln  = "left"
        elif name == "caption":
            continue   # caption placeholder: skip (no caption text stored)
        else:
            # content slot — pick from the round-robin groups
            col_idx = None
            for ci, slot in enumerate(content_slots):
                if slot.get("name") == name:
                    col_idx = ci
                    break
            if col_idx is None:
                col_idx = 0
            col_group = groups[col_idx] if col_idx < len(groups) else []
            value = "\n".join(f"• {line}" for line in col_group)
            fclr = body_clr
            fsz  = max(16, min(body_size, 24))
            fbold = False
            faln  = "left"
            rendered_body = rendered_body or bool(value.strip())

        if not value:
            continue

        # Wrap text at placeholder width (approximate chars per line)
        char_per_inch = 7.5   # ~7.5 chars per inch at body_size
        max_chars = int(pw * char_per_inch)
        wrapped = textwrap.fill(
            value, width=max(10, max_chars),
            subsequent_indent="",
            break_long_words=False,
            break_on_hyphens=True,
        )

        ax.text(
            px + 0.05, py + phh - fsz * 0.015,
            wrapped,
            fontsize=fsz,
            fontname=title_font if fbold else body_font,
            fontweight="bold" if fbold else "normal",
            color=[c / 255 for c in fclr],
            ha="left", va="top",
            wrap=False,               # we pre-wrap
            zorder=3,
            # clip to bounding box
            clip_on=True,
            # bbox so text doesn't overflow
            bbox=dict(
                boxstyle="square,pad=0",
                facecolor="none",
                edgecolor="none",
                alpha=0,
                lw=0,
            ),
        )

    # If no body text was drawn at all, fall back to a simple
    # content block at the bottom so the page isn't blank.
    if not rendered_body and all_lines:
        fallback_lines = "\n".join(f"• {ln}" for ln in all_lines[:8])
        ax.text(
            1.0, 1.8,
            fallback_lines,
            fontsize=max(12, min(body_size, 22)),
            fontname=body_font,
            color=[c / 255 for c in body_clr],
            ha="left", va="top",
            zorder=3,
        )

    # --- Save ------------------------------------------------------------
    preview_dir  = Path("storage") / "previews" / project_id / page_id
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_path = preview_dir / f"iteration-{iteration:02d}.png"
    fig.savefig(
        str(preview_path),
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0,
        format="png",
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)
    return str(preview_path)


# ------------------------------------------------------------------
# Node wrapper
# ------------------------------------------------------------------

def preview_renderer_node(state: AgentState) -> AgentState:
    """
    Render a preview image for the current page using the matplotlib
    renderer (mirrors PPTXGenerator._render_style_config).
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
