// Input component - Soft UI Style

import { forwardRef, InputHTMLAttributes } from 'react';
import { clsx } from 'clsx';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="text-sm font-medium text-gray-600 mb-2 block">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={clsx(
            'w-full px-5 py-3.5 bg-gray-50 border-0 rounded-2xl',
            'text-gray-800 placeholder-gray-400',
            'focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:bg-white',
            'transition-all duration-200 ease-out',
            'disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-gray-100',
            error && 'ring-2 ring-red-500/50',
            className
          )}
          {...props}
        />
        {error && (
          <p className="text-sm text-red-500 mt-2">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
