import { useState } from 'react';
import { Button, Card, Input } from '@/components/ui';
import { api, setSessionCsrf } from '@/api/client';
import toast from 'react-hot-toast';

export function PasswordSettings() {
  const [current,setCurrent] = useState(''); const [next,setNext] = useState(''); const [confirm,setConfirm] = useState('');
  const [busy,setBusy] = useState(false); const [error,setError] = useState('');
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    if (next !== confirm) { setError('两次输入的新密码不一致'); return; }
    setBusy(true);
    try { const session = await api.changePassword(current,next); setSessionCsrf(session.csrf_token); window.dispatchEvent(new CustomEvent('folio-session-refreshed',{detail:session})); setCurrent(''); setNext(''); setConfirm(''); toast.success('密码已更新，其他会话已退出'); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return <Card className="password-settings"><div className="section-heading"><h2>账号安全</h2><span>登录密码</span></div><form onSubmit={submit}><div className="form-grid"><Input label="当前密码" type="password" autoComplete="current-password" required maxLength={128} value={current} onChange={e => setCurrent(e.target.value)} disabled={busy} /><Input label="新密码" type="password" autoComplete="new-password" required minLength={10} maxLength={128} placeholder="至少 10 个字符" value={next} onChange={e => setNext(e.target.value)} disabled={busy} /><Input label="确认新密码" type="password" autoComplete="new-password" required minLength={10} maxLength={128} value={confirm} onChange={e => setConfirm(e.target.value)} disabled={busy} /></div>{error && <p className="studio-error" role="alert">{error}</p>}<div className="form-actions"><span>更新后，其他设备上的会话将失效。</span><Button type="submit" isLoading={busy}>更新密码</Button></div></form></Card>;
}
