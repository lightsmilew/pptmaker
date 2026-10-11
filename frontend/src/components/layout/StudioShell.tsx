import { useEffect, useRef, type ReactNode } from 'react';
import { ArrowUpRight, FileText, FolderOpen, LayoutGrid, LogOut, Plus, SlidersHorizontal, UserRound, Users, ShieldCheck, BarChart3, ScrollText, CreditCard, MessageSquare, Megaphone } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { Account } from '@/types/workspace';
import './navigation.css';

export type Section = 'home' | 'settings' | 'workspace' | 'account' | 'project' | 'support' | 'admin-overview' | 'admin-users' | 'admin-memberships' | 'admin-models' | 'admin-usage' | 'admin-records' | 'admin-account' | 'admin-support' | 'admin-announcements';
export function Brand({ href = '#/home', onClick }: { href?: string; onClick?:()=>void }) {
  return <a className="studio-brand" href={href} onClick={onClick} aria-label="Folio 首页"><img src="/folio-mark.svg" width="23" height="25" alt="" />Folio<span className="brand-dot">.</span></a>;
}

export function StudioShell({ section, children, onNavigate, onNew, account, projectTitle, hasProject, onLogout, mode = 'studio', supportUnread = 0 }: {
  section: Section; children: ReactNode; onNavigate: (section: Section) => void; onNew: () => void;
  account: Account | null; projectTitle?: string; hasProject: boolean;
  onLogout?: () => void;
  mode?: 'studio' | 'admin';
  supportUnread?: number;
}) {
  const mobileNav = useRef<HTMLElement>(null);
  const navigate = (value: Section) => onNavigate(value);
  useEffect(() => {
    const nav = mobileNav.current;
    const active = nav?.querySelector<HTMLElement>('[aria-current=page]');
    if (nav && active && nav.scrollWidth > nav.clientWidth) nav.scrollLeft = active.offsetLeft - (nav.clientWidth - active.offsetWidth) / 2;
  }, [section, hasProject]);
  const admin = mode === 'admin';
  const labels: Record<Section, string> = { 'admin-announcements':'公告管理', support:'与 Folio 沟通', 'admin-support':'用户沟通', home: '新建演示文稿', settings: '创作方案', workspace: '我的工作空间', account: '个人中心', project: projectTitle || '演示文稿', 'admin-overview':'管理概览', 'admin-users':'账号管理', 'admin-memberships':'会员权益', 'admin-models':'模型与环境', 'admin-usage':'用量与额度', 'admin-records':'活动记录', 'admin-account':'管理账号' };
  const navigation: { id: Section; icon: typeof LayoutGrid; label: string }[] = admin ? [{ id:'admin-overview',icon:LayoutGrid,label:'管理概览' },{ id:'admin-users',icon:Users,label:'账号管理' },{ id:'admin-memberships',icon:CreditCard,label:'会员权益' },{ id:'admin-models',icon:SlidersHorizontal,label:'模型与环境' },{ id:'admin-usage',icon:BarChart3,label:'用量与额度' },{ id:'admin-records',icon:ScrollText,label:'活动记录' },{ id:'admin-support',icon:MessageSquare,label:'用户沟通' },{ id:'admin-announcements',icon:Megaphone,label:'公告管理' }] : [{ id:'home',icon:LayoutGrid,label:'制作工作台' },{ id:'workspace',icon:FolderOpen,label:'我的工作空间' },{ id:'settings',icon:SlidersHorizontal,label:'创作方案' },{ id:'support',icon:MessageSquare,label:'与 Folio 沟通' }];
  const mobileItems = [...navigation.map(item => ({...item,short:({ home:'创作',workspace:'作品',settings:'方案',support:'沟通','admin-overview':'概览','admin-users':'账号','admin-memberships':'会员','admin-models':'模型','admin-usage':'用量','admin-records':'记录','admin-support':'沟通','admin-announcements':'公告' } as Record<string,string>)[item.id]})),
    ...(hasProject ? [{id:'project' as Section,icon:FileText,label:'当前演示',short:'预览'}] : []),
    {id:(admin ? 'admin-account' : 'account') as Section,icon:UserRound,label:admin ? '管理账号' : '个人中心',short:'我的'}];
  return <div className="studio-shell">
    <aside className="studio-sidebar" aria-label={admin ? 'Folio 管理导航' : 'Folio 工作台导航'}>
      <Brand href={admin ? '#/admin/overview' : '#/home'} />
      <button className="studio-new" onClick={onNew}>{admin ? <ShieldCheck size={17} /> : <Plus size={17} />}{admin ? 'Folio 管理中心' : '新建演示文稿'}</button>
      <span className="sidebar-caption">{admin ? '运营与设置' : '工作空间'}</span>
      <nav aria-label="主导航">
        {navigation.map(item => <button key={item.id} aria-current={section === item.id ? 'page' : undefined} className={section === item.id ? 'active' : ''} onClick={() => navigate(item.id)}><item.icon size={17} />{item.label}{item.id.endsWith('support') && supportUnread>0 && <span className="support-badge" aria-label={`${supportUnread} 条未读消息`}>{supportUnread>99 ? '99+' : supportUnread}</span>}</button>)}
        {hasProject && <button className={`current-presentation ${section === 'project' ? 'active' : ''}`} aria-current={section === 'project' ? 'page' : undefined} onClick={() => navigate('project')}><FileText size={17} /><span>{projectTitle || '当前演示'}</span></button>}
      </nav>
      <div className="sidebar-note"><span className="sidebar-note-rule" /><p>把时间留给内容。<br />把表达交给好设计。</p></div>
      <button className={`studio-profile ${section === (admin ? 'admin-account' : 'account') ? 'active' : ''}`} aria-label={admin ? '管理账号' : '个人中心'} onClick={() => navigate(admin ? 'admin-account' : 'account')}><span className="profile-avatar">{(account?.profile.display_name || 'F').slice(0, 1)}</span><span className="profile-copy"><strong>{account?.profile.display_name || '个人中心'}</strong><small>{admin ? '管理员 · 账号安全' : `${account?.membership.name || 'Folio 账号'} · 个人中心`}</small></span><ArrowUpRight size={14} /></button>
    </aside>
    <div className="studio-main">
      <header className="studio-topbar">
        <div className="mobile-brand"><Brand href={admin ? '#/admin/overview' : '#/home'} /></div>
        <div className="topbar-breadcrumb"><span className="mobile-location">{admin ? 'FOLIO ADMIN' : 'YOUR STUDIO'}</span><button className="breadcrumb-home" onClick={() => navigate(admin ? 'admin-overview' : 'workspace')}>{admin ? '管理中心' : '工作空间'}</button><span className="breadcrumb-slash">/</span><strong title={labels[section]}>{section === 'home' ? '制作工作台' : labels[section]}</strong></div>
        <div className="topbar-actions"><span className="topbar-tag"><span />{admin ? '让创作有序展开' : '你的私人工作台'}</span>{onLogout && <button className="topbar-logout" onClick={onLogout} aria-label="退出登录"><LogOut size={14} /><span>退出</span></button>}</div>
        <nav ref={mobileNav} className="mobile-primary-nav" aria-label={admin ? '管理页面导航' : '工作台页面导航'}>{mobileItems.map(item=><button key={item.id} aria-label={`前往${item.label}`} aria-current={section===item.id ? 'page' : undefined} onClick={()=>navigate(item.id)}><span className="mobile-nav-icon"><item.icon size={16} />{item.id.endsWith('support') && supportUnread>0 && <span className="mobile-unread">{supportUnread>99 ? '99+' : supportUnread}</span>}</span><span>{item.short}</span></button>)}</nav>
      </header>
      <main className={`studio-content ${section === 'project' ? 'presentation-content' : ''}`}>{children}{onLogout && (section==='account' || section==='admin-account') && <div className="mobile-session-action"><Button variant="outline" onClick={onLogout}><LogOut size={14} />退出当前账号</Button></div>}</main>
      <footer className="studio-footer shell-footer"><span>Folio — Let your ideas unfold.</span><span>你的内容，由你决定。</span></footer>
    </div>
  </div>;
}
