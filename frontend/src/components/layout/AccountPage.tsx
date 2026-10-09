import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, Crown, RefreshCw } from 'lucide-react';
import { Button, Card, Input, Select, Textarea } from '@/components/ui';
import { api } from '@/api/client';
import type { Account, Profile } from '@/types/workspace';
import { dateLabel, numberLabel } from './pageUtils';
import toast from 'react-hot-toast';
import { PasswordSettings } from './PasswordSettings';

export function AccountPage({ account, error, onChange, onRefresh }: { account: Account | null; error: string; onChange: (account: Account) => void; onRefresh: () => Promise<void> }) {
  const [draft, setDraft] = useState<Profile | null>(account?.profile || null);
  const [saving, setSaving] = useState(false); const [refreshing, setRefreshing] = useState(false);
  const dirty = useRef(false);
  useEffect(() => { if (account && !dirty.current) setDraft(account.profile); }, [account?.profile]);
  const update = (key: keyof Profile, value: string) => { dirty.current = true; setDraft(p => p ? { ...p, [key]: value } : p); };
  const save = async () => {
    if (!draft) return; setSaving(true);
    try { const { display_name, email, company, occupation, bio, timezone } = draft; const saved = await api.updateProfile({ display_name, email, company, occupation, bio, timezone }); dirty.current = false; setDraft(saved.profile); onChange(saved); toast.success('个人资料已保存'); }
    catch (e) { toast.error((e as Error).message); } finally { setSaving(false); }
  };
  const refresh = async () => { setRefreshing(true); await onRefresh(); setRefreshing(false); };
  if (!account || !draft) return <><div className="studio-heading"><p className="eyebrow">YOUR SPACE, YOUR PACE</p><h1>个人中心</h1></div><div className="empty-state" role={error ? 'alert' : 'status'}>{error || '正在读取账号…'}{error && <Button variant="outline" onClick={refresh}>重新加载</Button>}</div></>;
  const { membership, usage } = account;
  const rate = usage.provider_cache_hit_rate === null ? '—' : `${(usage.provider_cache_hit_rate * 100).toFixed(1)}%`;
  const maxDaily = Math.max(...usage.daily.map(day => day.output_tokens), 1);
  return <>
    <div className="page-heading-row"><div className="studio-heading"><p className="eyebrow">YOUR SPACE, YOUR PACE</p><h1>让创作，按自己的节奏。</h1><p>管理你的资料，了解每一次表达的用量。</p></div><Button variant="outline" size="sm" isLoading={refreshing} onClick={refresh}><RefreshCw size={14} />刷新用量</Button></div>
    {error && <p className="studio-error" role="alert">{error}</p>}
    <div className="account-identity"><span className="identity-avatar">{account.profile.display_name.slice(0,1)}</span><div><h2>{account.profile.display_name}</h2><p>{[account.profile.occupation, account.profile.company].filter(Boolean).join(' · ') || '把想法写下来，把故事展开。'}</p></div><span className="membership-label">{membership.is_vip && <Crown size={15} />}{membership.name}{membership.status === 'expired' ? ' · 已到期' : ''}</span></div>
    <div className="account-grid">
      <Card className="profile-panel"><div className="section-heading"><h2><span className="section-index">01</span>个人资料</h2></div><form onSubmit={e => { e.preventDefault(); save(); }}><div className="form-grid"><Input label="怎么称呼你" required maxLength={40} value={draft.display_name} onChange={e => update('display_name',e.target.value)} /><Input label="联系邮箱" type="email" maxLength={254} placeholder="选填" value={draft.email} onChange={e => update('email',e.target.value)} /><Input label="机构 / 公司" maxLength={80} placeholder="选填" value={draft.company} onChange={e => update('company',e.target.value)} /><Input label="职业 / 身份" maxLength={60} placeholder="选填" value={draft.occupation} onChange={e => update('occupation',e.target.value)} /></div><div className="form-block"><Textarea label="一句话介绍" rows={2} maxLength={200} placeholder="你正在探索的方向，或想表达的事情。" value={draft.bio} onChange={e => update('bio',e.target.value)} /></div><div className="form-block"><Select label="时区" value={draft.timezone} onValueChange={timezone => update('timezone',timezone)} options={[{ value: 'Asia/Shanghai',label:'上海 · UTC+8' },{ value: 'UTC',label:'UTC' },{ value: 'Asia/Tokyo',label:'东京 · UTC+9' },{ value: 'Europe/London',label:'伦敦' },{ value: 'America/New_York',label:'纽约' }]} /></div><div className="form-actions"><span>联系邮箱未验证，用于资料记录。</span><Button type="submit" isLoading={saving} disabled={!draft.display_name.trim()}>保存资料 <Check size={14} /></Button></div></form></Card>
      <div className="account-aside"><Card className="membership-panel"><div className="section-heading"><h2><span className="section-index">02</span>会员与权益</h2>{membership.is_vip && <Crown size={17} />}</div><p className="membership-name">{membership.name}</p><p className="membership-description">{membership.is_vip ? '让更多想法成为完整的作品。' : '从灵感开始，让每一份作品有序展开。'}</p><ul className="benefit-list">{membership.features.map(feature => <li key={feature}><Check size={13} />{feature}</li>)}</ul><dl className="detail-list"><div><dt>单份演示</dt><dd>最多 {membership.limits.max_pages} 页</dd></div><div><dt>并行制作</dt><dd>{membership.limits.concurrency} 页</dd></div><div><dt>有效期</dt><dd>{membership.expires_at ? dateLabel(membership.expires_at,draft.timezone) : '长期有效'}</dd></div></dl><p className="micro-note">了解你的会员权益与创作额度。</p></Card></div>
    </div>
    <Card className="usage-panel"><div className="section-heading"><h2><span className="section-index">03</span>用量与额度</h2><span>{usage.period} · 按 UTC 月份统计</span></div><div className="usage-metrics">{[{ label:'输出 Tokens',value:numberLabel(usage.output_tokens),note:'本月实际模型输出' },{ label:'输入 Tokens',value:numberLabel(usage.input_tokens),note:`已缓存 ${numberLabel(usage.cached_input_tokens)}` },{ label:'输入缓存命中',value:rate,note:'服务商报告的 Token 比例' },{ label:'模型调用',value:numberLabel(usage.calls),note:`成功 ${numberLabel(usage.successful_calls)} 次` }].map(metric => <div key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.note}</small></div>)}</div><div className="quota-row"><div><h3>本月输出额度</h3><p>{usage.quota.is_unlimited ? '本月额度不限' : `剩余 ${numberLabel(usage.quota.remaining || 0)} / ${numberLabel(usage.quota.limit || 0)} Tokens`}{usage.quota.reserved > 0 ? ` · 进行中的调用预留 ${numberLabel(usage.quota.reserved)}` : ''}</p></div><span>{dateLabel(usage.resets_at,'UTC')} UTC 重置</span></div>{usage.quota.limit && <div className="quota-track" role="progressbar" aria-label="本月额度使用" aria-valuemin={0} aria-valuemax={usage.quota.limit} aria-valuenow={usage.quota.used}><span style={{ width:`${Math.min(100, usage.quota.used / usage.quota.limit * 100)}%` }} /></div>}
      {usage.daily.length ? <div className="usage-chart" role="img" aria-label={`本月 ${usage.daily.length} 天有调用记录，输出共 ${numberLabel(usage.output_tokens)} Tokens`}><div>{usage.daily.map(day => <div key={day.date} title={`${day.date}：${numberLabel(day.output_tokens)} 输出 Tokens / ${day.calls} 次调用`}><span style={{ height:`${Math.max(2,day.output_tokens / maxDaily * 70)}px` }} /><small>{day.date.slice(8)}</small></div>)}</div><p>每日输出 Tokens · 只显示有调用记录的日期</p></div> : <p className="usage-empty">开始制作后，这里会记录实际调用用量。</p>}
      <p className="micro-note">额度以本月实际输出 Tokens 计算，不代表模型服务商余额。</p>
    </Card>
    <PasswordSettings />
    <details className="account-details"><summary>账号与模型连接 <ChevronDown size={15} /></summary><dl className="detail-grid"><div><dt>账号 ID</dt><dd>{draft.account_id}</dd></div><div><dt>登录邮箱</dt><dd>{account.account.login_email}</dd></div><div><dt>账号类型</dt><dd>Folio 账号</dd></div><div><dt>创建时间</dt><dd>{dateLabel(draft.created_at,draft.timezone)}</dd></div><div><dt>模型连接</dt><dd>{account.account.provider_connected ? '已配置' : '尚未配置'}</dd></div><div><dt>服务地址</dt><dd>{account.account.provider_host || '未配置'}</dd></div><div><dt>默认模型</dt><dd>{account.account.model || '未配置'}</dd></div><div><dt>累计调用</dt><dd>{numberLabel(usage.lifetime_calls)} 次</dd></div><div><dt>结果缓存</dt><dd>{numberLabel(usage.response_cache_hits)} 次命中 / 本月</dd></div><div><dt>额外推理输出</dt><dd>{numberLabel(usage.reasoning_tokens)} Tokens / 本月</dd></div></dl><p className="micro-note">邮箱认证与在线支付尚未接入。</p></details>
  </>;
}
