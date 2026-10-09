import { useState, type ReactNode } from 'react';
import { ArrowUpRight, FileText, FolderOpen, LayoutGrid, LogOut, PanelLeft, Plus, SlidersHorizontal, X } from 'lucide-react';
import type { Account } from '@/types/workspace';

export type Section = 'home' | 'settings' | 'workspace' | 'account' | 'project';
export function Brand({ href = '#/home' }: { href?: string }) {
  return <a className="studio-brand" href={href} aria-label="Folio 首页"><img src="/folio-mark.svg" width="23" height="25" alt="" />Folio<span className="brand-dot">.</span></a>;
}

export function StudioShell({ section, children, onNavigate, onNew, account, projectTitle, hasProject, onLogout }: {
  section: Section; children: ReactNode; onNavigate: (section: Section) => void; onNew: () => void;
  account: Account | null; projectTitle?: string; hasProject: boolean;
  onLogout?: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = (value: Section) => { onNavigate(value); setMenuOpen(false); };
  const labels: Record<Section, string> = { home: '新建演示文稿', settings: '创作方案', workspace: '我的工作空间', account: '个人中心', project: projectTitle || '演示文稿' };
  return <div className="studio-shell">
    {menuOpen && <button className="sidebar-scrim" aria-label="关闭导航" onClick={() => setMenuOpen(false)} />}
    <aside className={`studio-sidebar ${menuOpen ? 'is-open' : ''}`}>
      <Brand />
      <button className="studio-new" onClick={() => { onNew(); setMenuOpen(false); }}><Plus size={17} />新建演示文稿</button>
      <span className="sidebar-caption">工作空间</span>
      <nav aria-label="主导航">
        {([{ id: 'home', icon: LayoutGrid, label: '制作工作台' }, { id: 'workspace', icon: FolderOpen, label: '我的工作空间' }, { id: 'settings', icon: SlidersHorizontal, label: '创作方案' }] as const).map(item => <button key={item.id} aria-current={section === item.id ? 'page' : undefined} className={section === item.id ? 'active' : ''} onClick={() => navigate(item.id)}><item.icon size={17} />{item.label}</button>)}
        {hasProject && <button className={`current-presentation ${section === 'project' ? 'active' : ''}`} aria-current={section === 'project' ? 'page' : undefined} onClick={() => navigate('project')}><FileText size={17} /><span>{projectTitle || '当前演示'}</span></button>}
      </nav>
      <div className="sidebar-note"><span className="sidebar-note-rule" /><p>把时间留给内容。<br />把表达交给好设计。</p></div>
      <button className={`studio-profile ${section === 'account' ? 'active' : ''}`} aria-label="个人中心" onClick={() => navigate('account')}><span className="profile-avatar">{(account?.profile.display_name || 'F').slice(0, 1)}</span><span className="profile-copy"><strong>{account?.profile.display_name || '个人中心'}</strong><small>{account?.membership.name || 'Folio 账号'} · 个人中心</small></span><ArrowUpRight size={14} /></button>
    </aside>
    <div className="studio-main">
      <header className="studio-topbar"><div><button className="mobile-menu" aria-label="切换导航" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={18} /> : <PanelLeft size={18} />}</button><button className="breadcrumb-home" onClick={() => navigate('workspace')}>工作空间</button><span className="breadcrumb-slash">/</span><strong>{labels[section]}</strong></div><div className="topbar-actions"><span className="topbar-tag"><span />你的私人工作台</span>{onLogout && <button className="text-link" onClick={onLogout} aria-label="退出登录"><LogOut size={14} /><span>退出</span></button>}</div></header>
      <main className={`studio-content ${section === 'project' ? 'presentation-content' : ''}`}>{children}</main>
      <footer className="studio-footer shell-footer"><span>Folio — Let your ideas unfold.</span><span>你的内容，由你决定。</span></footer>
    </div>
  </div>;
}
