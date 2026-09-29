// Page editor component - Soft UI Style

import { useState } from 'react';
import { Save, X, Plus, Trash2 } from 'lucide-react';
import { Button, Input, Textarea, Select, Card, CardHeader, CardTitle } from '@/components/ui';
import type { PageData } from '@/types';

interface PageEditorProps {
  page: PageData;
  onSave: (data: Partial<PageData>) => void;
  onCancel: () => void;
}

const layoutOptions = [
  { value: '单栏布局', label: '单栏布局' },
  { value: '双栏布局', label: '双栏布局' },
  { value: '大图+文字', label: '大图+文字' },
  { value: '图表页', label: '图表页' },
  { value: '封面布局', label: '封面布局' },
  { value: '目录布局', label: '目录布局' },
  { value: '总结布局', label: '总结布局' },
];

export function PageEditor({ page, onSave, onCancel }: PageEditorProps) {
  const initialContent = page.content ?? {
    title: '',
    subtitle: '',
    key_points: [],
    bullet_points: [],
    speaker_notes: '',
  };

  const [title, setTitle] = useState(initialContent.title);
  const [subtitle, setSubtitle] = useState(initialContent.subtitle ?? '');
  const [layoutType, setLayoutType] = useState<string>(page.layout?.layout_type ?? '单栏布局');
  const [keyPoints, setKeyPoints] = useState<string[]>(initialContent.key_points ?? []);
  const [speakerNotes, setSpeakerNotes] = useState(initialContent.speaker_notes ?? '');
  const [isSaving, setIsSaving] = useState(false);

  const handleAddKeyPoint = () => {
    setKeyPoints([...keyPoints, '']);
  };

  const handleRemoveKeyPoint = (index: number) => {
    setKeyPoints(keyPoints.filter((_, i) => i !== index));
  };

  const handleKeyPointChange = (index: number, value: string) => {
    const updated = [...keyPoints];
    updated[index] = value;
    setKeyPoints(updated);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave({
        content: {
          ...initialContent,
          title,
          subtitle,
          key_points: keyPoints.filter((k) => k.trim()),
          bullet_points: initialContent.bullet_points ?? [],
          speaker_notes: speakerNotes,
        },
        layout: {
          ...page.layout,
          layout_type: layoutType,
        },
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Header */}
      <div className="flex items-center justify-between p-5 bg-white border-b border-gray-100">
        <h3 className="text-lg font-semibold text-gray-800">编辑第{page.page_id}页</h3>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="md" onClick={onCancel}>
            <X className="w-4 h-4 mr-1.5" />
            取消
          </Button>
          <Button size="md" onClick={handleSave} isLoading={isSaving}>
            <Save className="w-4 h-4 mr-1.5" />
            保存
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">基本信息</CardTitle>
          </CardHeader>
          <div className="space-y-5">
            <div>
              <label className="text-sm font-medium text-gray-600 mb-2 block">页面标题</label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="输入页面标题"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-600 mb-2 block">副标题</label>
              <Input
                value={subtitle}
                onChange={(e) => setSubtitle(e.target.value)}
                placeholder="输入副标题（可选）"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-600 mb-2 block">版式布局</label>
              <Select
                options={layoutOptions}
                value={layoutType}
                onChange={(e) => setLayoutType(e.target.value)}
              />
            </div>
          </div>
        </Card>

        {/* Key Points */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">核心要点</CardTitle>
          </CardHeader>
          <div className="space-y-3">
            {keyPoints.map((point, index) => (
              <div key={index} className="flex items-center gap-3">
                <span className="text-sm text-gray-400 font-medium w-6">{index + 1}.</span>
                <div className="flex-1">
                  <Input
                    value={point}
                    onChange={(e) => handleKeyPointChange(index, e.target.value)}
                    placeholder={`要点 ${index + 1}`}
                  />
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleRemoveKeyPoint(index)}
                  className="flex-shrink-0"
                >
                  <Trash2 className="w-4 h-4 text-gray-400 hover:text-red-500" />
                </Button>
              </div>
            ))}
            <Button variant="outline" size="md" onClick={handleAddKeyPoint} className="mt-2">
              <Plus className="w-4 h-4 mr-1.5" />
              添加要点
            </Button>
          </div>
        </Card>

        {/* Speaker Notes */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">演讲备注</CardTitle>
          </CardHeader>
          <Textarea
            value={speakerNotes}
            onChange={(e) => setSpeakerNotes(e.target.value)}
            placeholder="输入演讲备注，辅助演讲者讲解..."
            className="min-h-[140px]"
          />
        </Card>
      </div>
    </div>
  );
}
