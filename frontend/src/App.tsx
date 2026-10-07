import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui';
import { StudioShell, type Section } from '@/components/layout/StudioShell';
import { StudioHome } from '@/components/layout/StudioHome';
import { SettingsPage } from '@/components/layout/SettingsPage';
import { WorkspacePage } from '@/components/layout/WorkspacePage';
import { AccountPage } from '@/components/layout/AccountPage';
import { PresentationPage } from '@/components/layout/PresentationPage';
import { downloadFile } from '@/components/layout/pageUtils';
import { useExamples, useProjectStore } from '@/stores/projectStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { api } from '@/api/client';
import type { PPTProjectSpec } from '@/types';
import type { Account } from '@/types/workspace';

function readRoute(): { section: Section; id?: string } {
  const [section,id] = window.location.hash.replace(/^#\/?/, '').split('/');
  if (section === 'project' && id) return { section, id: decodeURIComponent(id) };
  return { section: ['settings','workspace','account'].includes(section) ? section as Section : 'home' };
}
function App() {
  const store = useProjectStore();
  const { project, isLoading, error, lastDownloadUrl, createProject, parseInput, planOutline, generateParallel, renderPPTX, setError, setProject } = store;
  const [route,setRoute] = useState(readRoute);
  const [account,setAccount] = useState<Account | null>(null); const [accountError,setAccountError] = useState('');
  const [selectedIndex,setSelectedIndex] = useState(0); const [downloading,setDownloading] = useState(false);
  const [loadingProject,setLoadingProject] = useState(false); const [loadError,setLoadError] = useState('');
  const autoGenerate = useRef<string | null>(null); const autoDownload = useRef<string | null>(null);
  useWebSocket(project?.id || null);
  useEffect(() => { const handler = () => setRoute(readRoute()); window.addEventListener('hashchange',handler); return () => window.removeEventListener('hashchange',handler); }, []);
  const navigate = useCallback((section: Section, id?: string) => { window.location.hash = section === 'project' && (id || project?.id) ? `/project/${encodeURIComponent(id || project!.id)}` : `/${section === 'project' ? 'home' : section}`; }, [project?.id]);
  const refreshAccount = useCallback(async () => { try { setAccount(await api.getAccount()); setAccountError(''); } catch (e) { setAccountError((e as Error).message); } }, []);
  useEffect(() => {
    let current = true; const originalDraft = useProjectStore.getState().draftSpec;
    api.getAccount().then(data => { if (!current) return; setAccount(data); if (useProjectStore.getState().draftSpec === originalDraft) useProjectStore.getState().setDraftSpec({ style:data.profile.preferences.style,page_count:data.profile.preferences.page_count }); }).catch(e => { if (current) setAccountError(e.message); });
    return () => { current = false; };
  }, []);
  useEffect(() => { if (route.section === 'account') void refreshAccount(); }, [route.section,refreshAccount]);
  useEffect(() => {
    if (route.section !== 'project' || !route.id || route.id === project?.id) return;
    let current = true; setLoadingProject(true); setLoadError(''); autoGenerate.current = null; autoDownload.current = null;
    api.getProject(route.id).then(data => { if (current) { setLoadingProject(false); setProject(data); setSelectedIndex(0); } }).catch(e => { if (current) { setLoadError(e.message); setLoadingProject(false); } });
    return () => { current = false; };
  }, [route.section,route.id,project?.id,setProject]);
  useEffect(() => {
    if (project?.status === 'planned' && autoGenerate.current === project.id) { autoGenerate.current = null; generateParallel(); }
    if (project?.status === 'failed') { autoGenerate.current = null; autoDownload.current = null; }
  }, [project?.status,project?.id,generateParallel]);
  const exportFile = useCallback(async () => {
    if (!project) return; setDownloading(true); setError(null);
    try {
      let url = lastDownloadUrl;
      if (!url || project.status !== 'completed') {
        const id = project.id; useProjectStore.setState({ lastDownloadUrl:null }); renderPPTX(); url = null;
        for (let i=0;i<120 && !url;i++) { await new Promise(resolve => setTimeout(resolve,250)); const state = useProjectStore.getState(); if (state.project?.id !== id) return; if (state.error) throw new Error(state.error); url = state.lastDownloadUrl; }
      }
      if (!url) throw new Error('导出还未完成，请稍后重试。');
      await downloadFile(url,project.spec.topic || 'Folio'); toast.success('PowerPoint 已开始下载');
    } catch (e) { setError((e as Error).message); toast.error((e as Error).message); } finally { setDownloading(false); }
  }, [project,lastDownloadUrl,renderPPTX,setError]);
  useEffect(() => {
    if (project?.status === 'completed' && lastDownloadUrl && autoDownload.current === project.id && !downloading) { autoDownload.current = null; void exportFile(); }
  }, [project?.status,project?.id,lastDownloadUrl,downloading,exportFile]);
  const create = useCallback(async (input: string, spec: PPTProjectSpec) => {
    try { setError(null); const id = await createProject(spec,input); autoGenerate.current = id; autoDownload.current = id; setSelectedIndex(0); setLoadError(''); navigate('project',id); parseInput(); planOutline(); }
    catch (e) { toast.error((e as Error).message); }
  }, [createProject,navigate,parseInput,planOutline,setError]);
  const example = (item: ReturnType<typeof useExamples>[number]) => create(`请制作关于“${item.spec.topic}”的演示。${item.description}`,item.spec);
  const newPresentation = () => { store.setDraftInput(''); store.setDraftFiles([]); store.setDraftSpec({ topic:'' }); setError(null); navigate('home'); window.setTimeout(() => document.getElementById('brief')?.focus(),0); };
  const resume = () => {
    if (!project) return; setError(null); autoDownload.current = project.id;
    if (project.status === 'completed' || project.status === 'editing') { autoDownload.current = null; void exportFile(); }
    else if (project.outline?.length && project.pages?.length) generateParallel();
    else { autoGenerate.current = project.id; if (!project.outline?.length) parseInput(); planOutline(); }
  };
  useEffect(() => { setSelectedIndex(0); }, [project?.id]);
  const pageTitle = route.section === 'project' ? `${project?.spec.topic || '展开你的想法'} — Folio` : route.section === 'workspace' ? '你的想法，都在这里 — Folio' : route.section === 'settings' ? '为下一次表达做好准备 — Folio' : route.section === 'account' ? '你的创作节奏 — Folio' : 'Folio — Let your ideas unfold.';
  useEffect(() => { document.title = pageTitle; }, [pageTitle]);
  return <StudioShell section={route.section} onNavigate={navigate} onNew={newPresentation} account={account} hasProject={!!project} projectTitle={project?.spec.topic}>
    {route.section === 'home' && <StudioHome onSubmit={create} onExample={example} onSettings={() => navigate('settings')} isLoading={isLoading} error={error} />}
    {route.section === 'settings' && <SettingsPage onBack={() => navigate('home')} onAccountChange={setAccount} />}
    {route.section === 'workspace' && <WorkspacePage onOpen={id => navigate('project',id)} onNew={newPresentation} />}
    {route.section === 'account' && <AccountPage account={account} error={accountError} onChange={setAccount} onRefresh={refreshAccount} />}
    {route.section === 'project' && (loadingProject || loadError || !project || project.id !== route.id ? <div className="empty-state" role={loadError ? 'alert' : 'status'}><p>{loadError || '正在打开演示…'}</p>{loadError && <Button variant="outline" onClick={() => navigate('workspace')}>返回工作空间</Button>}</div> : <PresentationPage key={project.id} project={project} selectedIndex={Math.min(selectedIndex,Math.max(0,(project.pages?.length || project.outline?.length || 1)-1))} onSelect={setSelectedIndex} onDownload={exportFile} onResume={resume} onWorkspace={() => navigate('workspace')} downloading={downloading} downloadUrl={lastDownloadUrl} error={error} scheduling={autoGenerate.current === project.id && project.status !== 'failed'} />)}
  </StudioShell>;
}
export default App;
