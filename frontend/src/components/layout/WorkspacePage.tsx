import { useEffect, useRef, useState } from 'react';
import { Archive, ArrowUpRight, Check, Download, FileText, FolderOpen, Plus, RotateCcw, Search, Star, X, Pencil } from 'lucide-react';
import { Button, Input, Select, Badge } from '@/components/ui';
import { api } from '@/api/client';
import type { PresentationSummary, ProjectList, WorkspaceOverview } from '@/types/workspace';
import { dateLabel, downloadFile, numberLabel, statusLabels } from './pageUtils';
import toast from 'react-hot-toast';

const filters = [{ id: 'all', label: '全部演示' }, { id: 'favorites', label: '收藏' }, { id: 'completed', label: '已完成' }, { id: 'draft', label: '进行中' }, { id: 'failed', label: '需重试' }, { id: 'archived', label: '已归档' }];
export function WorkspacePage({ onOpen, onNew }: { onOpen: (id: string) => void; onNew: () => void }) {
  const [overview, setOverview] = useState<WorkspaceOverview | null>(null);
  const [list, setList] = useState<ProjectList | null>(null);
  const [query, setQuery] = useState(''); const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all'); const [sort, setSort] = useState('updated');
  const [page, setPage] = useState(1); const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const [mutating, setMutating] = useState<string | null>(null);
  const [editing, setEditing] = useState<PresentationSummary | null>(null);
  const [title, setTitle] = useState(''); const [tags, setTags] = useState('');
  const editorRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (editing) { editorRef.current?.scrollIntoView?.({ behavior:'smooth',block:'center' }); editorRef.current?.querySelector('input')?.focus(); } }, [editing]);
  useEffect(() => { const timer = window.setTimeout(() => { setSearch(query.trim()); setPage(1); }, 250); return () => clearTimeout(timer); }, [query]);
  useEffect(() => {
    let current = true; setLoading(true); setError('');
    Promise.all([api.getWorkspace(), api.listProjects({ q: search, status: ['completed','draft','failed'].includes(filter) ? filter : 'all', ...(filter === 'favorites' ? { favorite: true } : {}), archived: filter === 'archived', sort, page, page_size: 12 })])
      .then(([stats, data]) => { if (!current) return; setOverview(stats); if (page > 1 && !data.projects.length) setPage(page - 1); else setList(data); })
      .catch(e => { if (current) setError(e.message); }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [search, filter, sort, page, revision]);
  const update = async (item: PresentationSummary, patch: Parameters<typeof api.updateMetadata>[1]) => {
    setMutating(item.id);
    try { await api.updateMetadata(item.id, patch); setEditing(null); setRevision(r => r + 1); }
    catch (e) { toast.error((e as Error).message); } finally { setMutating(null); }
  };
  const download = async (item: PresentationSummary) => {
    if (!item.download_url) return; setMutating(item.id);
    try { await downloadFile(item.download_url, item.title); } catch (e) { toast.error((e as Error).message); } finally { setMutating(null); }
  };
  return <>
    <div className="page-heading-row"><div className="studio-heading"><p className="eyebrow">YOUR COLLECTION</p><h1>每一次表达，都有迹可循。</h1><p>你的作品与正在展开的想法，都在这里。</p></div><Button onClick={onNew}><Plus size={15} />新建演示</Button></div>
    <div className="workspace-stats">{[{ label: '演示文稿', value: overview?.stats.total }, { label: '已完成', value: overview?.stats.completed }, { label: '已收藏', value: overview?.stats.favorites }, { label: '已生成页面', value: overview?.stats.pages }].map(item => <div key={item.label}><span>{item.label}</span><strong>{item.value === undefined ? '—' : numberLabel(item.value)}</strong></div>)}</div>
    <section className="collection-panel" aria-label="历史演示">
      <div className="collection-toolbar"><div className="search-field"><Search size={16} /><Input aria-label="搜索演示" placeholder="搜索标题、受众或标签" value={query} onChange={e => setQuery(e.target.value)} /></div><Select aria-label="排序方式" value={sort} onValueChange={value => { setSort(value); setPage(1); }} options={[{ value: 'updated', label: '最近更新' }, { value: 'created', label: '最近创建' }, { value: 'title', label: '按标题排序' }]} /><button className="icon-button" aria-label="刷新工作空间" onClick={() => setRevision(r => r + 1)}><RotateCcw size={16} /></button></div>
      <div className="filter-tabs" role="group" aria-label="筛选历史">{filters.map(item => <button key={item.id} aria-pressed={filter === item.id} className={filter === item.id ? 'active' : ''} onClick={() => { setFilter(item.id); setPage(1); }}>{item.label}</button>)}</div>
      {error ? <div className="empty-state" role="alert"><p>{error}</p><Button variant="outline" onClick={() => setRevision(r => r + 1)}>重新加载</Button></div> : loading ? <div className="empty-state" role="status">正在整理你的演示…</div> : !list?.projects.length ? <div className="empty-state"><FolderOpen size={30} strokeWidth={1.2} /><h2>{search ? '还没有匹配的演示。' : filter === 'all' ? '你的第一份演示，从这里开始。' : '这里暂时没有演示。'}</h2><p>{search ? '试试其他关键词或筛选条件。' : '从主题、听众和关键观点开始，制作你的第一份演示。'}</p>{filter === 'all' && !search && <Button variant="outline" onClick={onNew}>写下一个想法 <ArrowUpRight size={15} /></Button>}</div> : <>
        <div className="presentation-grid">{list.projects.map(item => <article key={item.id} className="presentation-card">
          <button className="presentation-cover" aria-label={`打开 ${item.title}`} onClick={() => onOpen(item.id)}><div className="cover-placeholder"><FileText size={23} strokeWidth={1.2} /><strong>{item.title}</strong><span>{item.style} / {item.page_count} 页</span></div>{item.preview_url && <img src={item.preview_url} alt={`${item.title}封面`} loading="lazy" onError={e => { e.currentTarget.hidden = true; }} />}<span className="cover-open"><ArrowUpRight size={18} /></span></button>
          <div className="presentation-card-body"><div className="card-title-row"><button className="presentation-title" onClick={() => onOpen(item.id)} title={item.title}>{item.title}</button><button className={`icon-button favorite ${item.favorite ? 'selected' : ''}`} aria-label={`${item.favorite ? '取消收藏' : '收藏'} ${item.title}`} aria-pressed={item.favorite} disabled={mutating === item.id} onClick={() => update(item, { favorite: !item.favorite })}><Star size={15} fill={item.favorite ? 'currentColor' : 'none'} /></button></div>
          <p className="presentation-meta">{item.page_count} 页<span>·</span>{item.style}<span>·</span>{item.audience}</p>
          {item.tags.length > 0 && <div className="tag-list">{item.tags.map(tag => <span key={tag}>{tag}</span>)}</div>}
          <div className="presentation-card-footer"><div><Badge variant={item.status === 'failed' ? 'error' : item.status === 'completed' ? 'success' : 'default'}>{statusLabels[item.status] || item.status}</Badge><small>{dateLabel(item.updated_at)}</small></div><div className="card-actions"><button className="icon-button" aria-label={`编辑资料 ${item.title}`} onClick={() => { setEditing(item); setTitle(item.title); setTags(item.tags.join('，')); }}><Pencil size={14} /></button>{item.download_url && <button className="icon-button" aria-label={`下载 ${item.title}`} disabled={mutating === item.id} onClick={() => download(item)}><Download size={15} /></button>}<button className="icon-button" disabled={mutating === item.id} aria-label={`${item.archived ? '恢复' : '归档'} ${item.title}`} onClick={() => update(item, { archived: !item.archived })}>{item.archived ? <RotateCcw size={15} /> : <Archive size={15} />}</button></div></div></div>
        </article>)}</div>
        <div className="pagination"><span>{list.total} 份演示 · 第 {page} / {Math.max(1, Math.ceil(list.total / 12))} 页</span><div><Button size="sm" variant="ghost" disabled={page === 1} onClick={() => setPage(page - 1)}>上一页</Button><Button size="sm" variant="ghost" disabled={page * 12 >= list.total} onClick={() => setPage(page + 1)}>下一页</Button></div></div>
      </>}
    </section>
    {editing && <div ref={editorRef} className="inline-editor" role="region" aria-label="编辑演示资料"><form onSubmit={e => { e.preventDefault(); update(editing, { title: title.trim(), tags: tags.split(/[，,]/).map(t => t.trim()).filter(Boolean) }); }}><div className="section-heading"><h2>整理演示资料</h2><button type="button" className="icon-button" aria-label="取消编辑资料" onClick={() => setEditing(null)}><X size={16} /></button></div><div className="form-grid"><Input label="标题" required maxLength={120} value={title} onChange={e => setTitle(e.target.value)} /><Input label="标签" placeholder="用逗号分隔，最多 8 个" value={tags} onChange={e => setTags(e.target.value)} /></div><div className="form-actions"><span>标题用于工作空间；幻灯片可在 PowerPoint 中编辑。</span><Button type="submit" isLoading={mutating === editing.id} disabled={!title.trim()}><Check size={15} />保存资料</Button></div></form></div>}
    <p className="page-footnote">归档后的作品可在“已归档”中找到并恢复。</p>
  </>;
}
