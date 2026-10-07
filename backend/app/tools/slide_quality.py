"""Deterministic geometry/text checks, explicitly separate from image review."""

from .slide_scene import build_scene, get_theme, rgb, valid_evidence, wrap


def contrast(first, second):
    def luminance(color):
        components = [v/255 for v in rgb(color)]
        components = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in components]
        return sum(v*w for v,w in zip(components,(.2126,.7152,.0722)))
    values = sorted([luminance(first), luminance(second)])
    return (values[1]+.05)/(values[0]+.05)


def review_scene(page, style="商务简约"):
    scene = build_scene(page, get_theme(style))
    issues = []
    def issue(category, target, description, owner="layout"):
        issues.append(dict(issue_id=f"local-{len(issues)+1}",category=category,severity="high",
                           target=target,description=description,owner=owner,
                           suggested_action="精简文字并保留关键证据" if owner == "content" else "调整位置、尺寸或文字对比度"))
    text_boxes = []
    for e in scene["elements"]:
        if e["x"] < 0 or e["y"] < 0 or e["x"]+e["w"] > scene["width"]+.01 or e["y"]+e["h"] > scene["height"]+.01:
            issue("overflow",e["name"],"元素超出画布")
        if e["kind"] == "text" and e["text"]:
            text_boxes.append(e)
            if e["overflow"]:
                issue("overflow",e["name"],"文字超出可用区域", "content")
            if contrast(e["color"],scene["background"]) < 3:
                issue("contrast",e["name"],"文字与背景的对比度不足")
        elif e["kind"] == "table":
            rows = [e["data"]["headers"]] + e["data"]["rows"]
            cell_w,cell_h = e["w"]/len(rows[0]), e["h"]/len(rows)
            if any(len(wrap(str(value),cell_w-.2,16))*16/72*1.3 > cell_h-.2 for row in rows for value in row):
                issue("overflow",e["name"],"表格文字过多，需减少行列或精简内容", "content")
    for i,a in enumerate(text_boxes):
        for b in text_boxes[i+1:]:
            if min(a["x"]+a["w"],b["x"]+b["w"]) > max(a["x"],b["x"])+.02 and min(a["y"]+a["h"],b["y"]+b["h"]) > max(a["y"],b["y"])+.02:
                issue("overlap",a["name"],f"与 {b['name']} 的文字区域重叠")
    return dict(status="needs_revision" if issues else "approved",
                score=max(0,100-20*len(issues)),dimensions={},issues=issues,
                review_method="local_geometry", next_action="revise_content" if any(i["owner"] == "content" for i in issues)
                else ("revise_layout" if issues else "approve"))
