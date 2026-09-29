// Outline preview card — used during the plan phase to summarise the
// selected outline entry before full page generation kicks off.

import { clsx } from 'clsx';
import type { OutlineItem, PageType } from '@/types';

interface OutlinePreviewProps {
  outline: OutlineItem[];
  selectedIndex: number | null;
  className?: string;
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

const pageTypeBadgeColors: Record<PageType, string> = {
  cover: 'bg-purple-100 text-purple-600',
  toc: 'bg-blue-100 text-blue-600',
  content: 'bg-indigo-100 text-indigo-600',
  chart: 'bg-green-100 text-green-600',
  table: 'bg-orange-100 text-orange-600',
  conclusion: 'bg-amber-100 text-amber-600',
  reference: 'bg-gray-100 text-gray-600',
  thankyou: 'bg-pink-100 text-pink-600',
};

export function OutlinePreview({ outline, selectedIndex, className }: OutlinePreviewProps) {
  if (outline.length === 0) {
    return (
      <div
        className={clsx(
          'flex items-center justify-center bg-gray-50 rounded-3xl shadow-soft-md aspect-video',
          className
        )}
      >
        <div className="text-center p-8">
          <div className="w-28 h-20 mx-auto mb-5 bg-white rounded-2xl shadow-soft-sm flex items-center justify-center">
            <span className="text-5xl text-gray-300">?</span>
          </div>
          <p className="text-gray-500 font-medium">大纲生成后将在此预览</p>
        </div>
      </div>
    );
  }

  const item =
    selectedIndex !== null && selectedIndex >= 0 && selectedIndex < outline.length
      ? outline[selectedIndex]
      : outline[0];

  return (
    <div
      className={clsx(
        'bg-white rounded-3xl shadow-soft-md p-6 aspect-video flex flex-col',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span
          className={clsx(
            'px-2 py-0.5 text-xs font-semibold rounded-full',
            pageTypeBadgeColors[item.page_type]
          )}
        >
          {pageTypeLabels[item.page_type]}
        </span>
        <span className="text-xs text-gray-400">第 {item.page_id} 页</span>
      </div>

      {/* Title */}
      <h2 className="text-xl font-bold text-gray-800 mb-2 line-clamp-2">
        {item.page_title || '未命名'}
      </h2>

      {/* Subtitle */}
      {item.subtitle && (
        <p className="text-sm text-gray-500 mb-4 line-clamp-2">{item.subtitle}</p>
      )}

      {/* Purpose */}
      {item.page_purpose && (
        <p className="text-sm text-gray-400 italic mb-4">{item.page_purpose}</p>
      )}

      {/* Key points */}
      {item.key_points && item.key_points.length > 0 && (
        <div className="mt-2 flex-1 overflow-hidden space-y-2">
          {item.key_points.slice(0, 6).map((point, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-semibold">
                {i + 1}
              </span>
              <span className="text-sm text-gray-600 leading-relaxed">{point}</span>
            </div>
          ))}
          {item.key_points.length > 6 && (
            <p className="text-xs text-gray-400 pl-7">+{item.key_points.length - 6} 更多要点</p>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400 flex items-center justify-between">
        <span>建议布局：{item.suggest_layout || '单栏'}</span>
        <span>
          {selectedIndex !== null ? selectedIndex + 1 : 1} / {outline.length}
        </span>
      </div>
    </div>
  );
}
