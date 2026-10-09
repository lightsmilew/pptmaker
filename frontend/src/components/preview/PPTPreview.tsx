// PPT Preview component - Updated for new architecture with preview images

import { clsx } from 'clsx';
import type { PageData, PageStatus } from '@/types';
import { useState, useEffect } from 'react';

interface PPTPreviewProps {
  page: PageData | null;
  className?: string;
  showPreviewImage?: boolean;
}

const statusColors: Record<PageStatus, string> = {
  pending: 'bg-gray-100 text-gray-600',
  writing: 'bg-blue-100 text-blue-600',
  designing: 'bg-[#edf1e8] text-[#52644d]',
  rendering: 'bg-yellow-100 text-yellow-600',
  reviewing: 'bg-orange-100 text-orange-600',
  revising: 'bg-orange-100 text-orange-600',
  completed: 'bg-green-100 text-green-600',
  failed: 'bg-red-100 text-red-600',
};

export function PPTPreview({ page, className, showPreviewImage = true }: PPTPreviewProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState(false);

  // Try to load preview image
  useEffect(() => {
    setImageFailed(false);
    if (page?.preview?.image_path && showPreviewImage) {
      const previewPath = page.preview.image_path;
      const normalized = previewPath.replace(/\\/g, '/');
      const marker = normalized.lastIndexOf('/previews/');
      const url = marker >= 0 ? '/storage' + normalized.slice(marker) : normalized.replace(/^\.?\/?storage\//, '/storage/');
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }
  }, [page?.preview?.image_path, showPreviewImage]);

  if (!page) {
    return (
      <div className={clsx('flex items-center justify-center bg-gray-50 rounded-lg border border-[#e1e5dc]', className)}>
        <div className="text-center p-8">
          <div className="w-28 h-20 mx-auto mb-5 bg-white rounded-md border border-[#e1e5dc] flex items-center justify-center">
            <span className="text-5xl text-gray-300">?</span>
          </div>
          <p className="text-gray-500 font-medium">选择或生成页面后在此预览</p>
        </div>
      </div>
    );
  }

  const title = page.content?.title || '无标题';
  const subtitle = page.content?.subtitle || '';
  const keyPoints: string[] = page.content?.key_points ?? [];
  const bulletPoints: string[] = page.content?.bullet_points ?? [];
  const points = keyPoints.length > 0 ? keyPoints : bulletPoints;

  // This is a readable content excerpt, never a second slide-layout engine.
  // Slide geometry, colors, preview and export are produced by the backend.
  const background = 'var(--folio-paper)';
  const primary = 'var(--folio-green)';
  const textColor = 'var(--folio-ink)';

  return (
    <div
      className={clsx(
        'bg-white rounded-lg border border-[#e1e5dc] overflow-hidden',
        'aspect-video relative',
        className
      )}
    >
      {/* Preview image layer */}
      {previewUrl && (
        <img
          src={previewUrl}
          alt={`${page.page_id} preview`}
          className="absolute inset-0 w-full h-full object-cover"
          onError={() => { setPreviewUrl(null); setImageFailed(true); }}
        />
      )}

      {/* Content overlay (when no preview image or as fallback) */}
      <div
        className={clsx(
          'absolute inset-0 flex flex-col p-6',
          previewUrl ? 'hidden' : ''
        )}
        style={!previewUrl ? { backgroundColor: background } : {}}
      >
        <p className="mb-2 text-xs text-[#74816f]" role={imageFailed ? 'alert' : undefined}>{imageFailed ? '预览暂时无法加载，以下为正文摘录。' : '正文摘录 · 幻灯片预览就绪后显示'}</p>
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <span className={clsx(
            'px-2 py-0.5 text-xs font-semibold rounded-full',
            previewUrl ? 'bg-white/80 text-gray-700' : statusColors[page.status] || 'bg-gray-100 text-gray-600'
          )}>
            {page.page_type}
          </span>
          <div className="flex items-center gap-2">
            {page.iteration && page.iteration > 1 && (
              <span className="text-xs bg-[#edf1e8] text-[#52644d] px-2 py-0.5 rounded-full">
                迭代 {page.iteration}
              </span>
            )}
            {page.review?.score != null && (
              <span className={clsx(
                'text-xs font-semibold px-2 py-0.5 rounded-full',
                page.review.score >= 85 ? 'bg-green-100 text-green-700' :
                page.review.score >= 70 ? 'bg-yellow-100 text-yellow-700' :
                'bg-red-100 text-red-700'
              )}>
                {page.review.method === 'local_geometry' ? '排版检查' : page.review.method === 'vision' ? '视觉复核' : '检查结果'} {page.review.score}
              </span>
            )}
            <span className="text-xs text-gray-400">{page.page_id}</span>
          </div>
        </div>

        {/* Title */}
        <h2
          className={clsx(
            'font-bold mb-2',
            page.page_type === 'cover' ? 'text-2xl' : 'text-xl',
            previewUrl ? 'text-white' : ''
          )}
          style={!previewUrl ? { color: primary } : {}}
        >
          {title}
        </h2>

        {/* Subtitle */}
        {subtitle && (
          <p
            className={clsx('text-sm mb-4', previewUrl ? 'text-white/80' : 'text-gray-500')}
            style={!previewUrl ? { color: textColor } : {}}
          >
            {subtitle}
          </p>
        )}

        {/* Content */}
        {!previewUrl && points.length > 0 && (
          <div className="flex-1 overflow-auto">
              <ul className="space-y-2">
                {points.map((point: string, index: number) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className={clsx(
                      'flex-shrink-0 w-5 h-5 rounded-lg flex items-center justify-center text-xs font-semibold',
                      previewUrl ? 'bg-white/80 text-gray-700' : 'bg-[#edf1e8] text-[#52644d]'
                    )}>
                      {index + 1}
                    </span>
                    <span style={{ color: textColor }} className="text-sm leading-relaxed">{point}</span>
                  </li>
                ))}
              </ul>
          </div>
        )}

        {/* Placeholder for when no content */}
        {!previewUrl && points.length === 0 && (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-gray-400 italic">等待内容生成...</p>
          </div>
        )}

        {/* Review issues indicator */}
        {page.review?.issues && page.review.issues.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {page.review.issues.slice(0, 3).map((issue, i) => (
              <span
                key={i}
                className={clsx(
                  'text-xs px-2 py-0.5 rounded-full',
                  issue.severity === 'high' || issue.severity === 'critical'
                    ? 'bg-red-100 text-red-700'
                    : issue.severity === 'medium'
                    ? 'bg-yellow-100 text-yellow-700'
                    : 'bg-gray-100 text-gray-600'
                )}
              >
                {(issue.description || '').slice(0, 20)}
              </span>
            ))}
            {page.review.issues.length > 3 && (
              <span className="text-xs text-gray-400">+{page.review.issues.length - 3} more</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Slide thumbnail
interface SlideThumbnailProps {
  page: PageData;
  isActive?: boolean;
  onClick?: () => void;
}

const statusBorderColors: Record<PageStatus, string> = {
  pending: 'border-gray-200',
  writing: 'border-blue-300',
  designing: 'border-purple-300',
  rendering: 'border-yellow-300',
  reviewing: 'border-orange-300',
  revising: 'border-orange-300',
  completed: 'border-green-300',
  failed: 'border-red-300',
};

export function SlideThumbnail({ page, isActive, onClick }: SlideThumbnailProps) {
  const title = page.content?.title || '无标题';
  const keyPoints: string[] = page.content?.key_points ?? [];

  return (
    <button
      onClick={onClick}
      className={clsx(
        'relative bg-white rounded-2xl overflow-hidden transition-all duration-200',
        'hover:shadow-soft-md hover:-translate-y-0.5 border-2',
        isActive ? 'ring-2 ring-indigo-500 shadow-soft-md' : 'shadow-soft-sm',
        statusBorderColors[page.status] || 'border-gray-200'
      )}
    >
      <div className="aspect-video p-2">
        <div className="w-full h-full bg-gray-50 rounded-xl flex flex-col p-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[7px] font-bold text-gray-700 truncate flex-1">{title}</span>
            {page.status === 'completed' && (
              <span className="text-[8px] text-green-600">✓</span>
            )}
            {page.status === 'failed' && (
              <span className="text-[8px] text-red-600">✗</span>
            )}
          </div>
          <div className="mt-auto space-y-0.5">
            {keyPoints.slice(0, 2).map((_: string, i: number) => (
              <div key={i} className="h-1 bg-gray-200 rounded-full" />
            ))}
            {!keyPoints.length && (
              <div className="h-1 bg-gray-100 rounded-full" />
            )}
          </div>
        </div>
      </div>
      {/* Review score badge */}
      {page.review?.score != null && (
        <div className={clsx(
          'absolute top-1 right-1 text-[8px] font-bold px-1 py-0.5 rounded-full',
          page.review.score >= 85 ? 'bg-green-500 text-white' :
          page.review.score >= 70 ? 'bg-yellow-500 text-white' :
          'bg-red-500 text-white'
        )}>
          {page.review.method === 'local_geometry' ? '排版检查' : page.review.method === 'vision' ? '视觉复核' : '检查结果'} {page.review.score}
        </div>
      )}
    </button>
  );
}

// Parallel generation progress component
interface ParallelProgressProps {
  totalPages: number;
  completedPages: number;
  failedPages: number;
  pagesStatus: Record<string, PageStatus>;
  className?: string;
}

const parallelStatusColors: Record<PageStatus, string> = {
  pending: 'bg-gray-200',
  writing: 'bg-blue-200',
  designing: 'bg-purple-200',
  rendering: 'bg-yellow-200',
  reviewing: 'bg-orange-200',
  revising: 'bg-orange-200',
  completed: 'bg-green-200',
  failed: 'bg-red-200',
};

export function ParallelGenerationProgress({
  totalPages,
  completedPages,
  failedPages,
  pagesStatus,
  className
}: ParallelProgressProps) {
  const progress = totalPages > 0 ? ((completedPages + failedPages) / totalPages) * 100 : 0;

  return (
    <div className={clsx('bg-white rounded-2xl p-4 shadow-soft-md', className)}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-800">并行生成进度</h3>
        <span className="text-sm text-gray-500">{completedPages}/{totalPages} 完成</span>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden mb-3">
        <div
          className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Page status grid */}
      <div className="grid grid-cols-4 gap-2">
        {Object.entries(pagesStatus).map(([pageId, status]) => {
          return (
            <div
              key={pageId}
              className={clsx(
                'aspect-square rounded-lg flex items-center justify-center text-xs font-medium transition-all',
                parallelStatusColors[status] || 'bg-gray-200'
              )}
            >
              {pageId.replace('page-', '')}
            </div>
          );
        })}
      </div>

      {/* Failed pages indicator */}
      {failedPages > 0 && (
        <div className="mt-3 text-sm text-red-600">
          {failedPages} 个页面生成失败
        </div>
      )}
    </div>
  );
}
