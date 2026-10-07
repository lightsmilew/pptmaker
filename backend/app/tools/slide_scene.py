"""Shared slide composition for editable PPTX and PNG previews.

Geometry is in inches, typography in points. Text is measured once and the same
explicit line breaks are used by both renderers. No model-generated drawing code.
"""

from copy import deepcopy
from functools import lru_cache
from pathlib import Path

WIDTH, HEIGHT, DPI = 13.333, 7.5, 120
FONT_NAME = "Microsoft YaHei"
PALETTES = {
    "商务简约": ("#29483E", "#75877E", "#202B26", "#FAF9F6"),
    "学术简约": ("#234B70", "#6F899F", "#202C38", "#FAFBFC"),
    "科技风": ("#9ECDBD", "#759FCA", "#EDF3F5", "#17242C"),
    "创意活泼": ("#A3432A", "#D39C67", "#392820", "#FFF8EE"),
    "教育培训": ("#356052", "#92AA91", "#243B31", "#F5F8F2"),
    "金融专业": ("#253D50", "#998865", "#25313B", "#FAF9F5"),
}
ALIASES = {"简约商务": "商务简约", "简约专业": "商务简约", "商务正式": "金融专业"}


def get_theme(style="商务简约"):
    primary, secondary, text, background = PALETTES.get(ALIASES.get(style, style), PALETTES["商务简约"])
    return dict(primary=primary, secondary=secondary, accent=primary, text=text, background=background,
                fonts=dict(title=FONT_NAME, body=FONT_NAME))


def rgb(value):
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return tuple(int(value.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=128)
def font(size, bold=False):
    from PIL import ImageFont
    candidates = [Path("C:/Windows/Fonts") / ("msyhbd.ttc" if bold else "msyh.ttc"),
                  Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), max(1, round(size * DPI / 72)))
    return ImageFont.load_default()


def wrap(text, width, size, bold=False):
    """Character wrapping supports Chinese and Latin; prefers word boundaries."""
    selected = font(size, bold)
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


def text_element(name, text, x, y, w, h, size=20, color="#202B26", bold=False, minimum=16):
    size = float(size)
    while size > minimum:
        lines = wrap(text, w, size, bold)
        if len(lines) * size / 72 * 1.3 <= h:
            break
        size -= 1
    lines = wrap(text, w, size, bold)
    return dict(kind="text", name=name, text="\n".join(lines), x=x, y=y, w=w, h=h,
                size=size, color=color, bold=bold, line_height=1.3,
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


def template_layout(page_type, count=3, subtitle=True, suggested=""):
    if page_type in ("cover", "thankyou"):
        kind = "cover"
        regions = [("title", "title", .8, 2.0, 9.5, 1.7), ("subtitle", "text", .85, 4.0, 8.8, 1.3)]
    else:
        kind = "toc" if page_type == "toc" else "title_content"
        regions = [("title", "title", .8, .6, 11.7, 1.2)]
        if subtitle:
            regions.append(("subtitle", "text", .85, 1.82, 11.5, .5))
        top = 2.6 if subtitle else 2.2
        if page_type == "table":
            regions.append(("table", "table", .85, top, 11.6, (5.1 if count else 6.65)-top))
            if count:
                regions.append(("caption", "text", .85, 5.35, 11.6, 1.3))
            kind = "title_content"
        elif page_type == "chart":
            regions.extend([("chart", "chart", .85, top, 7.4, 6.65-top),
                            ("content", "text", 8.7, top, 3.8, 6.65-top)])
            kind = "chart_content"
        elif page_type != "toc" and (count > 3 or suggested in ("two_column", "comparison", "左右双栏")):
            kind = "two_column"
            regions.extend([("content_1", "text", .85, top, 5.45, 6.65-top),
                            ("content_2", "text", 7.0, top, 5.45, 6.65-top)])
        elif page_type != "toc" and count == 3:
            kind = "three_column"
            regions.extend([(f"content_{i+1}", "text", .85+i*4.05, top, 3.5, 6.65-top) for i in range(3)])
        else:
            regions.append(("content", "text", .85, top, 11.6, 6.65-top))
    return dict(layout_id="editorial-"+kind, layout_type=kind, template_version=2,
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
    dark = sum(rgb(theme["background"])) < 320
    muted, rule = ("#BBCBC8", "#41514F") if dark else ("#6E7972", "#D8DDD7")
    def rect(name, x,y,w,h,color):
        elements.append(dict(kind="rect", name=name, x=x,y=y,w=w,h=h,color=color))
    if page_type in ("cover", "thankyou"):
        rect("cover_rule", .85, 1.5, .65, .055, accent)
        rect("cover_edge", 12.55, .0, .78, HEIGHT, accent)
    else:
        rect("title_rule", .85, 2.36 if page.get("subtitle") else 1.96, .55, .035, accent)
    rect("footer_rule", .85, 7.03, 11.6, .009, rule)
    page_number = str(page.get("page_id", "")).replace("page-", "")
    if page_number:
        elements.append(text_element("page_number", page_number, 11.85, 7.12, .6, .23, 10, muted, minimum=10))
    slots = [p for p in layout["placeholders"] if p["type"] in ("text", "toc") and p["name"] not in ("subtitle", "caption")]
    has_evidence = False
    for ph in layout["placeholders"]:
        x,y,w,h = (float(ph[k]) for k in ("x","y","w","h"))
        kind, name = ph["type"], ph["name"]
        if kind == "title":
            elements.append(text_element(name, page.get("title", ""), x,y,w,h,
                                         42 if page_type in ("cover", "thankyou") else 30, ink, True, 24))
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
                    title_h = min(.88 if w < 6 else .55, step*.46) if detail else step*.8
                    elements.append(text_element(f"{ph['name']}_heading_{j}", label, x,top,w,title_h,22,accent,True,18))
                else:
                    title_h = 0
                if detail:
                    elements.append(text_element(f"{ph['name']}_detail_{j}", detail, x,top+title_h+.12,w,
                                                 max(.2,step-title_h-.24),18,ink,False,16))
            if len(slots) > 1 and index < len(slots)-1:
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
            selected = font(e["size"],e["bold"])
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
