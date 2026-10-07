// Textarea component — Folio shared design system

import { forwardRef, useId, TextareaHTMLAttributes } from 'react';
import { clsx } from 'clsx';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
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
        <textarea
          ref={ref}
          id={inputId}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : props['aria-describedby']}
          className={clsx('studio-field resize-y', error && 'field-invalid', className)}
          {...props}
        />
        {error && (
          <p id={`${inputId}-error`} className="field-error">{error}</p>
        )}
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';
