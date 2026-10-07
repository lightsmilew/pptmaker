// Requirement input panel - Soft UI Style

import { useState, useRef } from 'react';
import { ArrowRight, FileUp, X, FileText } from 'lucide-react';
import { Button, Textarea, Input, Select, Card, CardHeader, CardTitle, CardDescription } from '@/components/ui';
import type { PPTProjectSpec } from '@/types';
import { api } from '@/api/client';
import { useProjectStore } from '@/stores/projectStore';

interface InputPanelProps {
  onSubmit: (input: string, spec: PPTProjectSpec) => void;
  isLoading?: boolean;
  mode: 'content' | 'settings';
}

const styleOptions = [
  { value: '商务简约', label: '商务简约' },
  { value: '学术简约', label: '学术简约' },
  { value: '科技风', label: '科技风' },
  { value: '创意活泼', label: '创意活泼' },
  { value: '教育培训', label: '教育培训' },
  { value: '金融专业', label: '金融专业' },
];

const audienceOptions = [
  { value: '通用', label: '通用受众' },
  { value: '小学生', label: '小学生' },
  { value: '初中生', label: '初中生' },
  { value: '高中生', label: '高中生' },
  { value: '本科学生', label: '大学生' },
  { value: '研究生', label: '研究生' },
  { value: '企业领导', label: '企业领导' },
  { value: '客户', label: '客户' },
  { value: '投资人', label: '投资人' },
  { value: '技术人员', label: '技术人员' },
];

interface UploadedFile {
  filename: string;
  content: string;
  size: number;
}

export function InputPanel({ onSubmit, isLoading, mode }: InputPanelProps) {
  const draftSpec = useProjectStore((s) => s.draftSpec);
  const setDraftSpec = useProjectStore((s) => s.setDraftSpec);
  const input = useProjectStore((s) => s.draftInput);
  const setInput = useProjectStore((s) => s.setDraftInput);
  const uploadedFiles = useProjectStore((s) => s.draftFiles);
  const setUploadedFiles = useProjectStore((s) => s.setDraftFiles);
  const effectiveSpec = draftSpec;
  const updateSpec = setDraftSpec;
  const [isUploading, setIsUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    setIsUploading(true);
    const newFiles: UploadedFile[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        const result = await api.uploadAndParse(file);
        newFiles.push({
          filename: result.filename,
          content: result.content,
          size: file.size,
        });
        // Append file content to input
        setInput(prev => prev + (prev ? '\n\n' : '') + `【文件内容 - ${result.filename}】\n` + result.content);
      } catch (err) {
        console.error('Upload failed:', err);
        alert(`文件 ${file.name} 上传失败: ${(err as Error).message}`);
      }
    }

    setUploadedFiles(prev => [...prev, ...newFiles]);
    setIsUploading(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const removeFile = (index: number) => {
    const file = uploadedFiles[index];
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
    // Remove file content from input
    setInput(prev => prev.replace(`【文件内容 - ${file.filename}】\n${file.content}`, '').trim());
  };

  const handleSubmit = () => {
    if (!input.trim() && uploadedFiles.length === 0) return;
    onSubmit(input, effectiveSpec);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleSubmit();
    }
  };

  return (
    <div className={mode === 'content' ? 'brief-panel' : 'settings-panel'}>
      {/* Main Input Card */}
      {mode === 'content' && <Card className="brief-card">
        <div className="space-y-6">
          {/* Main input */}
          <div className="relative">
            <Textarea
              id="brief"
              aria-label="演示内容或制作要求"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="这次你想分享什么？

写下主题、关键观点和听众，或者直接粘贴已有大纲。"
              className="min-h-[180px] text-[15px] pb-12"
            />
            <div className="absolute bottom-4 right-4 flex items-center gap-2">
              <span className="text-xs text-gray-400 bg-gray-100 px-2.5 py-1 rounded-full">Ctrl + Enter</span>
            </div>
          </div>

          {/* File upload area */}
          <div
            className={`brief-upload ${dragActive ? 'drag-active' : ''}`}
            role="button" tabIndex={0} aria-label="上传参考文档"
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef.current?.click(); } }}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.docx,.md,.txt,.markdown"
              multiple
              onChange={(e) => handleFileUpload(e.target.files)}
            />
            <FileUp size={19} />
            <span><strong>{isUploading ? '正在上传和解析…' : '添加参考文档'}</strong><small>PDF / Word / Markdown / TXT</small></span>
            <span className="upload-plus">+</span>
          </div>

          {/* Uploaded files list */}
          {uploadedFiles.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-600">已上传文件:</p>
              {uploadedFiles.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-xl border border-gray-100"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-[#29483e]" />
                    <div>
                      <p className="text-sm font-medium text-gray-700">{file.filename}</p>
                      <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(index);
                    }}
                    aria-label={`移除 ${file.filename}`} className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4 text-gray-400" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="brief-actions">
            <div className="brief-options"><label>页数 <input aria-label="演示页数" type="number" min={1} max={50} value={effectiveSpec.page_count} onChange={e => updateSpec({ page_count: Math.min(50, Math.max(1, Math.round(Number(e.target.value)) || 8)) })} /></label><span>{effectiveSpec.style}</span></div>
            <Button onClick={handleSubmit} disabled={!input.trim() || isLoading || isUploading} isLoading={isLoading}>创建演示 <ArrowRight size={16} /></Button>
          </div>
        </div>
      </Card>}

      {/* Configuration Panel */}
      {mode === 'settings' && <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">基本配置</CardTitle>
          </CardHeader>
          <div className="space-y-5">
            <div>
              <label className="text-sm font-medium text-gray-600 mb-2 block">页数</label>
              <Input
                aria-label="设置演示页数"
                type="number"
                min={1}
                max={50}
                value={effectiveSpec.page_count}
                onChange={(e) => updateSpec({ page_count: Math.min(50, Math.max(1, parseInt(e.target.value) || 8)) })}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-600 mb-2 block">风格</label>
              <Select
                aria-label="演示风格"
                options={styleOptions}
                value={effectiveSpec.style}
                onChange={(e) => updateSpec({ style: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-600 mb-2 block">目标受众</label>
              <Select
                aria-label="目标受众"
                options={audienceOptions}
                value={effectiveSpec.audience}
                onChange={(e) => updateSpec({ audience: e.target.value })}
              />
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">内容选项</CardTitle>
          </CardHeader>
          <div className="space-y-4">
            {[
              { key: 'needs_cover', label: '封面页', desc: '包含标题和副标题的封面', icon: '01' },
              { key: 'needs_toc', label: '目录页', desc: '展示汇报结构', icon: '02' },
              { key: 'needs_summary', label: '总结页', desc: '回顾核心要点', icon: '03' },
              { key: 'needs_chart', label: '图表页', desc: '包含数据可视化', icon: '04' },
            ].map((item) => (
              <label key={item.key} className="setting-toggle">
                <div className="flex items-center gap-3">
                  <span className="w-7 h-7 rounded-md bg-slate-100 text-slate-500 text-xs font-semibold flex items-center justify-center">{item.icon}</span>
                  <div>
                    <span className="text-sm font-medium text-gray-700">
                      {item.label}
                    </span>
                    <p className="text-xs text-gray-400">{item.desc}</p>
                  </div>
                </div>
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={effectiveSpec[item.key as keyof PPTProjectSpec] as boolean}
                    onChange={(e) => updateSpec({ [item.key]: e.target.checked } as Partial<PPTProjectSpec>)}
                    aria-label={item.label} className="sr-only peer"
                  />
                  <div className="w-10 h-6 bg-[#dde3d8] rounded-full peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-[#547459] peer-checked:bg-[#29483e] transition-colors duration-200"></div>
                  <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform duration-200 peer-checked:translate-x-4"></div>
                </div>
              </label>
            ))}
          </div>
        </Card>
      </div>}
    </div>
  );
}
