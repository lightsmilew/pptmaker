import { CheckCircle2, Circle, AlertCircle, Edit2, FileText } from 'lucide-react';
import type { PageData, PageType } from '@/types';
const labels: Record<PageType,string> = { cover:'封面',toc:'目录',content:'内容',chart:'图表',table:'表格',conclusion:'总结',reference:'参考',thankyou:'致谢' };
const statuses = { pending:'待制作',writing:'撰写中',designing:'设计中',rendering:'渲染中',reviewing:'检查中',revising:'调整中',completed:'已完成',failed:'失败' };
export function PageCard({ page, isSelected, onClick, onEdit }: { page:PageData; isSelected?:boolean; onClick?:()=>void; onEdit?:()=>void }) {
 const Icon = page.status === 'completed' ? CheckCircle2 : page.status === 'failed' ? AlertCircle : Circle;
 return <div className={`slide-list-item ${isSelected ? 'selected' : ''}`}><button className="slide-select" aria-pressed={!!isSelected} onClick={onClick}><span className="slide-number">{page.page_id.replace(/^page[-_]/, '').padStart(2,'0')}</span><span className="slide-copy"><strong>{page.content?.title || '等待内容'}</strong><small>{labels[page.page_type]} · {statuses[page.status]}</small></span><Icon size={14} className={page.status === 'failed' ? 'text-red-600' : ''} /></button>{onEdit && <button className="icon-button" aria-label={`编辑第 ${page.page_id} 页`} onClick={onEdit}><Edit2 size={14} /></button>}</div>;
}

// Page list component
interface PageListProps {
  pages: PageData[];
  selectedIndex?: number;
  onSelectPage?: (index: number) => void;
  onEditPage?: (index: number) => void;
}

export function PageList({ pages, selectedIndex, onSelectPage, onEditPage }: PageListProps) {
  const validPages = pages.filter(Boolean);

  if (validPages.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="w-20 h-20 rounded-3xl bg-gray-100 flex items-center justify-center mx-auto mb-4">
          <FileText className="w-10 h-10 text-gray-300" />
        </div>
        <p className="text-gray-500 font-medium">还没有生成任何页面</p>
        <p className="text-sm text-gray-400 mt-1">点击上方按钮开始生成</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {validPages.map((page, index) => (
        <PageCard
          key={page.page_id || index}
          page={page}
          isSelected={selectedIndex === index}
          onClick={() => onSelectPage?.(index)}
          onEdit={() => onEditPage?.(index)}
        />
      ))}
    </div>
  );
}
