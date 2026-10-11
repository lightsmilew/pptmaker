import { adminTitles } from '@/lib/pageTitles';
import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { ArrowRight, ShieldCheck, Users, SlidersHorizontal, ScrollText } from 'lucide-react';
import { Button, Input } from '@/components/ui';
import { Brand, StudioShell, type Section } from '@/components/layout/StudioShell';
import { adminApi, setAdminCsrf, type AdminSession } from '@/api/adminClient';
import { AdminAccount, AdminMemberships, AdminModels, AdminOverview, AdminRecords, AdminUsage, AdminUsers } from './AdminPages';
import './admin.css';
import { SupportPage } from '@/components/support/SupportPage';
import { useSupportNotifications } from '@/hooks/useSupportNotifications';
import { AdminAnnouncements } from './AdminAnnouncements';

const sections = ['overview','users','memberships','models','usage','records','account','support','announcements'];
function AdminLogin({ onAuthenticated }: { onAuthenticated:(s:AdminSession)=>void }) {
  const [email,setEmail] = useState(''); const [password,setPassword] = useState(''); const [error,setError] = useState(''); const [busy,setBusy] = useState(false);
  return <div className="admin-welcome"><header><Brand href="#/admin/login" /><a href="#/login" className="text-link">返回 Folio <ArrowRight size={14} /></a></header><main className="admin-welcome-main"><div className="admin-welcome-copy"><p className="eyebrow">FOLIO / BEHIND THE PAGES</p><h1>让好想法，<br />从容地展开。</h1><p>照顾每位创作者的账号与权益，<br />也照顾每一次表达背后的运转。</p><div className="admin-welcome-features">{[{ icon:Users,title:'账号与权益',text:'不同的创作节奏，恰如其分的空间。' },{ icon:SlidersHorizontal,title:'模型与运行',text:'选择连接与模型，让制作有序进行。' },{ icon:ScrollText,title:'用量与记录',text:'从真实活动中，看见每一个变化。' }].map(f=><div key={f.title}><f.icon size={18} /><div><h2>{f.title}</h2><p>{f.text}</p></div></div>)}</div></div><div className="admin-login-panel"><ShieldCheck size={22} /><p className="eyebrow">ADMINISTRATOR ACCESS</p><h2>进入管理中心</h2><p>使用专用管理账号登录。</p><form onSubmit={async e=>{ e.preventDefault(); setBusy(true); setError(''); try { onAuthenticated(await adminApi.login(email,password)); setPassword(''); } catch(e) { setError((e as Error).message); } finally { setBusy(false); } }}><Input label="管理员邮箱" type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} required maxLength={254} /><Input label="密码" type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required minLength={1} maxLength={128} />{error && <p className="field-error" role="alert">{error}</p>}<Button type="submit" isLoading={busy}>登录管理中心 <ArrowRight size={14} /></Button></form><p className="admin-login-footnote">管理入口仅向已创建的管理员开放。<br />首次登录后，可在管理账号中更换密码。</p></div></main><footer>Folio — Let your ideas unfold.<span>Behind every thoughtful presentation.</span></footer></div>;
}

export function AdminApp() {
  const [hash,setHash] = useState(window.location.hash); const [session,setSession] = useState<AdminSession | null>(null); const [checking,setChecking] = useState(true); const [error,setError] = useState(''); const ticket = useRef(0); const channel = useRef<BroadcastChannel | null>(null);
  const accept = useCallback((s:AdminSession) => { setAdminCsrf(s.csrf_token); setSession(s); setError(''); },[]);
  const supportUnread = useSupportNotifications(session?.account.profile.account_id,true,session?.csrf_token);
  const clear = useCallback(()=>{ setAdminCsrf(''); setSession(null); },[]);
  const check = useCallback(async()=>{ const current=++ticket.current; try { const data=await adminApi.session(); if(current===ticket.current) accept(data); } catch(e) { if(current===ticket.current) { clear(); if((e as Error).message !== '请从管理入口登录') setError((e as Error).message); } } finally { if(current===ticket.current) setChecking(false); } },[accept,clear]);
  useEffect(()=>{ void check(); const route=()=>setHash(window.location.hash); const expired=()=>{ ticket.current++; clear(); setChecking(false); window.location.hash='/admin/login'; }; window.addEventListener('hashchange',route); window.addEventListener('folio-admin-expired',expired); if(typeof BroadcastChannel !== 'undefined') { channel.current = new BroadcastChannel('folio-admin-auth'); channel.current.onmessage=()=>{ clear(); setChecking(true); void check(); }; } return()=>{ ticket.current++; window.removeEventListener('hashchange',route); window.removeEventListener('folio-admin-expired',expired); channel.current?.close(); clear(); }; },[check,clear]);
  const raw = hash.split('/')[2] || 'overview'; const route = sections.includes(raw) ? raw : 'overview'; const section = ('admin-'+route) as Section;
  useEffect(()=>{ if(!checking && !session && /^#\/admin(?:\/|$)/.test(hash) && hash !== '#/admin/login') window.location.hash='/admin/login'; },[checking,session,hash]);
  useEffect(()=>{ document.title = session ? `${adminTitles[route] || adminTitles.overview} — Folio Admin` : 'Folio — Behind the pages.'; window.scrollTo(0,0); },[route,session]);
  const navigate = (s:Section)=>{ window.location.hash='/admin/'+s.replace('admin-',''); };
  if(checking) return <div className="session-loading" role="status"><img src="/folio-mark.svg" width="28" alt="" /><span>正在打开管理中心…</span></div>;
  if(!session) return <>{error && <div role="alert" className="public-connection-error">{error}<Button variant="ghost" onClick={()=>{ setChecking(true); void check(); }}>重新连接</Button></div>}<AdminLogin onAuthenticated={s=>{ ticket.current++; accept(s); channel.current?.postMessage('changed'); window.location.hash='/admin/overview'; }} /></>;
  return <StudioShell supportUnread={supportUnread} mode="admin" section={section} account={session.account} hasProject={false} onNavigate={navigate} onNew={()=>navigate('admin-overview')} onLogout={async()=>{ try { await adminApi.logout(); ticket.current++; clear(); channel.current?.postMessage('changed'); window.location.hash='/admin/login'; } catch(e) { toast.error((e as Error).message); } }}>
    {route==='announcements' && <AdminAnnouncements />}
    {route==='support' && <SupportPage admin />}{route==='overview' && <AdminOverview navigate={navigate} />}{route==='users' && <AdminUsers />}{route==='memberships' && <AdminMemberships />}{route==='models' && <AdminModels />}{route==='usage' && <AdminUsage />}{route==='records' && <AdminRecords />}{route==='account' && <AdminAccount session={session} onSession={s=>{ accept(s); channel.current?.postMessage('changed'); }} />}
  </StudioShell>;
}
