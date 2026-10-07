"""Generate deterministic design samples without API calls.

Run from the repository root: python scripts/preview_styles.py
"""

import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from app.tools.slide_scene import build_scene, get_theme, render_scene_png
from app.tools.pptx_generator import PPTXGenerator
from app.tools.slide_quality import review_scene

pages = [
    dict(page_id="page-01",page_type="cover",title="清晰表达，从结构开始",subtitle="演示设计参考\n用一致的层级与留白，让内容自然展开。"),
    dict(page_id="page-02",page_type="content",title="先整理结构，再讲清重点",subtitle="每一页聚焦一个主题，让标题与说明形成清晰的层级",
         key_points=["明确主题","建立顺序","保留证据"],
         bullet_points=["说明演示的对象、听众和目的，减少无关的背景介绍。","按照听众理解信息的顺序组织内容，每一页都回答一个具体问题。","保留原文中的数据与结论，不补充没有依据的事实。"]),
    dict(page_id="page-03",page_type="content",title="让内容有层次，也有呼吸感",subtitle="用四个清晰的判断，检查页面的信息组织",
         key_points=["标题指向具体内容","解释紧贴核心观点","段落保持阅读顺序","统一字体与色彩"],
         bullet_points=["读完标题，就能知道本页讨论的对象和范围。","短标题下保留原因、例子与必要的说明。","同组内容放在一起，按从左到右、从上到下阅读。","通过字号、字重与留白建立层级，减少装饰。"]),
    dict(page_id="page-04",page_type="table",title="在同一尺度下比较",subtitle="示例表格：内容与布局的职责",
         table_data={"headers":["任务","负责方式","作用"],"rows":[["内容提炼","语言模型","根据来源组织观点"],["视觉排版","本地模板","稳定的层级与间距"],["质量检查","本地规则","定位溢出与重叠"]]}),
]

if __name__ == "__main__":
    output=Path("storage/design_samples")
    output.mkdir(parents=True,exist_ok=True)
    for style in ("商务简约","学术简约","科技风"):
        theme=get_theme(style)
        for page in pages:
            scene=build_scene(page,theme)
            render_scene_png(scene,output/f"{style}-{page['page_id']}.png")
            result=review_scene(page,style)
            if result["issues"]:
                raise RuntimeError(f"{style} {page['page_id']}: {result['issues']}")
        PPTXGenerator().generate(pages,str(output/f"{style}.pptx"),"演示设计参考",theme)
    print(str(output.resolve()))
