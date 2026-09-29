"""PPT generation tools."""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime


class PPTXGenerator:
    """Generate PowerPoint files from structured page data."""

    def __init__(self):
        self.pptx_available = self._check_pptx()

    def _check_pptx(self) -> bool:
        """Check if python-pptx is available."""
        try:
            from pptx import Presentation
            return True
        except ImportError:
            return False

    def generate(
        self,
        pages: List[Dict[str, Any]],
        output_path: str,
        title: str = "PPT Presentation",
        theme: Optional[Dict[str, Any]] = None,
        template_path: Optional[str] = None,
    ) -> str:
        """
        Generate a PPTX file from page data.

        Args:
            pages: List of page data dictionaries
            output_path: Path to save the file
            title: Presentation title
            theme: Theme configuration (colors, fonts)

        Returns:
            Path to generated file
        """
        if self.pptx_available:
            return self._generate_with_pptx(pages, output_path, title, theme, template_path)
        else:
            return self._generate_fallback(pages, output_path, title)

    def _generate_with_pptx(
        self,
        pages: List[Dict[str, Any]],
        output_path: str,
        title: str,
        theme: Optional[Dict[str, Any]],
        template_path: Optional[str] = None,
    ) -> str:
        """Generate using python-pptx library."""
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.enum.shapes import MSO_SHAPE

        # Default theme
        default_theme = {
            "primary": "#6366F1",
            "secondary": "#8B5CF6",
            "text": "#1E293B",
            "background": "#FFFFFF",
        }
        theme = theme or default_theme

        # Use a fresh package for output. Template files are kept as references
        # only and are not applied to generated presentations.
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        self.canvas_width, self.canvas_height = 13.333, 7.5

        # Color helpers
        from pydantic import BaseModel

        def hex_to_rgb(hex_color: str) -> RGBColor:
            hex_color = hex_color.lstrip("#")
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return RGBColor(r, g, b)

        primary = hex_to_rgb(theme.get("primary", "#6366F1"))
        text_color = hex_to_rgb(theme.get("text", "#1E293B"))
        gray_color = hex_to_rgb("#64748B")

        for page in pages:
            slide = prs.slides.add_slide(prs.slide_layouts[6])

            # Consistent editorial canvas: warm white background with a restrained accent rule.
            bg = slide.background.fill
            bg.solid()
            bg.fore_color.rgb = hex_to_rgb(theme.get("background", "#FFFFFF"))
            rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.12), prs.slide_height)
            rule.fill.solid()
            rule.fill.fore_color.rgb = primary
            rule.line.fill.background()

            # Handle both dict and Pydantic model
            if isinstance(page, BaseModel):
                page_dict = page.model_dump()
            else:
                page_dict = page

            # Designer may provide a complete JSON style contract. Render it first;
            # the legacy type-based renderer remains the compatibility fallback.
            style_config = page_dict.get("style_config")
            if style_config:
                self._render_style_config(slide, page_dict, style_config, theme)
                notes = page_dict.get("speaker_notes", "")
                if notes:
                    slide.notes_slide.notes_text_frame.text = notes
                continue

            # Add content based on page type
            page_type = page_dict.get("page_type", "content")

            # Title
            title_text = page_dict.get("title", "")
            if title_text:
                self._add_title(slide, title_text, text_color)

            # Subtitle
            subtitle = page_dict.get("subtitle", "")
            if subtitle:
                self._add_subtitle(slide, subtitle, gray_color)

            # Content based on type
            if page_type == "cover":
                self._add_cover_elements(slide, prs, primary)
            elif page_type == "toc":
                self._add_toc_elements(slide, page_dict.get("key_points", []), gray_color)
            elif page_type == "chart":
                self._add_chart_elements(slide, page_dict)
            else:
                self._add_content_elements(slide, page_dict)

            # Speaker notes
            notes = page_dict.get("speaker_notes", "")
            if notes:
                notes_slide = slide.notes_slide
                notes_slide.notes_text_frame.text = notes

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        prs.save(output_path)
        return output_path

    def _render_style_config(self, slide, page: Dict[str, Any], config: Dict[str, Any], theme: Optional[Dict[str, Any]] = None):
        """Render Designer's inch-based placeholders, filling every content region."""
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.enum.shapes import MSO_SHAPE
        master = config.get("master", {})
        colors = master.get("color_scheme", {})
        fonts = master.get("font_scheme", {})
        background = master.get("background", {}).get("rgb", [255, 255, 255])
        # The selected home-page style is authoritative for the exported deck.
        # Keep LLM geometry, but apply the chosen theme colors and fonts.
        if theme:
            def parse_hex(value, fallback):
                value = str(value or fallback).lstrip("#")
                try:
                    return [int(value[i:i+2], 16) for i in (0, 2, 4)]
                except (ValueError, IndexError):
                    return fallback
            colors = dict(colors)
            colors.update({
                "primary": parse_hex(theme.get("primary"), colors.get("primary", [20, 40, 80])),
                "secondary": parse_hex(theme.get("secondary"), colors.get("secondary", [80, 100, 140])),
                "text": parse_hex(theme.get("text"), colors.get("text", [30, 30, 30])),
            })
            background = parse_hex(theme.get("background"), background)
            fonts = dict(fonts)
            theme_fonts = theme.get("fonts", {})
            fonts["title_font"] = theme_fonts.get("title", fonts.get("title_font", "Microsoft YaHei"))
            fonts["body_font"] = theme_fonts.get("body", fonts.get("body_font", "Microsoft YaHei"))
        def rgb(name, fallback):
            return RGBColor(*colors.get(name, fallback))
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor(*background)
        title_color = rgb("primary", [20, 40, 80])
        body_color = rgb("text", [30, 30, 30])
        layouts = config.get("layouts", [])
        layout = layouts[0] if layouts else {"placeholders": []}
        placeholders = layout.get("placeholders", [])
        points = [str(x).strip() for x in (page.get("key_points") or page.get("bullet_points") or []) if str(x).strip()]
        if not points:
            points = [str(x).strip() for x in (page.get("bullet_points") or []) if str(x).strip()]
        content_slots = [p for p in placeholders if p.get("type") == "text" and p.get("name") not in ("subtitle", "caption")]
        groups = [[] for _ in content_slots]
        for index, point in enumerate(points):
            if groups:
                groups[index % len(groups)].append(point)
        content_index = 0
        rendered_body = False
        for ph in placeholders:
            kind = ph.get("type", "text"); name = ph.get("name", kind)
            # Clamp malformed LLM geometry to the 13.333 x 7.5 inch canvas.
            px, py, pw, phh = (float(ph.get(k, 0)) for k in ("x","y","w","h"))
            canvas_w = getattr(self, "canvas_width", 13.333)
            canvas_h = getattr(self, "canvas_height", 7.5)
            px, py = max(0, min(px, canvas_w - .1)), max(0, min(py, canvas_h - .1))
            pw, phh = max(.4, min(pw, canvas_w - px)), max(.3, min(phh, canvas_h - py))
            x,y,w,h = Inches(px), Inches(py), Inches(pw), Inches(phh)
            if kind == "accent":
                shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
                shape.fill.solid(); shape.fill.fore_color.rgb = rgb("accent", [60,120,180]); shape.line.fill.background()
                continue
            if kind == "chart" and page.get("chart_data"):
                data = page["chart_data"].get("data", {})
                labels, values = data.get("labels", []), data.get("values", [])
                if labels and values and len(labels) == len(values):
                    from pptx.chart.data import CategoryChartData
                    from pptx.enum.chart import XL_CHART_TYPE
                    chart_data = CategoryChartData(); chart_data.categories = labels
                    chart_data.add_series(page["chart_data"].get("title", "数据"), values)
                    slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, w, h, chart_data)
                    rendered_body = True
                    continue
            if kind == "table" and page.get("table_data"):
                table_data = page["table_data"]
                rows = [table_data.get("headers", [])] + table_data.get("rows", [])
                if rows and rows[0]:
                    table = slide.shapes.add_table(len(rows), len(rows[0]), x, y, w, h).table
                    # Keep table text readable and distribute columns evenly.
                    for column in table.columns:
                        column.width = int(w / len(rows[0]))
                    for row_index, row in enumerate(rows):
                        for col_index, value in enumerate(row[:len(rows[0])]):
                            cell = table.cell(row_index, col_index)
                            cell.text = str(value)
                            for paragraph in cell.text_frame.paragraphs:
                                paragraph.font.name = fonts.get("body_font", "Microsoft YaHei")
                                paragraph.font.size = Pt(max(14, min(float(fonts.get("body_size", 18)), 20)))
                    rendered_body = True
                    continue
            if kind in ("chart", "table"):
                # Unsupported or missing evidence: show the page's actual points.
                value = "\n".join(f"• {item}" for item in points)
                rendered_body = rendered_body or bool(value)
            elif kind == "title":
                value = page.get("title", "")
            elif name == "subtitle":
                value = page.get("subtitle", "")
            elif name == "caption":
                value = ""
            else:
                group = groups[content_index] if content_index < len(groups) else []
                content_index += 1
                value = "\n".join(f"• {item}" for item in group)
                rendered_body = rendered_body or bool(value)
            if not value:
                continue
            box = slide.shapes.add_textbox(x, y, w, h); tf = box.text_frame; tf.word_wrap = True
            for line_index, line in enumerate(value.split("\n")):
                p = tf.paragraphs[0] if line_index == 0 else tf.add_paragraph()
                p.text = line
                p.font.name = fonts.get("title_font" if kind == "title" else "body_font", "Microsoft YaHei")
                size = float(fonts.get("title_size" if kind == "title" else "body_size", 28 if kind == "title" else 18))
                p.font.size = Pt(max(24 if kind == "title" else 16, min(size, 44 if kind == "title" else 24)))
                p.font.bold = kind == "title"
                p.font.color.rgb = title_color if kind == "title" else body_color
                p.space_after = Pt(10)
                if kind == "title": p.alignment = PP_ALIGN.LEFT
        if points and not rendered_body:
            self._add_content_elements(slide, {"key_points": points})

    def _add_title(self, slide, text: str, color):
        """Add title text box."""
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN

        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(1))
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = Pt(32)
        p.font.bold = True
        p.font.color.rgb = color

    def _add_subtitle(self, slide, text: str, color):
        """Add subtitle text box."""
        from pptx.util import Inches, Pt

        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(1.1), Inches(12), Inches(0.6))
        tf = txBox.text_frame
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = Pt(18)
        p.font.color.rgb = color

    def _add_cover_elements(self, slide, prs, color):
        """Add decorative elements to cover."""
        from pptx.util import Inches
        from pptx.enum.shapes import MSO_SHAPE

        width = prs.slide_width
        height = prs.slide_height

        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            0, height - Inches(1.5),
            width, Inches(1.5)
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()

    def _add_toc_elements(self, slide, items: List[str], color):
        """Add table of contents."""
        from pptx.util import Inches, Pt

        txBox = slide.shapes.add_textbox(Inches(1), Inches(1.8), Inches(11), Inches(5))
        tf = txBox.text_frame

        for i, item in enumerate(items):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = f"{i + 1}. {item}"
            p.font.size = Pt(24)
            p.font.color.rgb = color
            p.space_after = Pt(16)

    def _add_chart_elements(self, slide, page: Dict[str, Any]):
        """Add chart placeholder."""
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.dml.color import RGBColor

        chart_data = page.get("chart_data", {})
        title = chart_data.get("title", "数据图表")

        # Add placeholder box
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.7), Inches(1.8),
            Inches(11.5), Inches(5)
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(0xF1, 0xF5, 0xF9)
        shape.line.color.rgb = RGBColor(0xE2, 0xE8, 0xF0)

        # Add text
        txBox = slide.shapes.add_textbox(Inches(0.7), Inches(4), Inches(11.5), Inches(0.8))
        tf = txBox.text_frame
        p = tf.paragraphs[0]
        p.text = f"[ {title} ]"
        p.font.size = Pt(24)
        p.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
        p.alignment = PP_ALIGN.CENTER

    def _add_content_elements(self, slide, page: Dict[str, Any]):
        """Add content elements."""
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor

        points = page.get("key_points", []) or page.get("bullet_points", [])
        gray_color = RGBColor(0x47, 0x56, 0x69)

        txBox = slide.shapes.add_textbox(Inches(0.7), Inches(1.8), Inches(11.5), Inches(5.5))
        tf = txBox.text_frame
        tf.word_wrap = True

        for i, point in enumerate(points):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()

            # Clean up bullet formatting
            clean_point = point.lstrip("•-*· ").strip()
            if not clean_point.startswith(("•", "-", "*")):
                clean_point = f"• {clean_point}"

            p.text = clean_point
            p.font.size = Pt(20)
            p.font.color.rgb = gray_color
            p.space_after = Pt(10)

    def _generate_fallback(
        self,
        pages: List[Dict[str, Any]],
        output_path: str,
        title: str
    ) -> str:
        """Fallback: generate a text-based representation."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        with open(output_path.replace(".pptx", ".txt"), "w", encoding="utf-8") as f:
            f.write(f"{'='*60}\n")
            f.write(f"{title}\n")
            f.write(f"{'='*60}\n\n")

            for i, page in enumerate(pages):
                f.write(f"\n--- Page {i+1}: {page.get('title', 'Untitled')} ---\n")
                f.write(f"Type: {page.get('page_type', 'content')}\n\n")

                for point in page.get("key_points", []):
                    f.write(f"  • {point}\n")

                if page.get("speaker_notes"):
                    f.write(f"\nNotes: {page.get('speaker_notes')}\n")

        return output_path


class TemplateLibrary:
    """Manage PPT layout templates."""

    TEMPLATES = {
        "学术简约": {
            "primary": "#2563EB",
            "secondary": "#3B82F6",
            "text": "#1E3A5F",
            "background": "#FFFFFF",
            "fonts": {"title": "Arial", "body": "Calibri"},
        },
        "商务正式": {
            "primary": "#1E40AF",
            "secondary": "#3B82F6",
            "text": "#1E293B",
            "background": "#F8FAFC",
            "fonts": {"title": "Arial", "body": "Arial"},
        },
        "科技风": {
            "primary": "#6366F1",
            "secondary": "#8B5CF6",
            "text": "#1E293B",
            "background": "#0F172A",
            "fonts": {"title": "Inter", "body": "Inter"},
        },
        "简约商务": {
            "primary": "#3B82F6",
            "secondary": "#60A5FA",
            "text": "#1E293B",
            "background": "#FFFFFF",
            "fonts": {"title": "Microsoft YaHei", "body": "Microsoft YaHei"},
        },
        "创意活泼": {
            "primary": "#EC4899",
            "secondary": "#F472B6",
            "text": "#1E293B",
            "background": "#FDF2F8",
            "fonts": {"title": "Poppins", "body": "Inter"},
        },
    }

    def get_template(self, name: str) -> Dict[str, Any]:
        """Get template by name."""
        return self.TEMPLATES.get(name, self.TEMPLATES["简约商务"])

    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.TEMPLATES.keys())
