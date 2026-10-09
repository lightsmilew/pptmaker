import { useState, type ReactNode } from 'react';
import { ArrowUpRight, FileText, FolderOpen, LayoutGrid, LogOut, PanelLeft, Plus, SlidersHorizontal, X, Users, ShieldCheck, BarChart3, ScrollText, CreditCard } from 'lucide-react';
import type { Account } from '@/types/workspace';

export type Section = 'home' | 'settings' | 'workspace' | 'account' | 'project' | 'admin-overview' | 'admin-users' | 'admin-memberships' | 'admin-models' | 'admin-usage' | 'admin-records' | 'admin-account';
export function Brand({ href = '#/home' }: { href?: string }) {
  return <a className="studio-brand" href={href} aria-label="Folio 首页"><img src="/folio-mark.svg" width="23" height="25" alt="" />Folio<span className="brand-dot">.</span></a>;
}

export function StudioShell({ section, children, onNavigate, onNew, account, projectTitle, hasProject, onLogout, mode = 'studio' }: {
  section: Section; children: ReactNode; onNavigate: (section: Section) => void; onNew: () => void;
  account: Account | null; projectTitle?: string; hasProject: boolean;
  onLogout?: () => void;
  mode?: 'studio' | 'admin';
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = (value: Section) => { onNavigate(value); setMenuOpen(false); };
  const admin = mode === 'admin';
  const labels: Record<Section, string> = { home: '新建演示文稿', settings: '创作方案', workspace: '我的工作空间', account: '个人中心', project: projectTitle || '演示文稿', 'admin-overview':'管理概览', 'admin-users':'账号管理', 'admin-memberships':'会员权益', 'admin-models':'模型与环境', 'admin-usage':'用量与额度', 'admin-records':'活动记录', 'admin-account':'管理账号' };
  const navigation: { id: Section; icon: typeof LayoutGrid; label: string }[] = admin ? [{ id:'admin-overview',icon:LayoutGrid,label:'管理概览' },{ id:'admin-users',icon:Users,label:'账号管理' },{ id:'admin-memberships',icon:CreditCard,label:'会员权益' },{ id:'admin-models',icon:SlidersHorizontal,label:'模型与环境' },{ id:'admin-usage',icon:BarChart3,label:'用量与额度' },{ id:'admin-records',icon:ScrollText,label:'活动记录' }] : [{ id:'home',icon:LayoutGrid,label:'制作工作台' },{ id:'workspace',icon:FolderOpen,label:'我的工作空间' },{ id:'settings',icon:SlidersHorizontal,label:'创作方案' }];
  return <div className="studio-shell">
    {menuOpen && <button className="sidebar-scrim" aria-label="关闭导航" onClick={() => setMenuOpen(false)} />}
    <aside className={`studio-sidebar ${menuOpen ? 'is-open' : ''}`}>
      <Brand href={admin ? '#/admin/overview' : '#/home'} />
      <button className="studio-new" onClick={() => { onNew(); setMenuOpen(false); }}>{admin ? <ShieldCheck size={17} /> : <Plus size={17} />}{admin ? 'Folio 管理中心' : '新建演示文稿'}</button>
      <span className="sidebar-caption">{admin ? '运营与设置' : '工作空间'}</span>
      <nav aria-label="主导航">
        {navigation.map(item => <button key={item.id} aria-current={section === item.id ? 'page' : undefined} className={section === item.id ? 'active' : ''} onClick={() => navigate(item.id)}><item.icon size={17} />{item.label}</button>)}
        {hasProject && <button className={`current-presentation ${section === 'project' ? 'active' : ''}`} aria-current={section === 'project' ? 'page' : undefined} onClick={() => navigate('project')}><FileText size={17} /><span>{projectTitle || '当前演示'}</span></button>}
      </nav>
      <div className="sidebar-note"><span className="sidebar-note-rule" /><p>把时间留给内容。<br />把表达交给好设计。</p></div>
      <button className={`studio-profile ${section === (admin ? 'admin-account' : 'account') ? 'active' : ''}`} aria-label={admin ? '管理账号' : '个人中心'} onClick={() => navigate(admin ? 'admin-account' : 'account')}><span className="profile-avatar">{(account?.profile.display_name || 'F').slice(0, 1)}</span><span className="profile-copy"><strong>{account?.profile.display_name || '个人中心'}</strong><small>{admin ? '管理员 · 账号安全' : `${account?.membership.name || 'Folio 账号'} · 个人中心`}</small></span><ArrowUpRight size={14} /></button>
    </aside>
    <div className="studio-main">
      <header className="studio-topbar"><div><button className="mobile-menu" aria-label="切换导航" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={18} /> : <PanelLeft size={18} />}</button><button className="breadcrumb-home" onClick={() => navigate(admin ? 'admin-overview' : 'workspace')}>{admin ? '管理中心' : '工作空间'}</button><span className="breadcrumb-slash">/</span><strong>{labels[section]}</strong></div><div className="topbar-actions"><span className="topbar-tag"><span />{admin ? '让创作有序展开' : '你的私人工作台'}</span>{onLogout && <button className="text-link" onClick={onLogout} aria-label="退出登录"><LogOut size={14} /><span>退出</span></button>}</div></header>
      <main className={`studio-content ${section === 'project' ? 'presentation-content' : ''}`}>{children}</main>
      <footer className="studio-footer shell-footer"><span>Folio — Let your ideas unfold.</span><span>你的内容，由你决定。</span></footer>
    </div>
  </div>;
}
