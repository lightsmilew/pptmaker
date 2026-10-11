// Button component - Folio shared design system

import { forwardRef, ButtonHTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { clsx } from 'clsx';
import { Loader2 } from 'lucide-react';
import './button.css';

const buttonVariants = cva(
  'folio-button inline-flex items-center justify-center gap-2 font-medium rounded-md transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-emerald-800 disabled:opacity-50 disabled:cursor-not-allowed',
  {
    variants: {
      variant: {
        primary: 'bg-[#29483e] text-white hover:bg-[#203a32]',
        secondary: 'folio-button-secondary',
        outline: 'folio-button-outline',
        ghost: 'folio-button-ghost',
        danger: 'bg-red-600 text-white hover:bg-red-700',
      },
      size: {
        sm: 'px-3 py-2 text-xs',
        md: 'px-4 py-2.5 text-xs',
        lg: 'px-6 py-3 text-base',
        xl: 'px-8 py-4 text-lg',
        icon: 'w-11 h-11',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, isLoading, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={clsx(buttonVariants({ variant, size, className }))}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
