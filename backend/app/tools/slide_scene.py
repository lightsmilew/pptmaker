"""Shared slide composition for editable PPTX and PNG previews.

Geometry is in inches, typography in points. Text is measured once and the same
explicit line breaks are used by both renderers. No model-generated drawing code.
"""

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from .design_catalog import STYLE_DEFINITIONS

WIDTH, HEIGHT, DPI = 13.333, 7.5, 120
FONT_NAME = "Microsoft YaHei"
PALETTES = {row[0]: row[4:] for row in STYLE_DEFINITIONS}
ALIASES = {"简约商务": "商务简约", "简约专业": "商务简约", "商务正式": "金融专业"}


def get_theme(style="商务简约"):
    name = ALIASES.get(style, style)
    definition = next((row for row in STYLE_DEFINITIONS if row[0] == name), STYLE_DEFINITIONS[0])
    family = definition[3]
    primary, secondary, text, background = definition[4:]
    return dict(primary=primary, secondary=secondary, accent=primary, text=text, background=background,
                family=family, fonts=dict(title="SimSun" if family in ("warm", "retro", "editorial") and name != "商务简约" else FONT_NAME, body=FONT_NAME))


def rgb(value):
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return tuple(int(value.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=128)
def font(size, bold=False, font_name=FONT_NAME):
    from PIL import ImageFont
    candidates = [Path("C:/Windows/Fonts") / ("simsun.ttc" if font_name == "SimSun" else "msyhbd.ttc" if bold else "msyh.ttc"),
                  Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), max(1, round(size * DPI / 72)))
    return ImageFont.load_default()


def wrap(text, width, size, bold=False, font_name=FONT_NAME):
    """Character wrapping supports Chinese and Latin; prefers word boundaries."""
    selected = font(size, bold, font_name)
    limit = max(1, width * DPI)
    lines = []
    for paragraph in str(text).split("\n"):
        current = ""
        for char in paragraph:
            if current and selected.getlength(current + char) > limit:
                if char in "，。；：！？、）】》,.!?;:)" and len(current) > 1:
                    # Never leave closing punctuation on its own line.
                    lines.append(current[:-1])
                    current = current[-1] + char
                    continue
                split = current.rfind(" ")
                if split > len(current) // 2:
                    lines.append(current[:split])
                    current = current[split + 1:] + char
                else:
                    lines.append(current)
                    current = char
            else:
                current += char
        lines.append(current)
    return lines


def text_element(name, text, x, y, w, h, size=20, color="#202B26", bold=False, minimum=16, font_name=FONT_NAME):
    size = float(size)
    while size > minimum:
        lines = wrap(text, w, size, bold, font_name)
        if len(lines) * size / 72 * 1.3 <= h:
            break
        size -= 1
    lines = wrap(text, w, size, bold, font_name)
    return dict(kind="text", name=name, text="\n".join(lines), x=x, y=y, w=w, h=h,
                size=size, color=color, bold=bold, font_name=font_name, line_height=1.3,
                overflow=len(lines) * size / 72 * 1.3 > h + .02)


def normalize_page(page):
    if hasattr(page, "model_dump"):
        page = page.model_dump(mode="json")
    result = deepcopy(page or {})
    result.update(result.pop("content", {}) or {})
    layout = result.pop("layout", {}) or {}
    if layout.get("layout_json") and not result.get("style_config"):
        result["style_config"] = {"master": layout.get("master_json") or {},
                                  "layouts": [layout["layout_json"]]}
    return result


def content_items(page):
    headings = page.get("key_points") or []
    details = page.get("bullet_points") or []
    return [(str(headings[i]) if i < len(headings) else "",
             str(details[i]) if i < len(details) and details[i] != (headings[i] if i < len(headings) else "") else "")
            for i in range(max(len(headings), len(details)))]


def template_layout(page_type, count=3, subtitle=True, suggested="", *,
                    layout_mode="auto", page_index=None, family="editorial", density="balanced"):
    """Choose content-safe measured geometry, with deterministic deck rhythm.

    Semantic comparisons/processes take priority over decorative variation.
    Page index rotates generic content layouts, without extra model calls.
    """
    index = page_index or 0
    suggested = str(suggested).lower()
    kind = "title_content"
    cover_variant = "edge"
    if page_type in ("cover", "thankyou"):
        kind = "cover"
        cover_variant = "center" if family in ("minimal", "dark") else "split" if family in ("grid", "bold", "playful", "portfolio") else "edge"
        if cover_variant == "split":
            regions = [("title", "title", .85, 1.6, 7.5, 2.0), ("subtitle", "text", .9, 4.0, 7.4, 1.3)]
        elif cover_variant == "center":
            regions = [("title", "title", 1.5, 2.2, 10.3, 1.8), ("subtitle", "text", 1.55, 4.35, 9.8, 1.1)]
        else:
            regions = [("title", "title", .85, 2.0, 9.5, 1.7), ("subtitle", "text", .85, 4.0, 8.8, 1.3)]
    else:
        top = 2.6 if subtitle else 2.2
        bottom = 6.65
        regions = [("title", "title", .85, .6, 11.6, 1.2)]
        if subtitle:
            regions.append(("subtitle", "text", .85, 1.82, 11.5, .5))
        if page_type == "table":
            regions.append(("table", "table", .85, top, 11.6, (5.1 if count else bottom)-top))
            if count:
                regions.append(("caption", "text", .85, 5.35, 11.6, 1.3))
        elif page_type == "chart":
            kind = "chart_content"
            regions.extend([("chart", "chart", .85, top, 7.4, bottom-top), ("content", "text", 8.7, top, 3.8, bottom-top)])
        else:
            if page_type == "toc":
                kind = "toc" if count <= 4 else "two_column"
            elif suggested in ("title_content", "single_column", "单栏布局"):
                kind = "title_content"
            elif suggested in ("two_column", "comparison", "左右双栏", "对比"):
                kind = "two_column"
            elif suggested in ("timeline", "流程", "上下分区", "步骤") and 2 <= count <= 4:
                kind = "timeline"
            elif suggested in ("cards_grid", "网格") and 2 <= count <= 6:
                kind = "cards_grid"
            elif layout_mode == "editorial":
                kind = ("left_rail", "stacked_rows" if count <= 3 else "two_column")[index % 2]
            elif layout_mode == "structured":
                kind = ("cards_grid", "three_column" if count == 3 else "two_column")[index % 2] if count <= 6 else "two_column"
            elif layout_mode == "spotlight":
                kind = "statement" if count <= 2 else "left_rail"
            elif page_index is not None:
                choices = (["statement", "left_rail", "stacked_rows"] if count <= 2 else
                           ["three_column", "left_rail", "stacked_rows", "cards_grid"] if count == 3 else
                           ["two_column", "cards_grid", "left_rail"] if count <= 6 else ["two_column", "left_rail"])
                # Same theme keeps a recognisable rhythm; typography and cover differ by family.
                offset = {"grid":1, "playful":2, "bold":1, "portfolio":1}.get(family, 0)
                kind = choices[(index + offset) % len(choices)]
            elif count > 3:
                kind = "two_column"
            elif count == 3:
                kind = "three_column"
            if kind == "left_rail":
                regions = [("title", "title", .85, 1.0, 3.35, 2.55)]
                if subtitle:
                    regions.append(("subtitle", "text", .85, 3.9, 3.35, 1.1))
                regions.append(("content", "text", 4.95, 1.05, 7.5, 5.6))
            elif kind == "cards_grid":
                cols = 2 if count in (2, 4) else 3
                rows = 1 if count <= 3 else 2
                cell_w = (11.6 - .38*(cols-1))/cols
                cell_h = (bottom-top-.35*(rows-1))/rows
                for i in range(max(1, count)):
                    regions.append((f"content_{i+1}", "text", .85+(i % cols)*(cell_w+.38)+.16,
                                    top+(i//cols)*(cell_h+.35)+.16, cell_w-.32, cell_h-.32))
            elif kind in ("stacked_rows", "timeline"):
                for i in range(max(1, count)):
                    if kind == "timeline":
                        cell_w = (11.6-.4*(count-1))/max(1,count)
                        regions.append((f"content_{i+1}", "text", .85+i*(cell_w+.4), top+.5, cell_w, bottom-top-.5))
                    else:
                        cell_h = (bottom-top-.2*(count-1))/max(1,count)
                        regions.append((f"content_{i+1}", "text", 1.45, top+i*(cell_h+.2), 11.0, cell_h))
            elif kind == "two_column":
                regions.extend([("content_1", "text", .85, top, 5.45, bottom-top), ("content_2", "text", 7.0, top, 5.45, bottom-top)])
            elif kind == "three_column":
                regions.extend([(f"content_{i+1}", "text", .85+i*4.05, top, 3.5, bottom-top) for i in range(3)])
            else:
                regions.append(("content", "text", .85, top, 11.6, bottom-top))
    return dict(layout_id=f"folio-{kind}-{cover_variant}" if kind == "cover" else f"folio-{kind}",
                layout_type=kind, cover_variant=cover_variant, content_density=density, template_version=3,
                placeholders=[dict(name=n, type=t, x=x, y=y, w=w, h=h) for n,t,x,y,w,h in regions])


def build_scene(page, theme=None):
    page = normalize_page(page)
    theme = theme or get_theme()
    config = page.get("style_config") or {}
    layout = (config.get("layouts") or [None])[0]
    items = content_items(page)
    page_type = page.get("page_type", "content")
    # Missing evidence should use the full text canvas, not an empty chart or
    # table with explanations squeezed into a narrow side column.
    if page_type in ("chart", "table") and not valid_evidence(page_type, page.get(page_type+"_data")):
        page_type = "content"
        layout = template_layout("content", len(items), bool(page.get("subtitle")))
    if not layout or not layout.get("placeholders"):
        layout = template_layout(page_type, len(items), bool(page.get("subtitle")))
    elements = []
    ink, accent = theme["text"], theme["primary"]
    family = theme.get("family", "editorial")
    layout_kind = layout.get("layout_type", "title_content")
    dark = sum(rgb(theme["background"])) < 320
    muted, rule = ("#BBCBC8", "#41514F") if dark else ("#6E7972", "#D8DDD7")
    def rect(name, x,y,w,h,color):
        elements.append(dict(kind="rect", name=name, x=x,y=y,w=w,h=h,color=color))
    if page_type in ("cover", "thankyou"):
        variant = layout.get("cover_variant", "edge")
        if variant == "split":
            rect("cover_panel", 9.25, 0, 4.08, HEIGHT, accent)
            rect("cover_panel_line", 9.85, 1.15, 2.85, .03, theme["background"])
            rect("cover_panel_line_2", 9.85, 6.25, 2.85, .03, theme["background"])
        elif variant == "center":
            rect("cover_top", 1.5, 1.5, 10.3, .035, accent)
            rect("cover_bottom", 1.5, 5.9, 10.3, .035, accent)
        else:
            rect("cover_rule", .85, 1.5, .65, .055, accent)
            rect("cover_edge", 12.55, .0, .78, HEIGHT, accent)
    elif layout_kind == "left_rail":
        rect("rail_rule", 4.5, 1, .012, 5.65, rule)
        rect("rail_accent", .85, .6, .6, .04, accent)
    else:
        rect("title_rule", .85, 2.36 if page.get("subtitle") else 1.96, .55, .035, accent)
        if family in ("grid", "portfolio"):
            rect("header_grid", 11.75, .4, .65, .045, accent)
        elif family == "bold":
            rect("bold_marker", .4, .6, .1, 1.05, accent)
    rect("footer_rule", .85, 7.03, 11.6, .009, rule)
    page_number = str(page.get("page_id", "")).replace("page-", "")
    if page_number:
        elements.append(text_element("page_number", page_number, 11.85, 7.12, .6, .23, 10, muted, minimum=10))
    slots = [p for p in layout["placeholders"] if p["type"] in ("text", "toc") and p["name"] not in ("subtitle", "caption")]
    for i, ph in enumerate(slots):
        if layout_kind == "cards_grid":
            base = rgb(theme["background"]); tint = rgb(theme["secondary"])
            color = "#" + "".join(f"{round(a*.92+b*.08):02x}" for a,b in zip(base,tint))
            rect(f"grid_panel_{i}", ph["x"]-.16, ph["y"]-.16, ph["w"]+.32, ph["h"]+.32, color)
        elif layout_kind == "stacked_rows":
            rect(f"row_marker_{i}", .85, ph["y"]+.08, .32, .04, accent)
        elif layout_kind == "timeline":
            rect(f"timeline_marker_{i}", ph["x"], ph["y"]-.35, .18, .18, accent)
            rect(f"timeline_line_{i}", ph["x"]+.22, ph["y"]-.26, max(.1, ph["w"]-.22), .012, rule)
    has_evidence = False
    for ph in layout["placeholders"]:
        x,y,w,h = (float(ph[k]) for k in ("x","y","w","h"))
        kind, name = ph["type"], ph["name"]
        if kind == "title":
            elements.append(text_element(name, page.get("title", ""), x,y,w,h,
                                         48 if family == "bold" and page_type == "cover" else 42 if page_type in ("cover", "thankyou") else 30,
                                         ink, True, 24, theme.get("fonts", {}).get("title", FONT_NAME)))
        elif name == "subtitle":
            elements.append(text_element(name, page.get("subtitle", ""), x,y,w,h, 18, muted))
        elif name == "caption":
            caption = "；".join("：".join(part for part in pair if part) for pair in items)
            elements.append(text_element(name, caption, x,y,w,h,18,ink))
        elif kind == "accent":
            rect(name, x,y,w,h,accent)
        elif kind in ("chart", "table"):
            data = page.get(kind+"_data")
            valid = valid_evidence(kind, data)
            if valid:
                elements.append(dict(kind=kind, name=name, x=x,y=y,w=w,h=h, data=data,
                                     color=ink, accent=accent, rule=rule, background=theme["background"],
                                     header_color="#17242C" if sum(rgb(accent)) > 420 else "#FFFFFF"))
                has_evidence = True
            elif not slots:
                slots.append({**ph, "type": "text"})
    if page_type not in ("cover", "thankyou"):
        for index, ph in enumerate(slots):
            # Contiguous groups keep reading order and headline/detail pairs together.
            start = len(items)*index // len(slots)
            stop = len(items)*(index+1) // len(slots)
            group = items[start:stop]
            if not group:
                continue
            x,y,w,h = (float(ph[k]) for k in ("x","y","w","h"))
            step = h / len(group)
            for j,(heading,detail) in enumerate(group):
                top = y+j*step
                label = f"{start+j+1:02d}  {heading}" if page_type == "toc" else heading
                if label:
                    title_h = min(max(.4, len(wrap(label,w,22,True))*22/72*1.3), step*.46) if detail else step*.8
                    heading_size = 30 if layout_kind == "statement" else 22
                    if layout_kind == "statement" and detail:
                        title_h = min(1.15, step*.4)
                    elements.append(text_element(f"{ph['name']}_heading_{j}", label, x,top,w,title_h,heading_size,accent,True,18))
                else:
                    title_h = 0
                if detail:
                    elements.append(text_element(f"{ph['name']}_detail_{j}", detail, x,top+title_h+.09,w,
                                                 max(.2,step-title_h-.17),18,ink,False,16))
            if layout_kind in ("two_column", "three_column") and index < len(slots)-1:
                rect(f"column_rule_{index}", x+w+.25,y,.009,h,rule)
    return dict(width=WIDTH, height=HEIGHT, background=theme["background"], elements=elements,
                evidence_rendered=has_evidence)


def valid_evidence(kind, data):
    if not isinstance(data, dict):
        return False
    if kind == "table":
        headers, rows = data.get("headers"), data.get("rows")
        return (isinstance(headers, list) and bool(headers) and isinstance(rows, list) and bool(rows)
                and all(isinstance(r, list) and len(r) == len(headers) for r in rows))
    payload = data.get("data") or {}
    if not isinstance(payload, dict):
        return False
    labels, values = payload.get("labels"), payload.get("values")
    return (isinstance(labels, list) and isinstance(values, list) and bool(labels)
            and len(labels) == len(values) and all(isinstance(v, (int,float)) for v in values))


def render_scene_png(scene, path):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (1600,900), rgb(scene["background"]))
    draw = ImageDraw.Draw(image)
    for element in scene["elements"]:
        e = element
        x,y,w,h = (e[k]*DPI for k in ("x","y","w","h"))
        if e["kind"] == "rect":
            draw.rectangle((x,y,x+w,y+max(1,h)), fill=rgb(e["color"]))
        elif e["kind"] == "text":
            selected = font(e["size"],e["bold"],e.get("font_name", FONT_NAME))
            for i,line in enumerate(e["text"].split("\n")):
                draw.text((x,y+i*e["size"]*DPI/72*e["line_height"]),line,
                          font=selected, fill=rgb(e["color"]), anchor="lt")
        elif e["kind"] == "table":
            rows = [e["data"]["headers"]]+e["data"]["rows"]
            cell_w, cell_h = w/len(rows[0]), h/len(rows)
            for ri,row in enumerate(rows):
                for ci,value in enumerate(row):
                    fill = e["accent"] if ri == 0 else e["background"]
                    draw.rectangle((x+ci*cell_w,y+ri*cell_h,x+(ci+1)*cell_w,y+(ri+1)*cell_h), fill=rgb(fill), outline=rgb(e["rule"]))
                    color = e["header_color"] if ri == 0 else e["color"]
                    for li,line in enumerate(wrap(str(value),cell_w/DPI-.2,16,ri==0)):
                        draw.text((x+ci*cell_w+12,y+ri*cell_h+12+li*35),line,font=font(16,ri==0),fill=rgb(color),anchor="lt")
        elif e["kind"] == "chart":
            data = e["data"]["data"]
            values,labels = data["values"],data["labels"]
            low,high = min(0,min(values)),max(0,max(values))
            span = high-low or 1
            baseline = y+h-.5*DPI-(-low/span)*(h-.9*DPI)
            draw.line((x,baseline,x+w,baseline),fill=rgb(e["rule"]),width=2)
            for i,(label,value) in enumerate(zip(labels,values)):
                bx = x+(i+.15)*w/len(values)
                bar_end = baseline-value/span*(h-.9*DPI)
                draw.rectangle((bx,min(baseline,bar_end),bx+.6*w/len(values),max(baseline,bar_end)),fill=rgb(e["accent"]))
                draw.text((bx,y+h-.32*DPI),str(label),font=font(12),fill=rgb(e["color"]),anchor="lt")
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    image.save(path)
    return str(path)
