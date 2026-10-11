import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Paperclip, FileText, Download, MessageSquare, Send, X, ArrowLeft } from 'lucide-react';
import toast from 'react-hot-toast';
import { Button, Input, Textarea } from '@/components/ui';
import { supportApi, type SupportInbox, type SupportMessage, type SupportThread } from '@/api/supportClient';
import { transferFiles, isPreviewImage } from '@/lib/fileTransfer';
import './support.css';

const time = (value:string) => new Date(value).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
export function SupportPage({ admin = false }: { admin?:boolean }) {
  const api = useMemo(()=>supportApi(admin),[admin]);
  const [uid,setUid] = useState(''); const [inbox,setInbox] = useState<SupportInbox | null>(null);
  const [q,setQ] = useState(''); const [search,setSearch] = useState(''); const [page,setPage] = useState(1);
  const [error,setError] = useState(''); const [revision,setRevision] = useState(0);
  useEffect(()=>{
    const refresh=()=>setRevision(n=>n+1); window.addEventListener('folio-support-update',refresh);
    return()=>window.removeEventListener('folio-support-update',refresh);
  },[]);
  useEffect(()=>{
    if (!admin) return; let current=true;
    api.inbox(q,page).then(data=>{ if(current) { setInbox(data); setError(''); } }).catch(e=>{ if(current) setError(e.message); });
    return()=>{ current=false; };
  },[api,admin,q,page,revision]);
  return <><div className="studio-heading support-heading"><p className="eyebrow">FOLIO / A LITTLE CONVERSATION</p><h1>{admin ? '每个问题，都值得回应。' : '有些想法，我们一起展开。'}</h1><p>{admin ? '查看创作者的问题，回复消息，跟进处理结果。' : '制作遇到问题，或有想告诉我们的建议？写下来，也可以附上截图。'}</p></div>
    <div className={`support-layout ${admin ? 'support-admin' : ''} ${uid ? 'has-conversation' : ''}`}>
      {admin && <aside className="support-inbox"><form onSubmit={e=>{ e.preventDefault(); setQ(search); setPage(1); }}><Input aria-label="搜索沟通账号" placeholder="邮箱或称呼" value={search} onChange={e=>setSearch(e.target.value)} /><Button type="submit" variant="outline" size="sm">搜索</Button></form><div className="support-inbox-caption"><span>用户沟通</span><span>{inbox?.total ?? '—'} 个会话</span></div>{error && <p role="alert" className="field-error">{error}<Button variant="ghost" size="sm" onClick={()=>setRevision(n=>n+1)}>重试</Button></p>}{!inbox && !error && <p role="status" className="support-empty">正在打开会话…</p>}{inbox?.items.map(c=><button className={`support-contact ${uid===c.user_id ? 'active' : ''}`} key={c.user_id} onClick={()=>setUid(c.user_id)}><span className="support-contact-top"><strong>{c.display_name}</strong>{c.unread>0 && <span className="support-badge" aria-label={`${c.unread} 条未读`}>{c.unread>99 ? '99+' : c.unread}</span>}</span><span className="support-contact-email">{c.email}</span><span className="support-contact-preview">{c.last_text || '附件消息'}</span><span className="support-contact-foot">{c.status==='closed' ? '已处理' : '沟通中'}<small>{c.updated_at ? time(c.updated_at) : ''}</small></span></button>)}{inbox && !inbox.total && <p className="support-empty">{q ? '没有找到相关会话。' : '收到用户消息后，会显示在这里。'}</p>}{inbox && inbox.total>inbox.page_size && <div className="support-pager"><Button size="sm" variant="ghost" disabled={page===1} onClick={()=>setPage(p=>p-1)}>上一页</Button><span>{page}</span><Button size="sm" variant="ghost" disabled={page*inbox.page_size>=inbox.total} onClick={()=>setPage(p=>p+1)}>下一页</Button></div>}</aside>}
      {(!admin || uid) ? <SupportChat key={uid || 'mine'} uid={uid} admin={admin} onBack={()=>setUid('')} /> : <section className="support-chat support-chat-placeholder"><MessageSquare size={25} /><h2>打开一个会话</h2><p>从左侧选择创作者，查看问题与历史消息。</p></section>}
    </div></>;
}

function SupportChat({ uid,admin,onBack }: { uid:string; admin:boolean; onBack:()=>void }) {
  const api=useMemo(()=>supportApi(admin),[admin]);
  const [thread,setThread]=useState<SupportThread | null>(null); const [error,setError]=useState('');
  const [text,setText]=useState(''); const [files,setFiles]=useState<File[]>([]); const [busy,setBusy]=useState(false);
  const [older,setOlder]=useState(false); const [statusBusy,setStatusBusy]=useState(false); const [dragActive,setDragActive]=useState(false);
  const dragDepth=useRef(0);
  const history=useRef<HTMLDivElement>(null); const input=useRef<HTMLInputElement>(null); const alive=useRef(true);
  const followHistory=useRef(true);
  const requestId=useRef(crypto.randomUUID()); const loadTicket=useRef(0);
  const previousAttempt=useRef<{text:string; files:File[]} | null>(null);
  const previews=useMemo(()=>files.map(file=>({file,url:isPreviewImage(file) ? URL.createObjectURL(file) : ''})),[files]);
  useEffect(()=>()=>previews.forEach(p=>{ if(p.url) URL.revokeObjectURL(p.url); }),[previews]);
  const markRead=useCallback((messages:SupportMessage[])=>{
    if (document.visibilityState!=='visible' || !messages.length) return;
    void api.read(uid,messages[messages.length-1].id).catch(e=>{ if(alive.current) setError(e.message); });
  },[api,uid]);
  const load=useCallback(async()=>{
    const ticket=++loadTicket.current;
    try {
      const data=await api.thread(uid);
      if(!alive.current || ticket!==loadTicket.current) return;
      setThread(previous=>previous ? {...data,messages:{...previous.messages,items:[...new Map([...previous.messages.items,...data.messages.items].map(m=>[m.id,m])).values()].sort((a,b)=>a.id-b.id)}} : data);
      setError(''); markRead(data.messages.items);
    } catch(e) { if(alive.current && ticket===loadTicket.current) setError((e as Error).message); }
  },[api,uid,markRead]);
  useEffect(()=>{
    alive.current=true; void load();
    const visible=()=>{ if(document.visibilityState==='visible') void load(); };
    window.addEventListener('folio-support-update',load); document.addEventListener('visibilitychange',visible);
    return()=>{ alive.current=false; loadTicket.current++; window.removeEventListener('folio-support-update',load); document.removeEventListener('visibilitychange',visible); };
  },[load]);
  const lastId=thread?.messages.items[thread.messages.items.length-1]?.id;
  useEffect(()=>{ const element=history.current; if(element) element.scrollTop=element.scrollHeight; },[lastId]);
  const add=useCallback((incoming:File[])=>{
    const next=[...files,...incoming];
    if(next.length>3) { toast.error('每条消息最多3个附件'); return; }
    if(incoming.some(f=>f.size>(isPreviewImage(f) ? 5 : 10)*1024*1024)) { toast.error('图片最大5 MiB，其他文件最大10 MiB'); return; }
    if(incoming.some(f=>f.type.startsWith('image/') && !isPreviewImage(f))) { toast.error('图片支持 PNG、JPEG 和 WebP'); return; }
    setFiles(next);
  },[files]);
  useEffect(()=>{
    const isFile=(e:DragEvent)=>Array.from(e.dataTransfer?.types || []).includes('Files');
    const reset=()=>{ dragDepth.current=0; setDragActive(false); };
    const enter=(e:DragEvent)=>{ if(!isFile(e)) return; e.preventDefault(); dragDepth.current++; if(!busy) setDragActive(true); };
    const leave=(e:DragEvent)=>{ if(!isFile(e)) return; dragDepth.current=Math.max(0,dragDepth.current-1); if(!dragDepth.current) setDragActive(false); };
    const over=(e:DragEvent)=>{ if(isFile(e)) { e.preventDefault(); if(e.dataTransfer) e.dataTransfer.dropEffect=busy ? 'none' : 'copy'; } };
    const drop=(e:DragEvent)=>{ if(!isFile(e) && !e.dataTransfer?.files.length) return; e.preventDefault(); reset(); if(!busy && e.dataTransfer) add(transferFiles(e.dataTransfer)); };
    const paste=(e:ClipboardEvent)=>{ const incoming=e.clipboardData ? transferFiles(e.clipboardData) : []; if(!incoming.length) return; e.preventDefault(); if(!busy) add(incoming); };
    document.addEventListener('dragenter',enter); document.addEventListener('dragleave',leave); document.addEventListener('dragover',over); document.addEventListener('drop',drop); document.addEventListener('paste',paste); window.addEventListener('blur',reset); window.addEventListener('dragend',reset);
    return()=>{ document.removeEventListener('dragenter',enter); document.removeEventListener('dragleave',leave); document.removeEventListener('dragover',over); document.removeEventListener('drop',drop); document.removeEventListener('paste',paste); window.removeEventListener('blur',reset); window.removeEventListener('dragend',reset); };
  },[add,busy]);
  const submit=async(e:React.FormEvent)=>{
    e.preventDefault(); if(busy || (!text.trim() && !files.length)) return;
    if (previousAttempt.current && (previousAttempt.current.text!==text || previousAttempt.current.files.length!==files.length || files.some((f,i)=>f!==previousAttempt.current!.files[i]))) requestId.current=crypto.randomUUID();
    previousAttempt.current={text,files};
    setBusy(true); setError('');
    try { await api.send(uid,text,files,requestId.current); if(!alive.current) return; setText(''); setFiles([]); requestId.current=crypto.randomUUID(); await load(); }
    catch(e) { if(alive.current) setError((e as Error).message); }
    finally { if(alive.current) setBusy(false); }
  };
  return <section className="support-chat"><header className="support-chat-header"><div>{admin && <button className="support-back" aria-label="返回会话列表" onClick={onBack}><ArrowLeft size={17} /></button>}<span className="support-avatar">{admin ? thread?.conversation.display_name.slice(0,1) || 'F' : 'F'}</span><div><h2>{admin ? thread?.conversation.display_name || '用户沟通' : 'Folio 支持'}</h2><p>{admin ? thread?.conversation.email : '关于制作、账号，或一个新建议。'}</p></div></div><span className="support-status">{thread?.conversation.status==='closed' ? '已处理' : '沟通中'}</span>{admin && thread && <Button size="sm" variant="outline" isLoading={statusBusy} onClick={async()=>{ setStatusBusy(true); try { await api.status(uid,thread.conversation.status==='closed' ? 'open' : 'closed'); await load(); } catch(e) { setError((e as Error).message); } finally { setStatusBusy(false); } }}>{thread.conversation.status==='closed' ? '重新打开' : '标记已处理'}</Button>}</header>
    <div className="support-history" ref={history} role="log" aria-label="沟通消息" aria-live="polite" onScroll={()=>{ const el=history.current; if(el) followHistory.current=el.scrollHeight-el.scrollTop-el.clientHeight<80; }}>
      {!thread && !error && <p role="status" className="support-empty">正在打开消息…</p>}
      {thread?.messages.has_more && <Button size="sm" variant="ghost" isLoading={older} className="support-older" onClick={async()=>{ setOlder(true); const height=history.current?.scrollHeight || 0; try { const data=await api.thread(uid,thread.messages.before || undefined); if(!alive.current) return; setThread(previous=>previous ? {...previous,messages:{...data.messages,items:[...data.messages.items,...previous.messages.items]}} : data); requestAnimationFrame(()=>{ if(history.current) history.current.scrollTop=history.current.scrollHeight-height; }); } catch(e) { if(alive.current) setError((e as Error).message); } finally { if(alive.current) setOlder(false); } }}>查看更早的消息</Button>}
      {thread && !thread.messages.items.length && <div className="support-empty-start"><MessageSquare size={24} /><h3>从一句话开始。</h3><p>描述遇到的情况，附上演示标题或截图，<br />能帮助我们更快理解你的问题。</p></div>}
      {thread?.messages.items.map(m=><article key={m.id} className={`support-message ${m.author_role===(admin ? 'admin' : 'user') ? 'is-mine' : ''}`}><div className="support-message-meta"><strong>{m.author_role==='admin' ? 'Folio 管理员' : admin ? thread.conversation.display_name : '你'}</strong><time dateTime={m.created_at}>{time(m.created_at)}</time></div><div className="support-bubble">{m.text && <p>{m.text}</p>}{!!m.images.length && <div className="support-images">{m.images.map(img=><a key={img.id} href={img.url} target="_blank" rel="noreferrer" aria-label={`查看图片：${img.filename}`}><img src={img.thumbnail_url || img.url} alt={img.filename} loading="lazy" decoding="async" width={img.width} height={img.height} onLoad={()=>{ if(followHistory.current && history.current) history.current.scrollTop=history.current.scrollHeight; }} /></a>)}</div>}{!!m.files?.length && <div className="support-file-list">{m.files.map(file=><a key={file.id} className="support-file-card" href={file.url} download={file.filename}><FileText size={18} /><span>{file.filename}<small>{(file.size/1024).toFixed(1)} KB</small></span><Download size={14} /></a>)}</div>}</div></article>)}
    </div>
    {error && <div className="support-error" role="alert">{error}<Button size="sm" variant="ghost" onClick={load}>重试加载</Button></div>}
    <form className={`support-composer ${dragActive ? 'is-dragging' : ''}`} onSubmit={submit}>
      {dragActive && <div className="support-drop-hint" role="status"><Paperclip size={16} />松开，添加图片或文件。</div>}
      {!!previews.length && <div className="support-attachments">{previews.map((p,i)=><div key={i} className={p.url ? '' : 'support-file-draft'}>{p.url ? <img src={p.url} alt={p.file.name} /> : <><FileText size={18} /><span>{p.file.name}<small>{(p.file.size/1024).toFixed(1)} KB</small></span></>}<button type="button" aria-label={`移除附件 ${i+1}`} disabled={busy} onClick={()=>setFiles(list=>list.filter((_,index)=>index!==i))}><X size={13} /></button></div>)}</div>}
      <Textarea aria-label="消息内容" placeholder={admin ? '写下回复…' : '告诉我们你遇到的问题…'} rows={3} maxLength={4000} value={text} disabled={busy} onChange={e=>setText(e.target.value)} />
      <div className="support-composer-actions"><input ref={input} type="file" multiple hidden onChange={e=>{ add([...(e.target.files || [])]); e.target.value=''; }} /><Button type="button" size="sm" variant="ghost" disabled={busy || files.length>=3} onClick={()=>input.current?.click()}><Paperclip size={16} />添加附件</Button><small>最多3个 · 图片5 MiB / 文件10 MiB · 拖入或 Ctrl+V</small><Button size="sm" type="submit" isLoading={busy} disabled={!thread || (!text.trim() && !files.length)}><Send size={14} />发送消息</Button></div>
    </form>
  </section>;
}
