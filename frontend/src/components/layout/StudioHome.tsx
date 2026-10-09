import { ArrowUpRight, Check, FileText } from 'lucide-react';
import { InputPanel } from '@/components/input';
import { useExamples, useProjectStore } from '@/stores/projectStore';
import type { PPTProjectSpec } from '@/types';

const themes = [
  { name: '商务简约', label: 'Editorial', note: '温润纸白 · 墨绿', color: '#29483e', paper: '#faf9f6', title: '让想法，\n有条理地呈现。', variant: 'editorial' },
  { name: '学术简约', label: 'Research', note: '清晰结构 · 学术蓝', color: '#234b70', paper: '#fafbfc', title: '研究的价值，\n始于清晰表达。', variant: 'research' },
  { name: '科技风', label: 'Midnight', note: '深色画布 · 冷静留白', color: '#9ecdbd', paper: '#17242c', title: '下一步，\n从这里开始。', variant: 'midnight' },
];

interface Props {
  onSubmit: (input: string, spec: PPTProjectSpec) => void;
  onExample: (example: ReturnType<typeof useExamples>[number]) => void;
  isLoading: boolean;
  error: string | null;
  onSettings: () => void;
}

export function StudioHome({ onSubmit, onExample, onSettings, isLoading, error }: Props) {
  const draft = useProjectStore(s => s.draftSpec);
  const setDraft = useProjectStore(s => s.setDraftSpec);
  const selectedStyle = draft.style || '商务简约';
  return <>
            <div className="studio-heading"><p className="eyebrow"><span />A SPACE FOR YOUR IDEAS</p><h1>好内容，值得好好呈现。</h1><p>从一段想法、一份文档开始，做一份清晰、耐看的演示文稿。</p></div>
            <div className="studio-workbench">
              <section className="brief-section" aria-labelledby="brief-heading"><div className="section-heading"><h2 id="brief-heading"><span className="section-index">01</span>写下你的内容</h2><span>想法的起点</span></div><InputPanel mode="content" onSubmit={onSubmit} isLoading={isLoading} />{error && <p role="alert" className="studio-error">{error}</p>}</section>
              <aside className="workbench-aside"><div className="aside-label">从内容到演示</div><h3>每一页，<br />都有自己的重点。</h3><p>整理结构，提炼要点。<br />让多样的版式，围绕内容展开。</p><ol><li><span>1</span>写下想法或上传文档</li><li><span>2</span>选择适合内容的风格</li><li><span>3</span>预览并下载 PowerPoint</li></ol><div className="aside-footer"><FileText size={16} /><span>可编辑的 .pptx 文件</span><ArrowUpRight size={16} /></div></aside>
            </div>
            <section className="theme-section" aria-labelledby="theme-heading"><div className="section-heading"><h2 id="theme-heading"><span className="section-index">02</span>选一种表达方式</h2><button className="text-link" onClick={onSettings}>创作方案 · 16 种风格 <ArrowUpRight size={14} /></button></div><div className="theme-grid">{themes.map((theme, i) => <button key={theme.name} disabled={isLoading} aria-pressed={selectedStyle === theme.name} className={`theme-option ${selectedStyle === theme.name ? 'selected' : ''}`} onClick={() => setDraft({ style: theme.name })}>
              <div className={`theme-art ${theme.variant}`} style={{ background: theme.paper, color: theme.color }}><span className="theme-art-kicker">{theme.label.toUpperCase()} / 0{i+1}</span><strong>{theme.title}</strong><div className="theme-art-rule" /><span className="theme-art-number">0{i+1}</span>{theme.variant === 'research' && <div className="mini-columns"><span /><span /><span /></div>}</div>
              <div className="theme-caption"><div><strong>{theme.name}</strong><span>{theme.note}</span></div><span className="theme-check">{selectedStyle === theme.name ? <Check size={14} /> : <ArrowUpRight size={15} />}</span></div>
            </button>)}</div></section>
            <section className="starter-section"><div className="section-heading"><h2>还没有想法？从一个示例开始。</h2></div><div className="starter-list">{useExamples().map((example, i) => <button key={example.title} disabled={isLoading} onClick={() => onExample(example)}><span className="starter-number">0{i+1}</span><span><strong>{example.title}</strong><small>{example.description}</small></span><span className="starter-pages">{example.spec.page_count} 页</span><ArrowUpRight size={17} /></button>)}</div></section>
  </>;
}
