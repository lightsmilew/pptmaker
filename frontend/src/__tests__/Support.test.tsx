import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { SupportPage } from '@/components/support/SupportPage';
import { useSupportNotifications } from '@/hooks/useSupportNotifications';
import { supportApi } from '@/api/supportClient';
import toast from 'react-hot-toast';

vi.mock('@/api/supportClient',()=>({supportApi:vi.fn()}));
vi.mock('react-hot-toast',()=>({default:Object.assign(vi.fn(),{error:vi.fn(),dismiss:vi.fn()})}));
const messages = [{id:1,author_role:'admin',text:'请补充页面截图',created_at:'2026-10-10T02:00:00Z',images:[]}];
const thread={conversation:{user_id:'u1',email:'example@test.example',display_name:'创作者',status:'open',unread:1},messages:{items:messages,has_more:false,before:1}};
const api={eventsUrl:'/api/v1/support/events',thread:vi.fn(),read:vi.fn(),send:vi.fn(),inbox:vi.fn(),status:vi.fn()};
beforeEach(()=>{ vi.clearAllMocks(); class TestURL extends URL { static createObjectURL() { return 'blob:preview'; } static revokeObjectURL() {} } vi.stubGlobal('URL',TestURL); vi.mocked(supportApi).mockReturnValue(api as unknown as ReturnType<typeof supportApi>); api.thread.mockResolvedValue(thread); api.read.mockResolvedValue({ok:true}); api.send.mockResolvedValue({id:2}); });
afterEach(()=>{ vi.unstubAllGlobals(); });

it('renders saved history and sends text with image attachments',async()=>{
  render(<SupportPage />); await screen.findByText('请补充页面截图');
  await waitFor(()=>expect(api.read).toHaveBeenCalledWith('',1));
  fireEvent.change(screen.getByRole('textbox',{name:'消息内容'}),{target:{value:'第2页出现排版问题'}});
  const file=new File(['test-image'],'preview.png',{type:'image/png'});
  fireEvent.change(document.querySelector('input[type=file]')!,{target:{files:[file]}});
  expect(screen.getByAltText('preview.png')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'发送消息'}));
  await waitFor(()=>expect(api.send).toHaveBeenCalledWith('','第2页出现排版问题',[file],expect.any(String)));
  await waitFor(()=>expect(screen.getByRole('textbox',{name:'消息内容'})).toHaveValue(''));
});

it('opens an admin conversation and updates its handling status',async()=>{
  api.inbox.mockResolvedValue({items:[{...thread.conversation,last_text:'我的问题',updated_at:null}],total:1,page:1,page_size:20});
  render(<SupportPage admin />);
  fireEvent.click(await screen.findByRole('button',{name:/创作者.*我的问题/}));
  fireEvent.click(await screen.findByRole('button',{name:'标记已处理'}));
  await waitFor(()=>expect(api.status).toHaveBeenCalledWith('u1','closed'));
});

it('pastes files and drops images anywhere in the conversation, with removable previews and downloadable history',async()=>{
  api.thread.mockResolvedValue({...thread,messages:{...thread.messages,items:[{...messages[0],files:[{id:'f1',url:'/api/v1/support/files/f1',filename:'saved.pdf',size:50}]}]}});
  render(<SupportPage />); await screen.findByText('请补充页面截图');
  expect(screen.getByRole('link',{name:/saved.pdf/})).toHaveAttribute('download','saved.pdf');
  const doc=new File(['document'],'reference.pdf',{type:'application/pdf'});
  fireEvent.paste(document.body,{clipboardData:{files:[doc],items:[]}});
  expect(screen.getByText('reference.pdf')).toBeInTheDocument();
  const image=new File(['image'],'dropped.png',{type:'image/png'});
  fireEvent.dragEnter(document.body,{dataTransfer:{types:['Files'],files:[image]}});
  expect(screen.getByRole('status')).toHaveTextContent('松开，添加图片或文件');
  fireEvent.drop(document.body,{dataTransfer:{types:['Files'],files:[image]}});
  expect(screen.getByAltText('dropped.png')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'移除附件 1'}));
  expect(screen.queryByText('reference.pdf')).not.toBeInTheDocument();
  fireEvent.paste(document.body,{clipboardData:{files:[],items:[{kind:'file',getAsFile:()=>doc}]}});
  fireEvent.click(screen.getByRole('button',{name:'发送消息'}));
  await waitFor(()=>expect(api.send).toHaveBeenCalledWith('','',[image,doc],expect.any(String)));
});

it('receives global notifications, refreshes streams after session rotation and closes on expiration',async()=>{
  class Events {
    static created:Events[]=[]; handlers:Record<string,EventListener>={}; close=vi.fn();
    constructor(public url:string) { Events.created.push(this); }
    addEventListener(name:string,callback:EventListener) { this.handlers[name]=callback; }
  }
  vi.stubGlobal('EventSource',Events); window.location.hash='/home';
  function Notifications({sessionKey}:{sessionKey:string}) { const count=useSupportNotifications('u1',false,sessionKey); return <span>{count} 未读</span>; }
  const {rerender}=render(<Notifications sessionKey="initial" />); const first=Events.created[0];
  act(()=>first.handlers.support(new MessageEvent('support',{data:JSON.stringify({unread:1,last_message_id:2,revision:'now'})})));
  expect(screen.getByText('1 未读')).toBeInTheDocument(); expect(toast).toHaveBeenCalledOnce();
  rerender(<Notifications sessionKey="rotated" />); expect(first.close).toHaveBeenCalled();
  const current=Events.created[1]; const expired=vi.fn(); window.addEventListener('folio-session-expired',expired);
  act(()=>current.handlers.expired(new Event('expired'))); expect(expired).toHaveBeenCalledOnce(); expect(current.close).toHaveBeenCalled();
  window.removeEventListener('folio-session-expired',expired);
});
