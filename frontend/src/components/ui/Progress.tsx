// Progress component - Folio shared design system

import * as ProgressPrimitive from '@radix-ui/react-progress';
import { clsx } from 'clsx';

interface ProgressProps {
  value: number;
  max?: number;
  className?: string;
  showLabel?: boolean;
  variant?: 'default' | 'success' | 'warning' | 'error';
}

const variantStyles = {
  default: 'bg-[#547459]',
  success: 'bg-[#547459]',
  warning: 'bg-amber-500',
  error: 'bg-red-500',
};

export function Progress({ value, max = 100, className, showLabel = false, variant = 'default' }: ProgressProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div className={clsx('w-full', className)}>
      <ProgressPrimitive.Root
        className="relative h-1 w-full overflow-hidden rounded-full bg-gray-100"
        value={value}
        max={max}
      >
        <ProgressPrimitive.Indicator
          className={clsx('h-full rounded-full transition-all duration-300 ease-out', variantStyles[variant])}
          style={{ width: `${percentage}%` }}
        />
      </ProgressPrimitive.Root>
      {showLabel && (
        <span className="text-xs text-gray-500 mt-2 block text-right">{Math.round(percentage)}%</span>
      )}
    </div>
  );
}
