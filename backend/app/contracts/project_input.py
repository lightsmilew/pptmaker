"""Apply the same settings boundary to HTTP creation and WebSocket edits."""

SPEC_FIELDS = {"topic","audience","page_count","style","needs_cover","needs_toc","needs_summary","needs_chart","notes","layout_mode","content_density"}


def validate_spec(spec):
    if spec is None:
        return spec
    if not isinstance(spec, dict) or set(spec) - SPEC_FIELDS:
        raise ValueError("演示设置包含不支持的字段")
    count = spec.get("page_count")
    if count is not None and (type(count) is not int or not 1 <= count <= 50):
        raise ValueError("演示页数需为1至50的整数")
    for key in ("needs_cover","needs_toc","needs_summary","needs_chart"):
        if key in spec and type(spec[key]) is not bool:
            raise ValueError("内容选项需为布尔值")
    for key,limit in (("topic",500),("audience",200),("style",60),("notes",4000)):
        if key in spec and (not isinstance(spec[key],str) or len(spec[key]) > limit):
            raise ValueError(f"{key} 字段长度或类型无效")
    for key, allowed in (("layout_mode", {"auto", "editorial", "structured", "spotlight"}),
                         ("content_density", {"airy", "balanced", "compact"})):
        if key in spec and (not isinstance(spec[key], str) or spec[key] not in allowed):
            raise ValueError(f"{key} 选项无效")
    if "style" in spec:
        from ..tools.design_catalog import STYLE_NAMES
        from ..tools.slide_scene import ALIASES
        if spec["style"] not in STYLE_NAMES | set(ALIASES):
            raise ValueError("请选择目录中的演示风格")
    return spec
