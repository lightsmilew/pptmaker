import { Check } from 'lucide-react';
import { Button, NumberInput, Select, Textarea } from '@/components/ui';
import { useProjectStore } from '@/stores/projectStore';
import { useDesignCatalog } from '@/hooks/useDesignCatalog';
import type { DesignStyle } from '@/types/design';
import './design.css';
const audiences = ['通用','小学生','初中生','高中生','本科学生','研究生','企业领导','客户','投资人','技术人员'];
function StylePreview({ style, topic }: { style: DesignStyle; topic: string }) {
  return <div className={`direction-preview family-${style.family}`} style={{ background:style.background,color:style.text,'--slide-accent':style.primary,'--slide-secondary':style.secondary } as React.CSSProperties} aria-label={`${style.name}版式示意`}>
    <span className="preview-kicker">FOLIO / {style.category}</span><strong>{topic || '让每一个观点，\n找到自己的位置。'}</strong><div className="preview-rule" /><span className="preview-page">01 / EXPRESSION</span><span className="preview-edge" />
  </div>;
}
export function DesignControls({ maxPages = 50 }: { maxPages?: number }) {
  const draft = useProjectStore(s => s.draftSpec); const update = useProjectStore(s => s.setDraftSpec);
  const { catalog, error, retry } = useDesignCatalog();
  const automatic = !draft.style || draft.style==='自动';
  const selected = catalog?.styles.find(s => s.name === draft.style) || catalog?.styles[0];
  return <div className="direction-controls">
    <section className="direction-section" aria-labelledby="direction-basics"><div className="direction-label"><h2 id="direction-basics"><span>01</span>内容轮廓</h2><p>先决定要说多少，以及说给谁听。</p></div><div className="direction-basics">
      <NumberInput label="演示页数" aria-label="设置演示页数" min={1} max={maxPages} value={draft.page_count || 8} onValueChange={page_count => update({page_count})} />
      <Select label="目标受众" value={draft.audience || '通用'} onValueChange={audience => update({audience})} options={audiences.map(a => ({value:a,label:a === '通用' ? '通用受众' : a === '本科学生' ? '大学生' : a}))} />
      <Select label="内容密度" value={draft.content_density || 'balanced'} onValueChange={content_density => update({content_density:content_density as NonNullable<typeof draft.content_density>})} options={(catalog?.densities || [{id:'balanced',name:'适中'}]).map(d => ({value:d.id,label:d.name}))} />
    </div><div className="direction-checks">{([{key:'needs_cover',name:'封面'},{key:'needs_toc',name:'目录'},{key:'needs_summary',name:'总结'},{key:'needs_chart',name:'图表'}] as const).map(item => <label key={item.key}><input type="checkbox" checked={!!draft[item.key]} onChange={e => update({[item.key]:e.target.checked})} />{item.name}</label>)}<span>图表仅使用材料中已有的数据</span></div></section>
    <section className="direction-section" aria-labelledby="direction-style"><div className="direction-label"><h2 id="direction-style"><span>02</span>视觉风格</h2><p>{catalog ? `自动匹配内容，或从 ${catalog.styles.length} 种风格中选择。` : '正在打开风格目录…'}</p></div>
      {error ? <div className="direction-error" role="alert">{error}<Button size="sm" variant="outline" onClick={retry}>重新加载</Button></div> : !catalog ? <p role="status">正在加载风格…</p> : <div className="direction-style-grid"><div className="direction-style-list" role="group" aria-label="演示风格"><button className="direction-auto-option" aria-pressed={automatic} onClick={() => update({style:'自动'})}><span className="direction-swatch direction-auto-swatch">A</span><span><strong>自动</strong><small>根据内容选择主题</small></span>{automatic && <Check size={13} />}</button>{catalog.styles.map(style => <button key={style.name} aria-pressed={draft.style === style.name} onClick={() => update({style:style.name})}><span className="direction-swatch" style={{background:style.background,borderColor:style.primary}}><i style={{background:style.primary}} /><i style={{background:style.secondary}} /></span><span><strong>{style.name}</strong><small>{style.category}</small></span>{draft.style === style.name && <Check size={13} />}</button>)}</div>{automatic ? <div className="direction-preview-wrap"><div className="direction-auto-preview"><span className="preview-kicker">FOLIO / FIND YOUR EXPRESSION</span><strong>内容的气质，<br />决定表达的样子。</strong><span className="direction-auto-rule" /><small>自动选择 · 16 种主题</small></div><div className="direction-preview-caption"><strong>自动</strong><span>默认方案</span></div><p>结合内容、受众与语气，分析并选择合适的主题。</p><small>主题选择与需求整理一次完成，生成后可查看选择结果。</small></div> : selected && <div className="direction-preview-wrap"><StylePreview style={selected} topic={draft.topic} /><div className="direction-preview-caption"><strong>{selected.name}</strong><span>版式示意</span></div><p>{selected.description}</p><small>实际页面会随内容与编排方式变化。</small></div>}</div>}
      <div className="direction-checks"><label><input type="checkbox" checked={draft.auto_images !== false} onChange={e=>update({auto_images:e.target.checked})} />自动配图</label><span>按内容选用主题图片，保留版式留白{catalog?.illustrations ? ` · ${catalog.illustrations.count} 张精选图片` : ""}</span></div>
    </section>
    <section className="direction-section" aria-labelledby="direction-layout"><div className="direction-label"><h2 id="direction-layout"><span>03</span>编排方式</h2><p>让页面有节奏，也让阅读更轻松。</p></div><div className="direction-layout-list">{catalog?.layout_modes.map(mode => <button key={mode.id} aria-pressed={(draft.layout_mode || 'auto') === mode.id} onClick={() => update({layout_mode:mode.id})}><span className={`layout-glyph glyph-${mode.id}`} aria-hidden="true"><i /><i /><i /></span><strong>{mode.name}</strong><small>{mode.description}</small>{(draft.layout_mode || 'auto') === mode.id && <Check size={13} />}</button>)}</div><p className="direction-mode-note">对比、流程、图表与表格优先使用适合内容的结构。{catalog?.densities.find(d => d.id === (draft.content_density || 'balanced'))?.description}</p></section>
    <section className="direction-section direction-notes"><div className="direction-label"><h2><span>04</span>补充要求</h2><p>选填，告诉 Folio 你的偏好。</p></div><Textarea aria-label="补充要求" rows={2} maxLength={4000} placeholder="例如：强调对比，语言简洁，保留材料中的数字与结论。" value={draft.notes || ''} onChange={e => update({notes:e.target.value})} /></section>
  </div>;
}
