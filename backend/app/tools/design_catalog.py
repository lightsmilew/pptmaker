"""Built-in, editable slide directions; shared by the API and renderers."""

# References describe design vocabulary, never third-party template assets.
# See docs/TEMPLATE_REFERENCES.md for the source galleries and implementation.
STYLE_DEFINITIONS = [
    ("商务简约", "清晰汇报", "克制留白与墨绿强调", "editorial", "#29483E", "#75877E", "#202B26", "#FAF9F6"),
    ("学术简约", "研究分享", "蓝灰层次与规整结构", "grid", "#234B70", "#6F899F", "#202C38", "#FAFBFC"),
    ("科技风", "技术发布", "深色舞台与冷色重点", "dark", "#9ECDBD", "#759FCA", "#EDF3F5", "#17242C"),
    ("创意活泼", "创意提案", "暖色撞色与轻快节奏", "playful", "#A3432A", "#D39C67", "#392820", "#FFF8EE"),
    ("教育培训", "课程教学", "舒展分区与柔和绿意", "nature", "#356052", "#92AA91", "#243B31", "#F5F8F2"),
    ("金融专业", "数据汇报", "藏蓝基调与细金线", "grid", "#253D50", "#998865", "#25313B", "#FAF9F5"),
    ("杂志编辑", "品牌叙事", "衬线标题与侧栏叙事", "editorial", "#803C2F", "#A28A70", "#302823", "#F6F1E8"),
    ("极简黑白", "观点表达", "单色层级与大胆留白", "minimal", "#252525", "#767676", "#242424", "#FCFCFA"),
    ("瑞士网格", "设计提案", "严谨网格与红色标记", "grid", "#A52821", "#696C70", "#252629", "#F8F8F5"),
    ("暖调人文", "文化分享", "沙色纸感与柔和衬线", "warm", "#78533C", "#B19775", "#352D27", "#FAF3E8"),
    ("自然清新", "可持续主题", "浅绿底色与自然节奏", "nature", "#3C5E35", "#7D9063", "#283B25", "#F0F4E8"),
    ("建筑作品集", "方案展示", "石灰底色与精细线框", "portfolio", "#494D48", "#8A7A64", "#2C302B", "#F1F0EB"),
    ("复古印刷", "文化创意", "奶油纸色与深红印记", "retro", "#8D322D", "#A17D43", "#352820", "#F5EEDB"),
    ("柔和彩色", "轻松分享", "低饱和配色与模块编排", "playful", "#674747", "#8C9D87", "#352E34", "#FFF6F3"),
    ("大胆宣言", "路演开场", "大字标题与强烈色块", "bold", "#AF4018", "#7D6757", "#28221E", "#FFF3DB"),
    ("深海蓝金", "高端提案", "深蓝画布与金色线条", "dark", "#D6B76F", "#86A9B8", "#F0F3F4", "#162C3A"),
]
STYLE_NAMES = {row[0] for row in STYLE_DEFINITIONS}
LAYOUT_MODES = [
    dict(id="auto", name="自动编排", description="按内容选择，交替使用多种版式"),
    dict(id="editorial", name="编辑叙事", description="侧栏标题、分段内容与舒展留白"),
    dict(id="structured", name="规整网格", description="双栏、三栏与模块网格"),
    dict(id="spotlight", name="重点聚焦", description="突出少量结论，逐点展开"),
]
DENSITIES = [dict(id="airy", name="舒展", description="少量重点，简短解释"),
             dict(id="balanced", name="适中", description="兼顾要点与解释"),
             dict(id="compact", name="充实", description="保留更多细节")]


def catalog():
    return dict(styles=[dict(name=name, category=category, description=description,
                            family=family, primary=primary, secondary=secondary,
                            text=text, background=background)
                        for name, category, description, family, primary, secondary, text, background in STYLE_DEFINITIONS],
                layout_modes=LAYOUT_MODES, densities=DENSITIES)
