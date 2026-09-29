// Main App component - Soft UI Style

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Play,
  RefreshCw,
  Download,
  CheckCircle,
  Loader2,
  FileText,
  LayoutGrid,
} from 'lucide-react';
import { Button, Card, CardHeader, CardTitle, CardDescription, Progress, Badge } from '@/components/ui';
import { NavBar, StepIndicator } from '@/components/layout';
import { InputPanel } from '@/components/input';
import { PPTPreview, PageCard } from '@/components/preview';
import { OutlinePreview } from '@/components/preview/OutlinePreview';
import { useProjectStore, useExamples } from '@/stores/projectStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import toast from 'react-hot-toast';
import type { PPTProjectSpec } from '@/types';

type AppStep = 'input' | 'plan' | 'generate' | 'export';

function App() {
  const {
    project,
    isLoading,
    error,
    lastDownloadUrl,
    createProject,
    parseInput,
    planOutline,
    generateParallel,
    renderPPTX,
    setError,
    clearProject,
  } = useProjectStore();

  const [currentStep, setCurrentStep] = useState<AppStep>('input');
  const [selectedPageIndex, setSelectedPageIndex] = useState<number | null>(null);
  const [isAutoDownloading, setIsAutoDownloading] = useState(false);

  // Connect to WebSocket for real-time updates
  useWebSocket(project?.id || null);

  // Update step based on project status
  useEffect(() => {
    if (!project) {
      setCurrentStep('input');
      return;
    }

    switch (project.status) {
      case 'idle':
      case 'parsing':
        setCurrentStep('input');
        break;
      case 'planning':
      case 'planned':
        setCurrentStep('plan');
        break;
      case 'generating':
      case 'reviewing':
        setCurrentStep('generate');
        break;
      case 'rendering':
      case 'completed':
        setCurrentStep('export');
        break;
      case 'failed':
        // Stay on current step
        break;
    }
  }, [project?.status]);

  // As each page arrives, show the newest page without requiring a click.
  useEffect(() => {
    const pages = project?.pages || [];
    const newest = pages.reduce((last, page, index) => page ? index : last, -1);
    if (newest >= 0) setSelectedPageIndex(newest);
  }, [project?.pages]);

  // Auto-trigger generation as soon as the outline is ready. The plan step
  // has no manual "Start" button any more, so this kicks off the writer /
  // designer / critic loop the moment status flips to `planned`.
  useEffect(() => {
    if (project?.status === 'planned' && !isLoading) {
      setCurrentStep('generate');
      generateParallel();
    }
  }, [project?.status, isLoading, generateParallel]);

  // Handle new project creation
  const handleCreateProject = useCallback(async (input: string, spec: PPTProjectSpec) => {
    try {
      setError(null);
      hasAutoDownloadedRef.current = false;
      await createProject(spec, input);

      // Auto-parse and plan via WebSocket commands
      parseInput();
      planOutline();

      setCurrentStep('plan');
    } catch (err) {
      toast.error((err as Error).message);
    }
  }, [createProject, parseInput, planOutline, setError]);

  // Handle start generation
  const handleStartGeneration = useCallback(() => {
    if (!project) return;
    if (project.status === 'idle' || project.status === 'parsing' || project.status === 'planning') {
      setError('请先生成大纲');
      return;
    }
    setError(null);
    setCurrentStep('generate');
    generateParallel();
  }, [project, generateParallel, setError]);

  // Handle export
  const handleExport = useCallback(async () => {
    if (!project) return;
    setError(null);
    setIsAutoDownloading(true);
    try {
      // Ask the backend to (re)render and then fetch the file as a Blob so
      // the browser actually triggers a download dialog instead of just
      // navigating to the URL (which often fails for application/octet-stream
      // responses and never auto-downloads on Chrome/Edge).
      await renderPPTX();
      // Wait briefly for the `completed` event to populate `lastDownloadUrl`.
      let url = lastDownloadUrl;
      for (let i = 0; i < 40 && !url; i += 1) {
        await new Promise((r) => setTimeout(r, 250));
        url = useProjectStore.getState().lastDownloadUrl;
      }
      if (!url) {
        toast.error('生成完成但未收到下载链接，请重试');
        return;
      }
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`下载失败: HTTP ${resp.status}`);
      const blob = await resp.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = `${project.spec?.topic || 'PPT演示'}.pptx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      toast.success('PPTX 已开始下载');
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(`导出失败：${msg}`);
    } finally {
      setIsAutoDownloading(false);
    }
  }, [project, renderPPTX, setError, lastDownloadUrl]);

  // Auto-trigger download the moment the backend reports generation complete
  // (the user no longer has to click "下载PPTX" once generation finishes).
  const hasAutoDownloadedRef = useRef(false);
  useEffect(() => {
    if (
      project?.status === 'completed' &&
      lastDownloadUrl &&
      !hasAutoDownloadedRef.current &&
      !isAutoDownloading
    ) {
      hasAutoDownloadedRef.current = true;
      void handleExport();
    }
  }, [project?.status, lastDownloadUrl, isAutoDownloading, handleExport]);

  // Handle example selection
  const handleSelectExample = useCallback(async (example: ReturnType<typeof useExamples>[number]) => {
    try {
      hasAutoDownloadedRef.current = false;
      await createProject(example.spec, '');
      planOutline();
      setCurrentStep('plan');
      toast.success(`已加载示例：${example.title}`);
    } catch (err) {
      toast.error((err as Error).message);
    }
  }, [createProject, planOutline]);

  // Render home screen
  if (!project) {
    return (
      <div className="min-h-screen bg-slate-50">
        <NavBar />

        <main className="max-w-6xl mx-auto px-4 md:px-6 lg:px-8 py-12 md:py-16">
          {/* Hero Section */}
          <div className="text-center mb-16">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-gray-800 mb-6 leading-tight">
              <span className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                输入需求
              </span>
              <br />
              即刻生成专业演示
            </h1>
            <p className="text-lg text-gray-500 max-w-2xl mx-auto leading-relaxed">
              基于多Agent协作系统，自动完成从大纲规划到页面生成的完整流程，
              支持迭代修改和增量更新，让你的演示文稿制作更高效。
            </p>
          </div>

          {/* Examples */}
          <div className="mb-12">
            <h2 className="text-xl font-semibold text-gray-700 mb-6">
              快速开始
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {useExamples().map((example, index) => (
                <Card
                  key={index}
                  hover
                  className="cursor-pointer group"
                  onClick={() => handleSelectExample(example)}
                >
                  <CardHeader>
                    <CardTitle className="text-base group-hover:text-indigo-600 transition-colors">
                      {example.title}
                    </CardTitle>
                    <CardDescription>{example.description}</CardDescription>
                  </CardHeader>
                  <div className="flex flex-wrap gap-2 mt-2">
                    <Badge variant="primary">{example.spec.page_count}页</Badge>
                    <Badge variant="secondary">{example.spec.style}</Badge>
                  </div>
                </Card>
              ))}
            </div>
          </div>

          {/* Main Input */}
          <InputPanel onSubmit={handleCreateProject} isLoading={isLoading} />
        </main>
      </div>
    );
  }

  // Render workspace
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <NavBar
        projectName={project.spec.topic}
        onHome={() => {
          hasAutoDownloadedRef.current = false;
          clearProject();
        }}
      />

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 md:px-6 lg:px-8 py-8">
        {/* Progress */}
        <StepIndicator
          currentStep={currentStep}
          progress={project.progress ?? 0}
        />

        {/* Status bar */}
        {project.status !== 'idle' && project.status !== 'completed' && project.status !== 'planned' && (
          <Card className="mb-8">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-indigo-100 flex items-center justify-center">
                  <Loader2 className="w-6 h-6 text-indigo-600 animate-spin" />
                </div>
                <div>
                  <p className="text-base font-medium text-gray-700">
                    {project.current_step || '处理中...'}
                  </p>
                  <p className="text-sm text-gray-400">
                    {project.status === 'parsing' && '正在解析输入内容'}
                    {project.status === 'planning' && '正在生成PPT大纲'}
                    {project.status === 'generating' && '正在逐页生成内容'}
                    {project.status === 'reviewing' && '正在审核页面'}
                    {project.status === 'rendering' && '正在渲染PPT文件'}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <span className="text-3xl font-bold text-indigo-600">{project.progress ?? 0}%</span>
              </div>
            </div>
            <Progress value={project.progress ?? 0} className="mt-5" />
          </Card>
        )}

        {/* Error display */}
        {error && (
          <Card className="mb-8 bg-red-50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-red-100 flex items-center justify-center">
                <span className="text-red-500 text-lg">!</span>
              </div>
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          </Card>
        )}

        {/* Main content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left panel - Pages list */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-2xl bg-indigo-100 flex items-center justify-center">
                      <FileText className="w-5 h-5 text-indigo-600" />
                    </div>
                    页面列表
                  </CardTitle>
                  <CardDescription>
                    共 {project.pages?.length || project.outline?.length || 0} 页
                  </CardDescription>
                </div>
              </CardHeader>
            </Card>

            {/* Outline view (before generation) */}
            {project.outline && project.outline.length > 0 && (
              <div className="space-y-4">
                {project.outline.map((item, index) => (
                  project.pages?.[index] ? (
                    <PageCard key={index} page={project.pages[index]!} isSelected={selectedPageIndex === index} onClick={() => setSelectedPageIndex(index)} />
                  ) : (
                  <Card key={index} className="opacity-60">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-2xl bg-gray-100 text-gray-500 flex items-center justify-center font-bold text-lg">{item.page_id}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-gray-800 truncate">{item.page_title}</h4>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            item.page_type === 'cover' ? 'bg-purple-100 text-purple-600' :
                            item.page_type === 'toc' ? 'bg-blue-100 text-blue-600' :
                            item.page_type === 'chart' ? 'bg-green-100 text-green-600' :
                            item.page_type === 'conclusion' ? 'bg-amber-100 text-amber-600' :
                            item.page_type === 'thankyou' ? 'bg-pink-100 text-pink-600' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            {item.page_type === 'cover' ? '封面' :
                             item.page_type === 'toc' ? '目录' :
                             item.page_type === 'chart' ? '图表' :
                             item.page_type === 'conclusion' ? '总结' :
                             item.page_type === 'thankyou' ? '致谢' :
                             item.page_type === 'content' ? '内容' : item.page_type}
                          </span>
                        </div>
                        {item.subtitle && (
                          <p className="text-sm text-gray-500 mb-2">{item.subtitle}</p>
                        )}
                        {item.key_points && item.key_points.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {item.key_points.slice(0, 3).map((point, i) => (
                              <span key={i} className="inline-flex items-center px-2 py-0.5 rounded bg-gray-50 text-gray-600 text-xs border border-gray-100">
                                {point}
                              </span>
                            ))}
                            {item.key_points.length > 3 && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded bg-gray-50 text-gray-400 text-xs">
                                +{item.key_points.length - 3}
                              </span>
                            )}
                          </div>
                        )}
                        <p className="text-xs text-gray-400 mt-2 flex items-center gap-1">
                          <span>布局:</span>
                          <span className="text-gray-500">{item.suggest_layout || '单栏布局'}</span>
                        </p>
                      </div>
                    </div>
                  </Card>
                  )
                ))}
              </div>
            )}

            {/* Empty state */}
            {!project.outline?.length && !project.pages?.length && (
              <Card className="text-center py-16">
                <div className="w-20 h-20 rounded-3xl bg-gray-100 flex items-center justify-center mx-auto mb-4">
                  <LayoutGrid className="w-10 h-10 text-gray-300" />
                </div>
                <p className="text-gray-500 font-medium">等待生成大纲...</p>
              </Card>
            )}
          </div>

          {/* Right panel - Preview/Editor */}
          <div className="space-y-6">
            {/* Preview */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-indigo-100 flex items-center justify-center">
                    <LayoutGrid className="w-5 h-5 text-indigo-600" />
                  </div>
                  预览
                </CardTitle>
              </CardHeader>
              <div className="space-y-6">
                {currentStep === 'plan' ? (
                  <OutlinePreview
                    outline={project.outline ?? []}
                    selectedIndex={selectedPageIndex}
                    className="w-full"
                  />
                ) : (
                  <>
                    {(project.pages || []).filter(Boolean).map((page, index) => (
                      <div key={page!.page_id || index}>
                        <div className="text-xs text-gray-400 mb-2">第 {page!.page_id} 页</div>
                        <PPTPreview page={page!} className="w-full" />
                      </div>
                    ))}
                    {!(project.pages || []).some(Boolean) && (
                      <PPTPreview page={null} className="w-full" />
                    )}
                  </>
                )}
              </div>
            </Card>

            {/* Actions */}
            {project.status === 'completed' && (
              <Card>
                <CardHeader>
                  <CardTitle>导出文件</CardTitle>
                </CardHeader>
                <div className="flex gap-4">
                  <Button
                    onClick={handleExport}
                    isLoading={isLoading}
                    className="flex-1"
                  >
                    <Download className="w-5 h-5 mr-2" />
                    下载PPTX
                  </Button>
                  {lastDownloadUrl && (
                    <Button
                      variant="outline"
                      onClick={() => window.open(lastDownloadUrl, '_blank')}
                    >
                      预览新窗口
                    </Button>
                  )}
                </div>
                {lastDownloadUrl && (
                  <div className="flex items-center gap-2 mt-4 text-emerald-600">
                    <CheckCircle className="w-5 h-5" />
                    <span className="text-sm font-medium">文件已准备好下载</span>
                  </div>
                )}
              </Card>
            )}

            {/* Regenerate */}
            {project.status === 'completed' && (
              <Button
                variant="secondary"
                onClick={handleStartGeneration}
                isLoading={isLoading}
                className="w-full"
              >
                <RefreshCw className="w-5 h-5 mr-2" />
                重新生成
              </Button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
