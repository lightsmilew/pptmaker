// Badge component - Folio shared design system

import { cva, type VariantProps } from 'class-variance-authority';
import { clsx } from 'clsx';

const badgeVariants = cva(
  'inline-flex items-center px-2 py-1 rounded-md text-[10px] font-medium transition-all duration-200',
  {
    variants: {
      variant: {
        default: 'bg-gray-100 text-gray-600',
        primary: 'bg-[#e8eee5] text-[#52644d]',
        secondary: 'bg-[#edf1e8] text-[#52644d]',
        success: 'bg-[#e8eee5] text-[#52644d]',
        warning: 'bg-amber-100 text-amber-600',
        error: 'bg-red-100 text-red-600',
        info: 'bg-[#edf1e8] text-[#52644d]',
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
