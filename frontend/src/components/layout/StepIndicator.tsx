// Step indicator component - Soft UI Style

import { clsx } from 'clsx';
import { Check, FileText, Map, PenTool, Download } from 'lucide-react';

export type Step = 'input' | 'plan' | 'generate' | 'export';

interface StepIndicatorProps {
  currentStep: Step;
  progress: number;
}

const steps: { id: Step; label: string; icon: typeof FileText }[] = [
  { id: 'input', label: '输入需求', icon: FileText },
  { id: 'plan', label: '生成大纲', icon: Map },
  { id: 'generate', label: '内容生成', icon: PenTool },
  { id: 'export', label: '导出文件', icon: Download },
];

export function StepIndicator({ currentStep, progress }: StepIndicatorProps) {
  const currentIndex = steps.findIndex((s) => s.id === currentStep);

  return (
    <div className="w-full max-w-3xl mx-auto mb-10">
      <div className="flex items-center justify-between">
        {steps.map((step, index) => {
          const isCompleted = index < currentIndex || (index === currentIndex && progress === 100);
          const isCurrent = index === currentIndex && progress < 100;
          const Icon = step.icon;

          return (
            <div key={step.id} className="flex items-center flex-1">
              {/* Step circle */}
              <div className="flex flex-col items-center">
                <div
                  className={clsx(
                    'w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-300 shadow-soft-md',
                    isCompleted && 'bg-indigo-600 text-white',
                    isCurrent && 'bg-white text-indigo-600 ring-4 ring-indigo-100',
                    !isCompleted && !isCurrent && 'bg-gray-100 text-gray-400'
                  )}
                >
                  {isCompleted ? <Check className="w-6 h-6" /> : <Icon className="w-5 h-5" />}
                </div>
                <span
                  className={clsx(
                    'text-sm mt-3 font-medium',
                    isCompleted && 'text-indigo-600',
                    isCurrent && 'text-gray-700',
                    !isCompleted && !isCurrent && 'text-gray-400'
                  )}
                >
                  {step.label}
                </span>
              </div>

              {/* Connector line */}
              {index < steps.length - 1 && (
                <div
                  className={clsx(
                    'flex-1 h-1.5 mx-3 rounded-full transition-all duration-500',
                    index < currentIndex ? 'bg-indigo-500' : 'bg-gray-200'
                  )}
                  style={{ marginTop: '-1.5rem' }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
