// Badge component - Soft UI Style

import { cva, type VariantProps } from 'class-variance-authority';
import { clsx } from 'clsx';

const badgeVariants = cva(
  'inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200',
  {
    variants: {
      variant: {
        default: 'bg-gray-100 text-gray-600',
        primary: 'bg-indigo-100 text-indigo-600',
        secondary: 'bg-pink-100 text-pink-600',
        success: 'bg-emerald-100 text-emerald-600',
        warning: 'bg-amber-100 text-amber-600',
        error: 'bg-red-100 text-red-600',
        info: 'bg-cyan-100 text-cyan-600',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={clsx(badgeVariants({ variant }), className)} {...props} />;
}
