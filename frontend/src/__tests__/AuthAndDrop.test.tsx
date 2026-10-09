import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '@/App';
import { InputPanel } from '@/components/input';
import { PublicHome } from '@/components/layout/PublicHome';
import { api, setSessionCsrf } from '@/api/client';
import { useProjectStore } from '@/stores/projectStore';

vi.mock('@/hooks/useWebSocket',() => ({ useWebSocket:vi.fn() }));
vi.mock('@/api/client',() => ({ setSessionCsrf:vi.fn(),api:{ getSession:vi.fn(),getAccount:vi.fn(),login:vi.fn(),register:vi.fn(),logout:vi.fn(),uploadAndParse:vi.fn() } }));
const account:any={ profile:{ account_id:'user_a',display_name:'Alice',email:'a@example.test',preferences:{ style:'商务简约',page_count:8 } },membership:{name:'Folio Basic'}, account:{} };
beforeEach(() => {
  vi.clearAllMocks(); window.location.hash=''; useProjectStore.getState().clearProject(); useProjectStore.setState({draftInput:'',draftFiles:[]});
  vi.mocked(api.getSession).mockRejectedValue(new Error('请先登录 Folio'));
  vi.mocked(api.getAccount).mockResolvedValue(account);
});

describe('public site and server login',() => {
  it('shows rich landing content and redirects a private route without revealing the workbench',async () => {
    window.location.hash='/workspace'; render(<App />);
    expect(await screen.findByRole('heading',{name:/让想法展开/})).toBeInTheDocument();
    await waitFor(() => expect(window.location.hash).toBe('#/login'));
    expect(screen.getByRole('heading',{name:'三步，把想法展开成页。'})).toBeInTheDocument();
    expect(screen.queryByRole('textbox',{name:'演示内容或制作要求'})).not.toBeInTheDocument();
  });
  it('submits real credentials and loads the workbench after login',async () => {
    vi.mocked(api.login).mockResolvedValue({account,csrf_token:'csrf-a'});
    render(<App />); await screen.findByRole('textbox',{name:'登录邮箱'});
    fireEvent.change(screen.getByRole('textbox',{name:'登录邮箱'}),{target:{value:'a@example.test'}});
    fireEvent.change(screen.getByLabelText('密码'),{target:{value:'password-123'}});
    fireEvent.click(screen.getByRole('button',{name:'登录，展开想法'}));
    expect(await screen.findByRole('textbox',{name:'演示内容或制作要求'})).toBeInTheDocument();
    expect(api.login).toHaveBeenCalledWith('a@example.test','password-123');
    expect(setSessionCsrf).toHaveBeenCalledWith('csrf-a');
  });
  it('validates password confirmation before registering',async () => {
    window.location.hash='/register'; render(<PublicHome onAuthenticated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('怎么称呼你'),{target:{value:'Alice'}});
    fireEvent.change(screen.getByLabelText('登录邮箱'),{target:{value:'a@example.test'}});
    fireEvent.change(screen.getByLabelText('密码'),{target:{value:'password-123'}});
    fireEvent.change(screen.getByLabelText('确认密码'),{target:{value:'different-123'}});
    fireEvent.click(screen.getByRole('button',{name:'创建账号，开始创作'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('两次输入的密码不一致');
    expect(api.register).not.toHaveBeenCalled();
  });
  it('logout clears project commands and draft identity',async () => {
    window.location.hash='/home'; vi.mocked(api.getSession).mockResolvedValue({account,csrf_token:'csrf-a'}); vi.mocked(api.logout).mockResolvedValue();
    render(<App />); await screen.findByRole('textbox',{name:'演示内容或制作要求'});
    act(() => useProjectStore.setState({draftInput:'private notes',pendingCommands:[{type:'parse_input'}]}));
    fireEvent.click(screen.getByRole('button',{name:'退出登录'}));
    await screen.findByRole('textbox',{name:'登录邮箱'});
    expect(api.logout).toHaveBeenCalled(); expect(useProjectStore.getState().draftInput).toBe(''); expect(useProjectStore.getState().pendingCommands).toEqual([]);
  });
});

describe('document drop across the workbench',() => {
  it('accepts files dropped outside the upload box, prevents browser navigation and avoids duplicates',async () => {
    vi.mocked(api.uploadAndParse).mockResolvedValue({upload_id:'upload_a',filename:'notes.txt',content:'研究要点',content_preview:'研究要点'});
    const file=new File(['研究要点'],'notes.txt',{type:'text/plain'});
    render(<InputPanel mode="content" onSubmit={vi.fn()} />);
    fireEvent.dragEnter(document.body,{dataTransfer:{types:['Files'],files:[file]}});
    expect(screen.getByRole('status')).toHaveTextContent('松开，把文档放进来');
    const drop=new Event('drop',{bubbles:true,cancelable:true}); Object.defineProperty(drop,'dataTransfer',{value:{types:['Files'],files:[file]}});
    fireEvent(document.body,drop);
    expect(drop.defaultPrevented).toBe(true);
    expect(await screen.findByText('notes.txt')).toBeInTheDocument();
    expect(useProjectStore.getState().draftFiles[0].upload_id).toBe('upload_a');
    expect(useProjectStore.getState().draftInput).toBe('');
    expect(screen.getByRole('button',{name:'创建演示'})).toBeEnabled();
    fireEvent.drop(document.body,{dataTransfer:{types:['Files'],files:[file]}});
    await waitFor(() => expect(screen.queryByText('正在上传和解析…')).not.toBeInTheDocument());
    expect(api.uploadAndParse).toHaveBeenCalledTimes(1);
  });
  it('rejects unsupported files before uploading and leaves text drag unaffected',async () => {
    render(<InputPanel mode="content" onSubmit={vi.fn()} />);
    fireEvent.drop(document.body,{dataTransfer:{types:['Files'],files:[new File(['binary'],'old.doc')]}});
    await waitFor(() => expect(screen.queryByText('正在上传和解析…')).not.toBeInTheDocument());
    expect(api.uploadAndParse).not.toHaveBeenCalled();
    const drop=new Event('drop',{bubbles:true,cancelable:true}); Object.defineProperty(drop,'dataTransfer',{value:{types:['text/plain'],files:[]}}); fireEvent(document.body,drop);
    expect(drop.defaultPrevented).toBe(false);
  });
});
