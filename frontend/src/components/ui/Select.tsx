// Select component - Soft UI Style

import { forwardRef, SelectHTMLAttributes } from 'react';
import { clsx } from 'clsx';
import { ChevronDown } from 'lucide-react';

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: { value: string; label: string }[];
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, options, error, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="text-sm font-medium text-gray-600 mb-2 block">
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            className={clsx(
              'w-full px-5 py-3.5 bg-gray-50 border-0 rounded-2xl appearance-none',
              'text-gray-800',
              'focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:bg-white',
              'transition-all duration-200 ease-out cursor-pointer',
              'disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-gray-100',
              error && 'ring-2 ring-red-500/50',
              className
            )}
            {...props}
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
        </div>
        {error && (
          <p className="text-sm text-red-500 mt-2">{error}</p>
        )}
      </div>
    );
  }
);

Select.displayName = 'Select';
