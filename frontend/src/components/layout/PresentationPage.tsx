import { useState } from 'react';
import { ArrowLeft, ChevronLeft, ChevronRight, Download, Play, RefreshCw } from 'lucide-react';
import { Button, Badge } from '@/components/ui';
import { StepIndicator, type Step } from './StepIndicator';
import { PageCard, PPTPreview } from '@/components/preview';
import { OutlinePreview } from '@/components/preview/OutlinePreview';
import type { PPTProject } from '@/types';
import { isBusy, statusLabels } from './pageUtils';

export function PresentationPage({ project, selectedIndex, onSelect, onDownload, onResume, onWorkspace, downloading, downloadUrl, error, scheduling = false }: {
  project: PPTProject; selectedIndex: number; onSelect: (index: number) => void; onDownload: () => void; onResume: () => void; onWorkspace: () => void;
  downloading: boolean; downloadUrl: string | null; error: string | null;
  scheduling?: boolean;
}) {
  const [tab,setTab] = useState<'preview' | 'notes' | 'content'>('preview');
  const pages = project.pages || []; const outline = project.outline || [];
  const selected = pages[selectedIndex] || null; const total = pages.length || outline.length;
  const completed = pages.filter(p => p.status === 'completed').length;
  const busy = scheduling || isBusy(project.status);
  const step: Step = ['completed','rendering','editing'].includes(project.status) ? 'export' : pages.some(p => p.status !== 'pending') || project.status === 'generating' ? 'generate' : outline.length || project.status === 'planning' ? 'plan' : 'input';
  return <>
    <button className="text-link back-link" onClick={onWorkspace}><ArrowLeft size={14} />我的工作空间</button>
    <div className="page-heading-row presentation-heading"><div className="studio-heading"><p className="eyebrow">YOUR IDEAS, UNFOLDED</p><h1>{project.spec.topic || '正在整理你的想法…'}</h1><p>{project.spec.style} · 面向{project.spec.audience || '通用受众'} · {total || project.spec.page_count} 页</p></div><div className="heading-actions"><Badge variant={project.status === 'failed' ? 'error' : project.status === 'completed' ? 'success' : 'default'}>{statusLabels[project.status]}</Badge>{downloadUrl && project.status === 'completed' ? <Button onClick={onDownload} isLoading={downloading}><Download size={15} />下载 PowerPoint</Button> : !busy && <Button onClick={onResume} isLoading={downloading}>{project.status === 'failed' ? <RefreshCw size={15} /> : <Play size={15} />}{project.status === 'editing' ? '重新导出' : project.status === 'failed' ? '重新制作' : '继续制作'}</Button>}</div></div>
    <StepIndicator currentStep={step} progress={project.status === 'completed' ? 100 : Math.min(99, project.progress || 0)} />
    {(error || project.error) && <p className="studio-error presentation-error" role="alert">{error || project.error}</p>}
    {busy && <div className="generation-status" role="status"><span className="status-dot" /><div><strong>{project.current_step || statusLabels[project.status]}</strong><small>已完成 {completed} / {total || project.spec.page_count || 0} 页 · 可以切换页面查看已生成内容</small></div><span>{Math.min(99,Math.round(project.progress || 0))}%</span></div>}
    <div className="presentation-editor"><aside className="slide-list"><div className="slide-list-heading"><h2>页面</h2><span>{total} 页</span></div>{pages.length ? pages.map((page,index) => <PageCard key={page.page_id} page={page} isSelected={index === selectedIndex} onClick={() => onSelect(index)} />) : outline.length ? outline.map((item,index) => <button key={item.page_id} className={`outline-list-item ${index === selectedIndex ? 'selected' : ''}`} onClick={() => onSelect(index)}><span>{String(index+1).padStart(2,'0')}</span>{item.page_title}</button>) : <p className="slide-list-empty">大纲就绪后，页面会出现在这里。</p>}</aside>
      <section className="slide-stage" aria-label="演示预览"><div className="slide-stage-toolbar"><div className="preview-tabs" role="group" aria-label="查看内容">{([{ id:'preview',label:'幻灯片' },{ id:'content',label:'页面内容' },{ id:'notes',label:'演讲备注' }] as const).map(item => <button key={item.id} aria-pressed={tab === item.id} onClick={() => setTab(item.id)} className={tab === item.id ? 'active' : ''}>{item.label}</button>)}</div><span>{total ? `${selectedIndex+1} / ${total}` : '等待大纲'}</span></div><div className="slide-stage-canvas">{tab === 'preview' ? selected ? <PPTPreview page={selected} /> : <OutlinePreview outline={outline} selectedIndex={selectedIndex} /> : <div className="slide-text-view"><span className="eyebrow">{tab === 'notes' ? 'SPEAKER NOTES' : 'PAGE CONTENT'}</span><h2>{selected?.content.title || outline[selectedIndex]?.page_title || '等待内容'}</h2>{tab === 'notes' ? <p>{selected?.content.speaker_notes || '这一页还没有演讲备注。'}</p> : <><p>{selected?.content.subtitle}</p><ul>{(selected?.content.key_points || outline[selectedIndex]?.key_points || []).map((point,i) => <li key={i}>{point}</li>)}</ul></>}</div>}</div><div className="slide-stage-footer"><span>{selected?.review ? `${selected.review.method === 'vision' ? '视觉复核' : '排版检查'} ${selected.review.score} 分` : busy ? '页面生成后，会进行排版检查。' : '可在 PowerPoint 中继续编辑。'}</span><div><button className="icon-button" aria-label="上一张幻灯片" disabled={selectedIndex <= 0} onClick={() => onSelect(selectedIndex-1)}><ChevronLeft size={17} /></button><button className="icon-button" aria-label="下一张幻灯片" disabled={selectedIndex >= total-1} onClick={() => onSelect(selectedIndex+1)}><ChevronRight size={17} /></button></div></div></section>
    </div><p className="page-footnote">预览与导出共享版式。图表轴线、字体和表格细节可能随 PowerPoint 环境有所差异。</p>
  </>;
}
