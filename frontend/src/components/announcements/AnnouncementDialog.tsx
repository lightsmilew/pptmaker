import { useEffect, useRef, useState } from 'react';
import { Button, Modal, ModalContent, ModalTitle, ModalDescription } from '@/components/ui';
import { api } from '@/api/client';
import type { Announcement } from '@/api/announcements';
import './announcements.css';

export function AnnouncementDialog({ sessionKey }: { sessionKey: string }) {
  const [items,setItems] = useState<Announcement[]>([]);
  const [daily,setDaily] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const ticket = useRef(0);
  const seen = useRef(new Set<string>());
  const seenDay = useRef('');
  useEffect(() => {
    let active = true; const version = ++ticket.current;
    seen.current.clear(); setItems([]); setError(''); setBusy(false); setDaily(false);
    const load = () => { void api.getAnnouncements().then(data => {
      if(active && version === ticket.current) {
        if(seenDay.current !== data.day) { seen.current.clear(); seenDay.current = data.day; }
        setItems(data.items.filter(n => !seen.current.has(n.id+':'+n.revision)));
      }
    }).catch(() => { /* A failed background refresh never invents a notice. */ }); };
    load(); window.addEventListener('focus',load);
    return () => { active = false; ticket.current++; window.removeEventListener('focus',load); };
  },[sessionKey]);
  const notice = items[0];
  const close = async () => {
    if(!notice || busy) return;
    const version = ticket.current; setBusy(true); setError('');
    try {
      if(daily) await api.dismissAnnouncement(notice.id,notice.revision);
      if(version !== ticket.current) return;
      seen.current.add(notice.id+':'+notice.revision);
      setItems(list => list.filter(n => n.id !== notice.id)); setDaily(false);
    } catch(e) { if(version === ticket.current) setError((e as Error).message); }
    finally { if(version === ticket.current) setBusy(false); }
  };
  return <Modal open={!!notice} onOpenChange={open => { if(!open) void close(); }}><ModalContent className="notice-dialog" onPointerDownOutside={e=>e.preventDefault()}>
    <p className="eyebrow">FOLIO / A NOTE FOR YOU{items.length > 1 ? ` · 还有 ${items.length} 条` : ''}</p>
    <ModalTitle>{notice?.title}</ModalTitle><ModalDescription>来自 Folio 的消息</ModalDescription>
    <div className="notice-body">{notice?.body}</div>
    {error && <p role="alert" className="field-error">{error}</p>}
    <div className="notice-footer"><label><input type="checkbox" checked={daily} disabled={busy} onChange={e=>setDaily(e.target.checked)} />当日不再展示</label><Button isLoading={busy} onClick={()=>void close()}>知道了</Button></div>
  </ModalContent></Modal>;
}
