// Page card component for displaying individual slides - Soft UI Style

import { clsx } from 'clsx';
import { FileText, Layout, CheckCircle2, Circle, AlertCircle, Edit2 } from 'lucide-react';
import { Badge } from '@/components/ui';
import type { PageData, PageStatus, PageType } from '@/types';

interface PageCardProps {
  page: PageData;
  isSelected?: boolean;
  onClick?: () => void;
  onEdit?: () => void;
}

const pageTypeLabels: Record<PageType, string> = {
  cover: '封面',
  toc: '目录',
  content: '内容',
  chart: '图表',
  table: '表格',
  conclusion: '总结',
  reference: '参考',
  thankyou: '致谢',
};

const pageTypeColors: Record<PageType, string> = {
  cover: 'bg-indigo-100 text-indigo-600',
  toc: 'bg-pink-100 text-pink-600',
  content: 'bg-cyan-100 text-cyan-600',
  chart: 'bg-amber-100 text-amber-600',
  table: 'bg-orange-100 text-orange-600',
  conclusion: 'bg-emerald-100 text-emerald-600',
  reference: 'bg-gray-100 text-gray-500',
  thankyou: 'bg-pink-100 text-pink-500',
};

const statusIcons: Record<PageStatus, typeof Circle> = {
  pending: Circle,
  writing: Circle,
  designing: Circle,
  rendering: Circle,
  reviewing: Circle,
  revising: Circle,
  completed: CheckCircle2,
  failed: AlertCircle,
};

const statusLabels: Record<PageStatus, string> = {
  pending: '待生成',
  writing: '撰写中',
  designing: '设计中',
  rendering: '渲染中',
  reviewing: '审核中',
  revising: '修订中',
  completed: '已完成',
  failed: '失败',
};

const statusClasses: Record<PageStatus, string> = {
  pending: 'text-gray-400',
  writing: 'text-amber-500 animate-pulse',
  designing: 'text-amber-500 animate-pulse',
  rendering: 'text-amber-500 animate-pulse',
  reviewing: 'text-amber-500 animate-pulse',
  revising: 'text-amber-500 animate-pulse',
  completed: 'text-emerald-500',
  failed: 'text-red-500',
};

export function PageCard({ page, isSelected, onClick, onEdit }: PageCardProps) {
  const StatusIcon = statusIcons[page.status];
  const keyPoints = page.content?.key_points ?? [];

  return (
    <div
      onClick={onClick}
      className={clsx(
        'group relative bg-white rounded-3xl p-5 cursor-pointer transition-all duration-300',
        'hover:shadow-soft-xl hover:-translate-y-1',
        isSelected ? 'ring-2 ring-indigo-400 shadow-soft-lg' : 'shadow-soft-md'
      )}
    >
      {/* Page number & type */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-medium text-gray-400">第{page.page_id}页</span>
        <Badge variant={page.page_type as any} className={pageTypeColors[page.page_type]}>
          {pageTypeLabels[page.page_type]}
        </Badge>
      </div>

      {/* Title */}
      <h4 className="text-lg font-semibold text-gray-800 mb-2 line-clamp-1">
        {page.content?.title || '未命名'}
      </h4>

      {/* Subtitle */}
      {page.content?.subtitle && (
        <p className="text-sm text-gray-400 mb-4 line-clamp-1">{page.content.subtitle}</p>
      )}

      {/* Key points preview */}
      {keyPoints.length > 0 && (
        <div className="space-y-2 mb-4">
          {keyPoints.slice(0, 3).map((point: string, i: number) => (
            <div key={i} className="flex items-start gap-2">
              <span className="text-indigo-400 mt-0.5">•</span>
              <span className="text-sm text-gray-500 line-clamp-1">{point}</span>
            </div>
          ))}
          {keyPoints.length > 3 && (
            <span className="text-xs text-gray-400">+{keyPoints.length - 3} 更多</span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
        <div className="flex items-center gap-2 text-gray-400">
          <StatusIcon className={clsx('w-4 h-4', statusClasses[page.status])} />
          <span className="text-xs font-medium">{statusLabels[page.status]}</span>
        </div>

        {page.layout?.layout_type && (
          <div className="flex items-center gap-1 text-xs text-gray-400">
            <Layout className="w-3.5 h-3.5" />
            {page.layout.layout_type}
          </div>
        )}
      </div>

      {/* Edit button on hover */}
      {onEdit && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onEdit();
          }}
          className="absolute top-3 right-3 p-2 rounded-xl bg-gray-100 opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-indigo-100 hover:text-indigo-600"
        >
          <Edit2 className="w-4 h-4 text-gray-500" />
        </button>
      )}
    </div>
  );
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
