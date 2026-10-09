import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui';
import { StudioShell, type Section } from '@/components/layout/StudioShell';
import { StudioHome } from '@/components/layout/StudioHome';
import { SettingsPage } from '@/components/layout/SettingsPage';
import { WorkspacePage } from '@/components/layout/WorkspacePage';
import { AccountPage } from '@/components/layout/AccountPage';
import { PresentationPage } from '@/components/layout/PresentationPage';
import { PublicHome } from '@/components/layout/PublicHome';
import { downloadFile } from '@/components/layout/pageUtils';
import { useExamples, useProjectStore } from '@/stores/projectStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { api, setSessionCsrf, type AuthSession } from '@/api/client';
import type { PPTProjectSpec } from '@/types';
import type { Account } from '@/types/workspace';

function readRoute(): { section: Section; id?: string } {
  const [section,id] = window.location.hash.replace(/^#\/?/, '').split('/');
  if (section === 'project' && id) return { section, id: decodeURIComponent(id) };
  return { section: ['settings','workspace','account'].includes(section) ? section as Section : 'home' };
}
function StudioApp({ initialAccount, onLogout }: { initialAccount: Account; onLogout: () => void }) {
  const store = useProjectStore();
  const { project, isLoading, error, lastDownloadUrl, createProject, runWorkflow, generateParallel, workflowPending, setError, setProject } = store;
  const [route,setRoute] = useState(readRoute);
  const [account,setAccount] = useState<Account | null>(initialAccount); const [accountError,setAccountError] = useState('');
  const [selectedIndex,setSelectedIndex] = useState(0); const [downloading,setDownloading] = useState(false);
  const [loadingProject,setLoadingProject] = useState(false); const [loadError,setLoadError] = useState('');
  useWebSocket(project?.id || null);
  useEffect(() => { window.scrollTo(0,0); }, [route.section,route.id]);
  useEffect(() => { const handler = () => setRoute(readRoute()); window.addEventListener('hashchange',handler); return () => window.removeEventListener('hashchange',handler); }, []);
  const navigate = useCallback((section: Section, id?: string) => { window.location.hash = section === 'project' && (id || project?.id) ? `/project/${encodeURIComponent(id || project!.id)}` : `/${section === 'project' ? 'home' : section}`; }, [project?.id]);
  const refreshAccount = useCallback(async () => { try { setAccount(await api.getAccount()); setAccountError(''); } catch (e) { setAccountError((e as Error).message); } }, []);
  useEffect(() => {
    let current = true; const originalDraft = useProjectStore.getState().draftSpec;
    api.getAccount().then(data => { if (!current) return; setAccount(data); if (useProjectStore.getState().draftSpec === originalDraft) useProjectStore.getState().setDraftSpec({ style:data.profile.preferences.style,page_count:data.profile.preferences.page_count,layout_mode:data.profile.preferences.layout_mode || 'auto',content_density:data.profile.preferences.content_density || 'balanced' }); }).catch(e => { if (current) setAccountError(e.message); });
    return () => { current = false; };
  }, []);
  useEffect(() => { if (route.section === 'account') void refreshAccount(); }, [route.section,refreshAccount]);
  useEffect(() => {
    if (route.section !== 'project' || !route.id || route.id === project?.id) return;
    let current = true; setLoadingProject(true); setLoadError('');
    api.getProject(route.id).then(data => { if (current) { setLoadingProject(false); setProject(data); setSelectedIndex(0); } }).catch(e => { if (current) { setLoadError(e.message); setLoadingProject(false); } });
    return () => { current = false; };
  }, [route.section,route.id,project?.id,setProject]);
  const exportFile = useCallback(async () => {
    if (!project) return; setDownloading(true); setError(null);
    try {
      if (!lastDownloadUrl) throw new Error('导出还未完成，请先继续制作。');
      await downloadFile(lastDownloadUrl,project.spec.topic || 'Folio'); toast.success('PowerPoint 已开始下载');
    } catch (e) { setError((e as Error).message); toast.error((e as Error).message); } finally { setDownloading(false); }
  }, [project,lastDownloadUrl,setError]);
  const create = useCallback(async (input: string, spec: PPTProjectSpec) => {
    try { setError(null); const id = await createProject(spec,input); setSelectedIndex(0); setLoadError(''); navigate('project',id); runWorkflow(); }
    catch (e) { toast.error((e as Error).message); }
  }, [createProject,navigate,runWorkflow,setError]);
  const example = (item: ReturnType<typeof useExamples>[number]) => create(`请制作关于“${item.spec.topic}”的演示。${item.description}`,item.spec);
  const newPresentation = () => { store.setDraftInput(''); store.setDraftFiles([]); store.setDraftSpec({ topic:'' }); setError(null); navigate('home'); window.setTimeout(() => document.getElementById('brief')?.focus(),0); };
  const resume = () => {
    if (!project) return; setError(null);
    runWorkflow();
  };
  useEffect(() => { setSelectedIndex(0); }, [project?.id]);
  const pageTitle = route.section === 'project' ? `${project?.spec.topic || '展开你的想法'} — Folio` : route.section === 'workspace' ? '你的想法，都在这里 — Folio' : route.section === 'settings' ? '每个想法，都有自己的样子 — Folio' : route.section === 'account' ? '你的创作节奏 — Folio' : 'Folio — Let your ideas unfold.';
  useEffect(() => { document.title = pageTitle; }, [pageTitle]);
  return <StudioShell section={route.section} onNavigate={navigate} onNew={newPresentation} account={account} hasProject={!!project} projectTitle={project?.spec.topic} onLogout={onLogout}>
    {route.section === 'home' && <StudioHome onSubmit={create} onExample={example} onSettings={() => navigate('settings')} isLoading={isLoading} error={error} />}
    {route.section === 'settings' && <SettingsPage onBack={() => navigate('home')} onAccountChange={setAccount} />}
    {route.section === 'workspace' && <WorkspacePage onOpen={id => navigate('project',id)} onNew={newPresentation} />}
    {route.section === 'account' && <AccountPage account={account} error={accountError} onChange={setAccount} onRefresh={refreshAccount} />}
    {route.section === 'project' && (loadingProject || loadError || !project || project.id !== route.id ? <div className="empty-state" role={loadError ? 'alert' : 'status'}><p>{loadError || '正在打开演示…'}</p>{loadError && <Button variant="outline" onClick={() => navigate('workspace')}>返回工作空间</Button>}</div> : <PresentationPage key={project.id} project={project} selectedIndex={Math.min(selectedIndex,Math.max(0,(project.pages?.length || project.outline?.length || 1)-1))} onSelect={setSelectedIndex} onDownload={exportFile} onResume={resume} onRepair={() => { setError(null); generateParallel(); }} onWorkspace={() => navigate('workspace')} downloading={downloading} downloadUrl={lastDownloadUrl} error={error} scheduling={workflowPending} />)}
  </StudioShell>;
}
export default function App() {
  const [session,setSession] = useState<AuthSession | null>(null);
  const [checking,setChecking] = useState(true); const [sessionError,setSessionError] = useState('');
  const [hash,setHash] = useState(window.location.hash);
  const destination = useRef(window.location.hash);
  const channel = useRef<BroadcastChannel | null>(null);
  const sessionCheck = useRef(0);
  const clearIdentity = useCallback(() => {
    setSessionCsrf(''); setSession(null);
    useProjectStore.getState().clearProject();
    useProjectStore.setState({ draftInput:'',draftFiles:[],draftSpec:{ topic:'',page_count:8,style:'商务简约',audience:'通用',needs_cover:true,needs_toc:true,needs_summary:true,needs_chart:false } });
  }, []);
  const accept = useCallback((data: AuthSession) => {
    setSessionCsrf(data.csrf_token); setSession(data); setSessionError('');
  }, []);
  const checkSession = useCallback(async () => {
    const ticket = ++sessionCheck.current;
    try { const data = await api.getSession(); if (ticket===sessionCheck.current) accept(data); }
    catch (e) { if (ticket!==sessionCheck.current) return; clearIdentity(); if ((e as Error).message !== '请先登录 Folio') setSessionError((e as Error).message); }
    finally { if (ticket===sessionCheck.current) setChecking(false); }
  }, [accept,clearIdentity]);
  useEffect(() => { void checkSession(); return () => { sessionCheck.current++; }; }, [checkSession]);
  useEffect(() => {
    const route = () => setHash(window.location.hash);
    const expired = () => { sessionCheck.current++; clearIdentity(); setChecking(false); window.location.hash='/login'; };
    const refreshed = (event: Event) => { sessionCheck.current++; accept((event as CustomEvent<AuthSession>).detail); setChecking(false); window.location.hash='/account'; channel.current?.postMessage('changed'); };
    window.addEventListener('hashchange',route); window.addEventListener('folio-session-expired',expired);
    window.addEventListener('folio-session-refreshed',refreshed);
    if (typeof BroadcastChannel !== 'undefined') {
      channel.current = new BroadcastChannel('folio-auth');
      channel.current.onmessage = () => { clearIdentity(); setChecking(true); void checkSession(); };
    }
    return () => { window.removeEventListener('hashchange',route); window.removeEventListener('folio-session-expired',expired); window.removeEventListener('folio-session-refreshed',refreshed); channel.current?.close(); };
  }, [accept,clearIdentity,checkSession]);
  const privateRoute = /^#\/(home|settings|workspace|account|project)(\/|$)/.test(hash);
  useEffect(() => {
    if (!checking && !session && privateRoute) { destination.current=hash; window.location.hash='/login'; }
  }, [checking,session,privateRoute,hash]);
  const login = (data: AuthSession, registered = false) => {
    sessionCheck.current++;
    clearIdentity(); accept(data); channel.current?.postMessage('changed');
    window.location.hash = !registered && /^#\/(home|settings|workspace|account|project)(\/|$)/.test(destination.current) ? destination.current.slice(1) : '/home';
    destination.current='';
  };
  const logout = async () => {
    try { await api.logout(); sessionCheck.current++; clearIdentity(); channel.current?.postMessage('changed'); window.location.hash='/login'; }
    catch (e) { toast.error((e as Error).message); }
  };
  if (checking) return <div className="session-loading" role="status"><img src="/folio-mark.svg" width="28" alt="" /><span>正在打开 Folio…</span></div>;
  if (session && privateRoute) return <StudioApp key={session.account.profile.account_id} initialAccount={session.account} onLogout={logout} />;
  return <>{sessionError && <div className="public-connection-error" role="alert">{sessionError}<Button variant="ghost" onClick={() => { setSessionError(''); setChecking(true); void checkSession(); }}>重新连接</Button></div>}<PublicHome signedIn={!!session} onAuthenticated={login} onEnter={() => { window.location.hash='/home'; }} /></>;
}
