import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '@/App';
import { useProjectStore } from '@/stores/projectStore';
import { api } from '@/api/client';
import type { Account } from '@/types/workspace';
import { designFixture } from '@/test/designFixture';
import { downloadFile } from '@/components/layout/pageUtils';
vi.mock('@/components/layout/pageUtils',async importOriginal => ({ ...await importOriginal<typeof import('@/components/layout/pageUtils')>(),downloadFile:vi.fn() }));
vi.mock('@/hooks/useWebSocket',() => ({ useWebSocket:vi.fn() }));
vi.mock('@/api/client',() => ({ setSessionCsrf:vi.fn(), api:{ getAnnouncements:vi.fn().mockResolvedValue({items:[],day:"2026-10-10"}),getDesignCatalog:vi.fn(),getSession:vi.fn(),login:vi.fn(),register:vi.fn(),logout:vi.fn(),getAccount:vi.fn(),updateProfile:vi.fn(),getProject:vi.fn(),createProject:vi.fn(),getWorkspace:vi.fn(),listProjects:vi.fn(),updateMetadata:vi.fn() } }));
const account: Account = {
 profile:{ account_id:'local_test',display_name:'Folio 创作者',email:'',company:'',occupation:'',bio:'',timezone:'Asia/Shanghai',created_at:'2026-10-01T00:00:00Z',preferences:{ style:'商务简约',page_count:8,language:'zh-CN' } },
 membership:{ tier:'local',name:'Folio Local',is_vip:false,status:'active',expires_at:null,managed_by:'local_configuration',billing_mode:'own_api_key',features:['可编辑 PowerPoint 导出'],limits:{ max_pages:50,concurrency:3 } },
 usage:{ period:'2026-10',period_start:'2026-10-01',resets_at:'2026-11-01',calls:2,lifetime_calls:2,input_tokens:1000,output_tokens:300,cached_input_tokens:500,reasoning_tokens:0,successful_calls:2,response_cache_hits:0,duration_ms:3000,provider_cache_hit_rate:.5,daily:[],quota:{ unit:'output_tokens',limit:null,used:300,reserved:0,remaining:null,is_unlimited:true,source:'local_budget' } },
 account:{ mode:'local',status:'active',email_verified:false,provider_host:'api.example.com',model:'example',provider_connected:true,authentication:'local_workspace' }
};
describe('Folio navigation and persistent account',() => {
 beforeEach(() => {
  vi.clearAllMocks(); window.location.hash = '/home'; useProjectStore.getState().clearProject();
  useProjectStore.setState({ draftInput:'',draftFiles:[],draftSpec:{ topic:'',page_count:8,style:'商务简约' } });
  vi.mocked(api.getAccount).mockResolvedValue(account);
  vi.mocked(api.getDesignCatalog).mockResolvedValue(designFixture);
  vi.mocked(downloadFile).mockResolvedValue();
  vi.mocked(api.getSession).mockResolvedValue({ account,csrf_token:'test-csrf' });
  vi.mocked(api.getWorkspace).mockResolvedValue({ name:'我的工作空间',mode:'local',stats:{ total:0,completed:0,favorites:0,in_progress:0,archived:0,pages:0,storage_bytes:0 },recent:[] });
  vi.mocked(api.listProjects).mockResolvedValue({ projects:[],total:0,page:1,page_size:12 });
 });
 it('retains brief and settings when navigating through the shared sidebar',async () => {
  render(<App />); await screen.findByText('Folio 创作者');
  fireEvent.change(screen.getByRole('textbox',{name:'演示内容或制作要求'}),{target:{value:'材料与试用结果'}});
  fireEvent.click(screen.getByRole('button',{name:'创作方案'}));
  fireEvent.change(await screen.findByRole('spinbutton',{name:'设置演示页数'}),{target:{value:'4'}});
  expect(useProjectStore.getState().draftSpec.page_count).toBe(4);
  fireEvent.click(await screen.findByRole('button',{name:/^学术简约/}));
  fireEvent.click(screen.getByRole('button',{name:/^编辑叙事/}));
  await act(() => userEvent.click(screen.getByRole('combobox',{name:'内容密度'})));
  await act(() => userEvent.keyboard('{ArrowUp}{Enter}'));
  await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument());
  fireEvent.change(screen.getByRole('textbox',{name:'补充要求'}),{target:{value:'保留已有结论'}});
  expect(useProjectStore.getState().draftSpec.page_count).toBe(4);
  fireEvent.click(screen.getByRole('button',{name:'返回制作工作台'}));
  expect(await screen.findByRole('textbox',{name:'演示内容或制作要求'})).toHaveValue('材料与试用结果');
  expect(screen.getByRole('spinbutton',{name:'演示页数'})).toHaveValue(4);
  vi.mocked(api.createProject).mockResolvedValue({ id:'proj_new',status:'idle',spec:{ topic:'测试',page_count:4 },pages:[] });
  fireEvent.click(screen.getByRole('button',{name:'创建演示'}));
  await waitFor(() => expect(api.createProject).toHaveBeenCalledWith(expect.objectContaining({ user_input:'材料与试用结果',spec:expect.objectContaining({ page_count:4,style:'学术简约',layout_mode:'editorial',content_density:'airy',notes:'保留已有结论' }) })));
  expect(await screen.findByRole('heading',{name:'测试'})).toBeInTheDocument();
  expect(useProjectStore.getState().pendingCommands).toEqual([{type:'run_workflow'}]);
 });
 it('a failed automatic creation exposes the retry action',async () => {
  vi.mocked(api.createProject).mockResolvedValue({ id:'proj_failed',status:'idle',spec:{ topic:'失败演示' },pages:[] });
  render(<App />); await screen.findByText('Folio 创作者');
  fireEvent.change(screen.getByRole('textbox',{name:'演示内容或制作要求'}),{target:{value:'制作一份演示'}});
  fireEvent.click(screen.getByRole('button',{name:'创建演示'}));
  await screen.findByRole('heading',{name:'失败演示'});
  act(() => { useProjectStore.getState().handleStatePatch({status:'failed',error:'额度不足'} as any); });
  expect(await screen.findByRole('button',{name:'重试未完成页面'})).toBeEnabled();
  expect(screen.getByRole('alert')).toHaveTextContent('额度不足');
 });
 it('opens workspace from sidebar and shows the real empty state',async () => {
  render(<App />); fireEvent.click(await screen.findByRole('button',{name:'我的工作空间'}));
  expect(await screen.findByText('你的第一份演示，从这里开始。')).toBeInTheDocument();
  expect(api.listProjects).toHaveBeenCalledWith(expect.objectContaining({ page:1,page_size:12,archived:false }));
 });
 it('saves profile and updates the sidebar identity',async () => {
  vi.mocked(api.updateProfile).mockResolvedValue({ ...account,profile:{ ...account.profile,display_name:'林间' } });
  render(<App />); fireEvent.click(await screen.findByRole('button',{name:'个人中心'}));
  fireEvent.change(await screen.findByRole('textbox',{name:'怎么称呼你'}),{target:{value:'林间'}});
  fireEvent.click(screen.getByRole('button',{name:'保存资料'}));
  await waitFor(() => expect(api.updateProfile).toHaveBeenCalledWith(expect.objectContaining({ display_name:'林间' })));
  await waitFor(() => expect(screen.getByRole('button',{name:'个人中心'})).toHaveTextContent('林间'));
  expect(screen.getByText('输出 Tokens')).toBeInTheDocument();
  expect(screen.getByText('本月额度不限')).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/服务端|持久化|保存到/);
 });
 it('restores a planned historical presentation without triggering new generation',async () => {
  window.location.hash = '/project/proj_history';
  vi.mocked(api.getProject).mockResolvedValue({ id:'proj_history',status:'planned',spec:{ topic:'历史演示' },pages:[],outline:[] });
  render(<App />); expect(await screen.findByRole('heading',{name:'历史演示'})).toBeInTheDocument();
  expect(useProjectStore.getState().pendingCommands).toHaveLength(0);
  expect(screen.getByRole('button',{name:'继续制作'})).toBeInTheDocument();
 });
 it('completion waits for an explicit download button click',async () => {
  vi.mocked(api.createProject).mockResolvedValue({ id:'proj_done',status:'idle',spec:{ topic:'手动下载' },pages:[] });
  render(<App />); await screen.findByText('Folio 创作者');
  fireEvent.change(screen.getByRole('textbox',{name:'演示内容或制作要求'}),{target:{value:'制作一份演示'}});
  fireEvent.click(screen.getByRole('button',{name:'创建演示'})); await screen.findByRole('heading',{name:'手动下载'});
  act(() => { useProjectStore.getState().handleStatePatch({status:'completed'} as any); useProjectStore.setState({lastDownloadUrl:'/storage/proj_done.pptx'}); });
  const button=await screen.findByRole('button',{name:'下载 PowerPoint'});
  expect(downloadFile).not.toHaveBeenCalled(); fireEvent.click(button);
  await waitFor(() => expect(downloadFile).toHaveBeenCalledOnce());
  expect(downloadFile).toHaveBeenCalledWith('/storage/proj_done.pptx','手动下载');
 });
 it('applies all selected directions as defaults',async () => {
  vi.mocked(api.updateProfile).mockResolvedValue(account);
  render(<App />); fireEvent.click(await screen.findByRole('button',{name:'创作方案'}));
  fireEvent.click(await screen.findByRole('button',{name:/^复古印刷/}));
  fireEvent.click(screen.getByRole('button',{name:/^规整网格/}));
  await act(() => userEvent.click(screen.getByRole('combobox',{name:'内容密度'})));
  await act(() => userEvent.keyboard('{ArrowDown}{Enter}'));
  await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument());
  expect(screen.getByRole('group',{name:'演示风格'}).querySelectorAll('button')).toHaveLength(17);
  fireEvent.click(screen.getByRole('button',{name:'设为默认方案'}));
  await waitFor(() => expect(api.updateProfile).toHaveBeenCalledWith({preferences:expect.objectContaining({style:'复古印刷',layout_mode:'structured',content_density:'compact'})}));
 });
 it('retains download and exposes repair advice without marking the presentation failed',async () => {
  window.location.hash='/project/proj_review';
  vi.mocked(api.getProject).mockResolvedValue({id:'proj_review',status:'completed',spec:{topic:'检查建议示例'},pages:[{
   page_id:'p-1',page_type:'content',status:'completed',iteration:1,max_iterations:4,
   content:{title:'页面标题',subtitle:'',key_points:['观点'],bullet_points:['解释'],speaker_notes:''},layout:{layout_type:'title_content'},
   review:{status:'needs_revision',score:60,issues:[{issue_id:'advice',category:'readability',severity:'medium',target:'content',owner:'layout',description:'建议调整层级',suggested_action:'增加留白'}],suggestions:['增加留白'],warning:'已保留当前版本'}
  }]});
  render(<App />);
  await screen.findByRole('heading',{name:'检查建议示例'});
  act(() => useProjectStore.setState({lastDownloadUrl:'/storage/proj_review.pptx'}));
  expect(screen.getByRole('button',{name:'下载 PowerPoint'})).toBeEnabled();
  expect(screen.getByRole('status')).toHaveTextContent('1 页有调整建议');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('第 1 页的检查建议'));
  expect(screen.getByText('建议调整层级；增加留白')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'继续调整问题页'}));
  expect(useProjectStore.getState().pendingCommands).toContainEqual({type:'generate_parallel'});
  expect(useProjectStore.getState().project?.status).toBe('completed');
  expect(useProjectStore.getState().workflowPending).toBe(true);
  expect(downloadFile).not.toHaveBeenCalled();
 });
 it('restores the backend automatic image preference without replacing an explicit false',async () => {
  vi.mocked(api.getAccount).mockResolvedValue({...account,profile:{...account.profile,preferences:{...account.profile.preferences,auto_images:false}}});
  render(<App />); await screen.findByText('Folio 创作者');
  fireEvent.click(screen.getByRole('button',{name:'创作方案'}));
  await waitFor(()=>expect(screen.getByRole('checkbox',{name:'自动配图'})).not.toBeChecked());
  fireEvent.click(screen.getByRole('checkbox',{name:'自动配图'}));
  vi.mocked(api.updateProfile).mockResolvedValue(account);
  fireEvent.click(screen.getByRole('button',{name:'设为默认方案'}));
  await waitFor(()=>expect(api.updateProfile).toHaveBeenCalledWith(expect.objectContaining({preferences:expect.objectContaining({auto_images:true})})));
 });
});
