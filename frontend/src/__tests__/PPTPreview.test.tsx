// PPTPreview and ParallelGenerationProgress component tests
// Covers placeholder rendering, status badges, preview image fallback, and progress bar.

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  PPTPreview,
  SlideThumbnail,
  ParallelGenerationProgress,
} from '@/components/preview/PPTPreview';
import type { PageData } from '@/types';

// ================== Sample fixtures ==================
const makePage = (overrides: Partial<PageData> = {}): PageData => ({
  page_id: 'page-01',
  page_type: 'cover',
  content: {
    title: '编译原理',
    subtitle: '一份课件',
    key_points: ['词法分析', '语法分析', '语义分析'],
    bullet_points: [],
    speaker_notes: '',
  },
  layout: { layout_type: 'cover' },
  iteration: 1,
  max_iterations: 3,
  status: 'completed',
  ...overrides,
});

// ================== PPTPreview: empty state ==================
describe('PPTPreview - empty state', () => {
  it('shows placeholder when page is null', () => {
    render(<PPTPreview page={null} />);
    expect(screen.getByText('选择或生成页面后在此预览')).toBeInTheDocument();
    expect(screen.getByText('?')).toBeInTheDocument();
  });

  it('hides preview image when page is null', () => {
    render(<PPTPreview page={null} />);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});

// ================== PPTPreview: content rendering ==================
describe('PPTPreview - content rendering', () => {
  it('renders title from content', () => {
    const page = makePage();
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('编译原理')).toBeInTheDocument();
  });

  it('renders subtitle when present', () => {
    const page = makePage();
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('一份课件')).toBeInTheDocument();
  });

  it('falls back to "无标题" when title is empty', () => {
    const page = makePage({
      content: { title: '', subtitle: '', key_points: [], bullet_points: [], speaker_notes: '' },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('无标题')).toBeInTheDocument();
  });
});

// ================== PPTPreview: status badges ==================
describe('PPTPreview - status badges', () => {
  it('shows page_type badge', () => {
    const page = makePage({ page_type: 'toc' });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('toc')).toBeInTheDocument();
  });

  it('shows iteration badge when iteration > 1', () => {
    const page = makePage({ iteration: 3 });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('迭代 3')).toBeInTheDocument();
  });

  it('hides iteration badge when iteration is 1', () => {
    const page = makePage({ iteration: 1 });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.queryByText(/迭代/)).not.toBeInTheDocument();
  });

  it('shows review score badge with green color for high scores', () => {
    const page = makePage({
      review: {
        status: 'approved',
        score: 90,
        issues: [],
        suggestions: [],
      },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    const badge = screen.getByText('90分');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('bg-green-100');
  });

  it('shows review score badge with yellow color for medium scores', () => {
    const page = makePage({
      review: { status: 'needs_revision', score: 75, issues: [], suggestions: [] },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    const badge = screen.getByText('75分');
    expect(badge.className).toContain('bg-yellow-100');
  });

  it('shows review score badge with red color for low scores', () => {
    const page = makePage({
      review: { status: 'blocked', score: 50, issues: [], suggestions: [] },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    const badge = screen.getByText('50分');
    expect(badge.className).toContain('bg-red-100');
  });

  it('shows page_id as secondary text', () => {
    const page = makePage({ page_id: 'page-05' });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('page-05')).toBeInTheDocument();
  });
});

// ================== PPTPreview: layout and points ==================
describe('PPTPreview - layout and points', () => {
  it('renders key_points when no preview image', () => {
    const page = makePage({
      content: {
        title: 'Test',
        subtitle: '',
        key_points: ['Point 1', 'Point 2'],
        bullet_points: [],
        speaker_notes: '',
      },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('Point 1')).toBeInTheDocument();
    expect(screen.getByText('Point 2')).toBeInTheDocument();
  });

  it('falls back to bullet_points when key_points is empty', () => {
    const page = makePage({
      content: {
        title: 'Test',
        subtitle: '',
        key_points: [],
        bullet_points: ['Bullet A', 'Bullet B'],
        speaker_notes: '',
      },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('Bullet A')).toBeInTheDocument();
    expect(screen.getByText('Bullet B')).toBeInTheDocument();
  });

  it('shows "等待内容生成..." when no points and no preview', () => {
    const page = makePage({
      content: { title: 'Test', subtitle: '', key_points: [], bullet_points: [], speaker_notes: '' },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('等待内容生成...')).toBeInTheDocument();
  });

  it('hides points grid when preview image is present', () => {
    const page = makePage({
      preview: {
        image_path: 'storage/preview.png',
        width: 1280,
        height: 720,
        rendered_at: new Date().toISOString(),
      },
      content: {
        title: 'Test',
        subtitle: '',
        key_points: ['Point 1'],
        bullet_points: [],
        speaker_notes: '',
      },
    });
    render(<PPTPreview page={page} />);
    // The text "Point 1" is hidden behind the image overlay
    const points = screen.queryByText('Point 1');
    expect(points).toBeNull();
  });
});

// ================== PPTPreview: preview image ==================
describe('PPTPreview - preview image', () => {
  it('shows preview image when image_path is set', () => {
    const page = makePage({
      preview: {
        image_path: 'storage/preview.png',
        width: 1280,
        height: 720,
        rendered_at: new Date().toISOString(),
      },
    });
    render(<PPTPreview page={page} />);
    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('src', '/storage/preview.png');
  });

  it('converts Windows path separators to URL-friendly form', () => {
    const page = makePage({
      preview: {
        image_path: 'storage\\preview.png',
        width: 1280,
        height: 720,
        rendered_at: new Date().toISOString(),
      },
    });
    render(<PPTPreview page={page} />);
    const img = screen.getByRole('img');
    expect(img.getAttribute('src')).toBe('/storage/preview.png');
  });

  it('does not show preview image when showPreviewImage is false', () => {
    const page = makePage({
      preview: {
        image_path: 'storage/preview.png',
        width: 1280,
        height: 720,
        rendered_at: new Date().toISOString(),
      },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});

// ================== PPTPreview: review issues ==================
describe('PPTPreview - review issues', () => {
  it('renders review issue descriptions', () => {
    const page = makePage({
      review: {
        status: 'needs_revision',
        score: 60,
        issues: [
          {
            issue_id: 'i-1',
            category: 'layout',
            severity: 'high',
            target: 'title',
            description: '对齐问题：标题与正文未对齐到基线',
            owner: 'layout',
          },
        ],
        suggestions: [],
      },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    // Description is shorter than 20 chars, so it is shown in full
    expect(screen.getByText('对齐问题：标题与正文未对齐到基线')).toBeInTheDocument();
  });

  it('truncates review issue descriptions longer than 20 chars', () => {
    const longDescription = 'A'.repeat(30);
    const page = makePage({
      review: {
        status: 'needs_revision',
        score: 60,
        issues: [
          {
            issue_id: 'i-1',
            category: 'layout',
            severity: 'high',
            target: 'title',
            description: longDescription,
            owner: 'layout',
          },
        ],
        suggestions: [],
      },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('A'.repeat(20))).toBeInTheDocument();
    // Should not contain the full 30-char string
    expect(screen.queryByText('A'.repeat(30))).not.toBeInTheDocument();
  });

  it('shows high severity issue in red', () => {
    const page = makePage({
      review: {
        status: 'needs_revision',
        score: 60,
        issues: [
          {
            issue_id: 'i-1',
            category: 'layout',
            severity: 'high',
            target: 'title',
            description: 'x',
            owner: 'layout',
          },
        ],
        suggestions: [],
      },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    const issue = screen.getByText('x');
    expect(issue.className).toContain('bg-red-100');
  });

  it('shows "+N more" when there are more than 3 issues', () => {
    const issues = Array.from({ length: 5 }, (_, i) => ({
      issue_id: `i-${i}`,
      category: 'layout',
      severity: 'low' as const,
      target: 'title',
      description: `issue ${i}`,
      owner: 'layout' as const,
    }));
    const page = makePage({
      review: { status: 'needs_revision', score: 60, issues, suggestions: [] },
    });
    render(<PPTPreview page={page} showPreviewImage={false} />);
    expect(screen.getByText('+2 more')).toBeInTheDocument();
  });
});

// ================== PPTPreview: layout colors ==================
describe('PPTPreview - layout colors', () => {
  it('uses master color scheme from layout.master_json when present', () => {
    const page = makePage({
      layout: {
        layout_type: 'cover',
        master_json: {
          background: { type: 'solid', rgb: [255, 255, 255] },
          logo: { enable: false },
          color_scheme: {
            primary: [30, 41, 59],
            secondary: [100, 116, 139],
            accent: [99, 102, 241],
            text: [71, 85, 105],
            light_text: [148, 163, 184],
          },
          font_scheme: { title_font: 'sans', body_font: 'sans', title_size: 28, body_size: 14 },
        },
      },
    });
    const { container } = render(<PPTPreview page={page} showPreviewImage={false} />);
    const title = screen.getByText('编译原理');
    expect(title).toBeInTheDocument();
    expect(container.firstChild).toBeInTheDocument();
  });
});

// ================== SlideThumbnail ==================
describe('SlideThumbnail', () => {
  it('renders thumbnail button with title', () => {
    const page = makePage();
    render(<SlideThumbnail page={page} />);
    expect(screen.getByRole('button')).toBeInTheDocument();
    expect(screen.getByText('编译原理')).toBeInTheDocument();
  });

  it('applies active ring when isActive is true', () => {
    const page = makePage();
    const { container } = render(<SlideThumbnail page={page} isActive={true} />);
    const button = container.querySelector('button');
    expect(button?.className).toContain('ring-indigo-500');
  });

  it('applies status border for completed pages', () => {
    const page = makePage({ status: 'completed' });
    const { container } = render(<SlideThumbnail page={page} />);
    const button = container.querySelector('button');
    expect(button?.className).toContain('border-green-300');
  });

  it('applies status border for failed pages', () => {
    const page = makePage({ status: 'failed' });
    const { container } = render(<SlideThumbnail page={page} />);
    const button = container.querySelector('button');
    expect(button?.className).toContain('border-red-300');
  });

  it('shows checkmark for completed pages', () => {
    const page = makePage({ status: 'completed' });
    render(<SlideThumbnail page={page} />);
    expect(screen.getByText('✓')).toBeInTheDocument();
  });

  it('shows X mark for failed pages', () => {
    const page = makePage({ status: 'failed' });
    render(<SlideThumbnail page={page} />);
    expect(screen.getByText('✗')).toBeInTheDocument();
  });

  it('shows review score badge for reviewed pages', () => {
    const page = makePage({
      review: { status: 'approved', score: 88, issues: [], suggestions: [] },
    });
    render(<SlideThumbnail page={page} />);
    expect(screen.getByText('88')).toBeInTheDocument();
  });
});

// ================== ParallelGenerationProgress ==================
describe('ParallelGenerationProgress', () => {
  it('renders the title and completion counter', () => {
    render(
      <ParallelGenerationProgress
        totalPages={4}
        completedPages={2}
        failedPages={0}
        pagesStatus={{
          'page-01': 'completed',
          'page-02': 'completed',
          'page-03': 'writing',
          'page-04': 'pending',
        }}
      />
    );
    expect(screen.getByText('并行生成进度')).toBeInTheDocument();
    expect(screen.getByText('2/4 完成')).toBeInTheDocument();
  });

  it('calculates progress percentage correctly', () => {
    const { container } = render(
      <ParallelGenerationProgress
        totalPages={4}
        completedPages={3}
        failedPages={0}
        pagesStatus={{}}
      />
    );
    const bar = container.querySelector('div[style*="width"]');
    expect(bar).toBeInTheDocument();
    expect(bar?.getAttribute('style')).toContain('width: 75%');
  });

  it('shows 0% when no pages completed', () => {
    const { container } = render(
      <ParallelGenerationProgress
        totalPages={4}
        completedPages={0}
        failedPages={0}
        pagesStatus={{}}
      />
    );
    const bar = container.querySelector('div[style*="width"]');
    expect(bar?.getAttribute('style')).toContain('width: 0%');
  });

  it('handles 0 total pages without crashing', () => {
    render(
      <ParallelGenerationProgress
        totalPages={0}
        completedPages={0}
        failedPages={0}
        pagesStatus={{}}
      />
    );
    expect(screen.getByText('0/0 完成')).toBeInTheDocument();
  });

  it('shows failed page count when there are failures', () => {
    render(
      <ParallelGenerationProgress
        totalPages={4}
        completedPages={2}
        failedPages={1}
        pagesStatus={{}}
      />
    );
    expect(screen.getByText('1 个页面生成失败')).toBeInTheDocument();
  });

  it('does not show failed indicator when failedPages is 0', () => {
    render(
      <ParallelGenerationProgress
        totalPages={4}
        completedPages={4}
        failedPages={0}
        pagesStatus={{}}
      />
    );
    expect(screen.queryByText(/页面生成失败/)).not.toBeInTheDocument();
  });

  it('renders page status cells for each page', () => {
    render(
      <ParallelGenerationProgress
        totalPages={3}
        completedPages={1}
        failedPages={0}
        pagesStatus={{
          'page-01': 'completed',
          'page-02': 'writing',
          'page-03': 'pending',
        }}
      />
    );
    expect(screen.getByText('01')).toBeInTheDocument();
    expect(screen.getByText('02')).toBeInTheDocument();
    expect(screen.getByText('03')).toBeInTheDocument();
  });

  it('strips "page-" prefix from page labels', () => {
    render(
      <ParallelGenerationProgress
        totalPages={1}
        completedPages={0}
        failedPages={0}
        pagesStatus={{ 'page-07': 'pending' }}
      />
    );
    expect(screen.getByText('07')).toBeInTheDocument();
  });

  it('includes failed pages in progress calculation', () => {
    const { container } = render(
      <ParallelGenerationProgress
        totalPages={4}
        completedPages={2}
        failedPages={2}
        pagesStatus={{}}
      />
    );
    const bar = container.querySelector('div[style*="width"]');
    expect(bar?.getAttribute('style')).toContain('width: 100%');
  });
});
