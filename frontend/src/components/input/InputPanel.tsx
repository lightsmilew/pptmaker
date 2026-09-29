// Requirement input panel - Soft UI Style

import { useState, useRef } from 'react';
import { Send, Sparkles, FileUp, X, FileText } from 'lucide-react';
import { Button, Textarea, Input, Select, Card, CardHeader, CardTitle, CardDescription } from '@/components/ui';
import type { PPTProjectSpec } from '@/types';
import { api } from '@/api/client';

interface InputPanelProps {
  onSubmit: (input: string, spec: PPTProjectSpec) => void;
  isLoading?: boolean;
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

export function InputPanel({ onSubmit, isLoading }: InputPanelProps) {
  const [input, setInput] = useState('');
  const [spec, setSpec] = useState<PPTProjectSpec>({
    topic: '',
    page_count: 8,
    style: '商务简约',
    audience: '通用',
    needs_cover: true,
    needs_toc: true,
    needs_summary: true,
    needs_chart: false,
  });
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
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
    onSubmit(input, spec);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleSubmit();
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      {/* Main Input Card */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-100 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-indigo-600" />
            </div>
            描述你的PPT需求
          </CardTitle>
          <CardDescription>
            输入自然语言描述，系统将自动解析并生成PPT。也可以粘贴Markdown大纲或上传文档。
          </CardDescription>
        </CardHeader>

        <div className="space-y-6">
          {/* Main input */}
          <div className="relative">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="例如：做一份10页的人工智能技术汇报PPT，面向本科生，风格简约学术，需要包含图表..."
              className="min-h-[160px] text-base"
            />
            <div className="absolute bottom-4 right-4 flex items-center gap-2">
              <span className="text-xs text-gray-400 bg-gray-100 px-2.5 py-1 rounded-full">Ctrl + Enter 发送</span>
            </div>
          </div>

          {/* File upload area */}
          <div
            className={`border-2 border-dashed rounded-3xl p-8 text-center transition-all duration-200 cursor-pointer group ${
              dragActive
                ? 'border-indigo-400 bg-indigo-50'
                : 'border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/30'
            }`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.docx,.doc,.md,.txt,.markdown"
              multiple
              onChange={(e) => handleFileUpload(e.target.files)}
            />
            <div className="w-14 h-14 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-4 group-hover:bg-indigo-100 transition-colors duration-200">
              {isUploading ? (
                <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              ) : (
                <FileUp className="w-6 h-6 text-gray-400 group-hover:text-indigo-500 transition-colors duration-200" />
              )}
            </div>
            <p className="text-sm text-gray-600 font-medium">
              {isUploading ? '正在上传和解析...' : '拖拽上传或点击上传文档'}
            </p>
            <p className="text-xs text-gray-400 mt-1">支持 PDF、Word、Markdown、TXT 格式</p>
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
                    <FileText className="w-5 h-5 text-indigo-500" />
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
                    className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4 text-gray-400" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Submit button */}
          <Button
            onClick={handleSubmit}
            disabled={!input.trim() || isLoading}
            isLoading={isLoading}
            className="w-full"
            size="xl"
          >
            <Send className="w-5 h-5 mr-2" />
            开始生成PPT大纲
          </Button>
        </div>
      </Card>

      {/* Configuration Panel */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">基本配置</CardTitle>
          </CardHeader>
          <div className="space-y-5">
            <div>
              <label className="text-sm font-medium text-gray-600 mb-2 block">页数</label>
              <Input
                type="number"
                min={1}
                max={50}
                value={spec.page_count}
                onChange={(e) => setSpec({ ...spec, page_count: parseInt(e.target.value) || 8 })}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-600 mb-2 block">风格</label>
              <Select
                options={styleOptions}
                value={spec.style}
                onChange={(e) => setSpec({ ...spec, style: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-600 mb-2 block">目标受众</label>
              <Select
                options={audienceOptions}
                value={spec.audience}
                onChange={(e) => setSpec({ ...spec, audience: e.target.value })}
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
              <label key={item.key} className="flex items-center justify-between p-3 rounded-2xl hover:bg-gray-50 transition-colors cursor-pointer">
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
                    checked={spec[item.key as keyof PPTProjectSpec] as boolean}
                    onChange={(e) =>
                      setSpec({ ...spec, [item.key]: e.target.checked })
                    }
                    className="sr-only peer"
                  />
                  <div className="w-12 h-7 bg-gray-200 rounded-full peer-checked:bg-indigo-500 transition-colors duration-200"></div>
                  <div className="absolute left-1 top-1 w-5 h-5 bg-white rounded-full shadow-soft-sm transition-transform duration-200 peer-checked:translate-x-5"></div>
                </div>
              </label>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
