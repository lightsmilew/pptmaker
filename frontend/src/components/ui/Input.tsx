// Input component — Folio shared design system

import { forwardRef, useId, InputHTMLAttributes } from 'react';
import { clsx } from 'clsx';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => {
    const fieldId = useId();
    const inputId = id || fieldId;
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="field-label">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : props['aria-describedby']}
          className={clsx('studio-field', error && 'field-invalid', className)}
          {...props}
        />
        {error && (
          <p id={`${inputId}-error`} className="field-error">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
