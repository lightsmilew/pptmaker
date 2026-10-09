import { useState } from 'react';
import { ArrowRight, Check } from 'lucide-react';
import { DesignControls } from '@/components/input/DesignControls';
import { Button } from '@/components/ui';
import { useProjectStore } from '@/stores/projectStore';
import { api } from '@/api/client';
import type { Account } from '@/types/workspace';
import toast from 'react-hot-toast';

export function SettingsPage({ onBack, onAccountChange }: { onBack: () => void; onAccountChange: (account: Account) => void }) {
  const draft = useProjectStore(s => s.draftSpec); const [saving,setSaving] = useState(false);
  const saveDefaults = async () => { setSaving(true); try { onAccountChange(await api.updateProfile({ preferences: { style:draft.style || '商务简约',page_count:draft.page_count || 8,layout_mode:draft.layout_mode || 'auto',content_density:draft.content_density || 'balanced' } })); toast.success('已设为默认创作方案'); } catch (e) { toast.error((e as Error).message); } finally { setSaving(false); } };
  return <><div className="studio-heading"><p className="eyebrow">CREATIVE DIRECTION</p><h1>创作方案</h1><p>从内容的轮廓，到页面的节奏。为这次表达选一条方向。</p></div><DesignControls /><div className="direction-footer"><div><strong>{draft.page_count} 页 · {draft.style}</strong><p>面向{draft.audience || '通用受众'} · 选项即时用于下一次制作</p></div><div className="direction-footer-actions"><Button variant="outline" size="sm" isLoading={saving} onClick={saveDefaults}><Check size={14} />设为默认方案</Button><Button onClick={onBack}>返回制作工作台 <ArrowRight size={15} /></Button></div></div></>;
}
