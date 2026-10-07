import { useState } from 'react';
import { ArrowRight, Check } from 'lucide-react';
import { InputPanel } from '@/components/input';
import { Button } from '@/components/ui';
import { useProjectStore } from '@/stores/projectStore';
import { api } from '@/api/client';
import type { Account } from '@/types/workspace';
import toast from 'react-hot-toast';

export function SettingsPage({ onBack, onAccountChange }: { onBack: () => void; onAccountChange: (account: Account) => void }) {
  const draft = useProjectStore(s => s.draftSpec); const [saving,setSaving] = useState(false);
  const saveDefaults = async () => { setSaving(true); try { onAccountChange(await api.updateProfile({ preferences: { style:draft.style || '商务简约',page_count:draft.page_count || 8 } })); toast.success('默认风格和页数已保存'); } catch (e) { toast.error((e as Error).message); } finally { setSaving(false); } };
  return <><div className="studio-heading"><p className="eyebrow">PRESENTATION SETTINGS</p><h1>为这次演示，做好准备。</h1><p>选择适合内容的页数、受众与结构。你的想法会保留在制作工作台。</p></div><InputPanel mode="settings" onSubmit={() => {}} /><div className="settings-summary"><div><span className="eyebrow">YOUR NEXT PRESENTATION</span><h2>{draft.page_count} 页 · {draft.style}</h2><p>面向{draft.audience || '通用受众'} · {[draft.needs_cover && '封面',draft.needs_toc && '目录',draft.needs_summary && '总结',draft.needs_chart && '图表'].filter(Boolean).join(' / ') || '自由内容结构'}</p></div><Button onClick={onBack}>返回制作工作台 <ArrowRight size={16} /></Button></div><div className="settings-bottom"><p>本次选项即时生效。保存默认值后，下次打开会沿用风格和页数。</p><Button variant="outline" size="sm" isLoading={saving} onClick={saveDefaults}><Check size={14} />保存为默认值</Button></div></>;
}
