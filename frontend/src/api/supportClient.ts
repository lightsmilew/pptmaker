import { getSessionRequestState, sessionExpired } from './client';
import { getAdminRequestState } from './adminClient';
import { isPreviewImage } from '@/lib/fileTransfer';
import { prepareImageUpload } from '@/lib/imageUpload';

export interface SupportImage { id:string; url:string; thumbnail_url?:string; filename:string; width:number; height:number }
export interface SupportFile { id:string; url:string; filename:string; size:number }
export interface SupportMessage { id:number; author_role:'user'|'admin'; text:string; created_at:string; images:SupportImage[]; files?:SupportFile[] }
export interface Conversation { user_id:string; email:string; display_name:string; status:'open'|'closed'; unread:number; updated_at:string | null; last_message_id:number | null; last_text:string | null }
export interface SupportThread { conversation:Conversation; messages:{ items:SupportMessage[]; has_more:boolean; before:number | null } }
export interface SupportInbox { items:Conversation[]; total:number; page:number; page_size:number }
export interface SupportNotification { unread:number; last_message_id:number; last_incoming_id?:number; revision:string }

export function supportApi(admin = false) {
  const base = admin ? '/api/v1/admin/support' : '/api/v1/support';
  const state = admin ? getAdminRequestState : getSessionRequestState;
  async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const current = state(); const form = body instanceof FormData;
    const response = await fetch(base+path,{ method,credentials:'same-origin',headers:{ 'X-Folio-Request':'1','X-CSRF-Token':current.csrf,...(!form ? {'Content-Type':'application/json'} : {}) },...(body === undefined ? {} : { body:form ? body as FormData : JSON.stringify(body) }) });
    if (state().version !== current.version) throw new Error('账号已更新，请重新打开会话');
    if (!response.ok) {
      if (response.status===401) { if(admin) window.dispatchEvent(new Event('folio-admin-expired')); else sessionExpired(); }
      const error = await response.json().catch(()=>({}));
      throw new Error(typeof error.detail==='string' ? error.detail : '消息操作失败，请重试');
    }
    return response.json();
  }
  const threadPath = (uid:string) => admin ? '/'+encodeURIComponent(uid) : '';
  return {
    eventsUrl:base+'/events',
    inbox:(q = '',page = 1) => request<SupportInbox>('?'+new URLSearchParams({q,page:String(page)})),
    thread:(uid = '',before?:number) => request<SupportThread>(threadPath(uid)+(before ? '?before='+before : '')),
    read:(uid:string,last_id:number) => request(threadPath(uid)+'/read','POST',{last_id}),
    send:async(uid:string,text:string,files:File[],requestId:string) => { const version=state().version; const form=new FormData(); form.append('text',text); form.append('request_id',requestId); for(const file of files) { const prepared=await prepareImageUpload(file,'support'); form.append(isPreviewImage(file) ? 'images' : 'files',prepared); } if(state().version!==version) throw new Error('账号已更新，请重新打开会话'); return request<{id:number}>(threadPath(uid)+'/messages','POST',form); },
    status:(uid:string,status:'open'|'closed') => request(threadPath(uid),'PATCH',{status}),
  };
}
