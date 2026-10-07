import type { ProjectStatus } from '@/types';
export const statusLabels: Record<ProjectStatus, string> = { idle: '待开始', parsing: '整理材料', parsed: '材料就绪', planning: '规划大纲', planned: '大纲就绪', generating: '制作中', reviewing: '检查中', rendering: '导出中', editing: '待重新导出', completed: '已完成', failed: '需重试' };
export const isBusy = (status?: ProjectStatus) => !!status && ['parsing', 'planning', 'generating', 'reviewing', 'rendering'].includes(status);
export function dateLabel(date?: string | null, timezone?: string) {
  return date ? new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', ...(timezone ? { timeZone: timezone } : {}) }).format(new Date(date)) : '—';
}
export const numberLabel = (value: number) => new Intl.NumberFormat('zh-CN').format(value);
export async function downloadFile(url: string, title: string) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`下载失败：HTTP ${response.status}`);
  const objectUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = objectUrl; link.download = `${title.replace(/[\\/:*?"<>|]/g, '_') || 'Folio'}.pptx`;
  document.body.appendChild(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
