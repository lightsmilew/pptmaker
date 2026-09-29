// Button component - Soft UI Style

import { forwardRef, ButtonHTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { clsx } from 'clsx';
import { Loader2 } from 'lucide-react';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 font-medium rounded-2xl transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500/50 disabled:opacity-50 disabled:cursor-not-allowed',
  {
    variants: {
      variant: {
        primary: 'bg-indigo-600 text-white shadow-lg hover:-translate-y-0.5 hover:shadow-xl hover:shadow-indigo-500/30 active:scale-95 active:shadow-md',
        secondary: 'bg-white text-gray-700 shadow-lg hover:-translate-y-0.5 hover:shadow-xl active:scale-95 active:shadow-md',
        outline: 'bg-transparent text-indigo-600 border-2 border-indigo-200 hover:bg-indigo-50 hover:border-indigo-300 active:scale-95',
        ghost: 'bg-transparent text-gray-600 hover:bg-gray-100 active:scale-95',
        danger: 'bg-red-500 text-white shadow-lg hover:-translate-y-0.5 hover:shadow-xl hover:shadow-red-500/30 active:scale-95',
      },
      size: {
        sm: 'px-4 py-2 text-sm',
        md: 'px-5 py-2.5 text-sm',
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
