import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { supportApi, type SupportNotification } from '@/api/supportClient';

export function useSupportNotifications(identity?: string, admin = false, sessionKey?:string) {
  const [unread,setUnread] = useState(0);
  useEffect(()=>{
    setUnread(0);
    if (!identity || typeof EventSource==='undefined') return;
    const events = new EventSource(supportApi(admin).eventsUrl);
    let previous:SupportNotification | undefined;
    const route = admin ? '/admin/support' : '/support';
    const receive = (event:MessageEvent) => {
      const snapshot = JSON.parse(event.data) as SupportNotification;
      setUnread(snapshot.unread);
      window.dispatchEvent(new CustomEvent('folio-support-update',{detail:snapshot}));
      if (snapshot.unread>0 && (!previous || snapshot.unread>previous.unread || (snapshot.last_incoming_id || 0)>(previous.last_incoming_id || 0)) && !(window.location.hash.startsWith('#'+route) && document.visibilityState==='visible')) {
        toast(t=><button className="support-toast" onClick={()=>{ window.location.hash=route; toast.dismiss(t.id); }}><strong>{admin ? '收到用户消息' : '管理员有新回复'}</strong><span>{snapshot.unread} 条未读 · 点击查看</span></button>,{id:'folio-support-notification',duration:6000});
      }
      previous=snapshot;
    };
    events.addEventListener('support',receive as EventListener);
    events.addEventListener('expired',()=>{ events.close(); window.dispatchEvent(new Event(admin ? 'folio-admin-expired' : 'folio-session-expired')); });
    return ()=>{ events.close(); toast.dismiss('folio-support-notification'); };
  },[identity,admin,sessionKey]);
  return unread;
}
