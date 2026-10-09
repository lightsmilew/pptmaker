import { forwardRef, useEffect, useId, useImperativeHandle, useRef, useState, InputHTMLAttributes } from 'react';
import { clsx } from 'clsx';
import { Minus, Plus } from 'lucide-react';
import './controls.css';

export interface NumberInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'value' | 'defaultValue' | 'onChange' | 'min' | 'max' | 'step'> {
  label?: string;
  error?: string;
  value: number;
  onValueChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  compact?: boolean;
}

export const NumberInput = forwardRef<HTMLInputElement, NumberInputProps>(
  ({ label, error, id, className, value, onValueChange, min, max, step = 1, compact, disabled, readOnly, onBlur, ...props }, ref) => {
    const fieldId = useId();
    const inputId = id || fieldId;
    const inputRef = useRef<HTMLInputElement>(null);
    const [draft, setDraft] = useState(String(value));
    useImperativeHandle(ref, () => inputRef.current!, []);
    useEffect(() => { setDraft(String(value)); }, [value]);

    // Keep incomplete edits local; only valid numbers change the application value.
    const commit = () => {
      const number = draft.trim() ? Number(draft) : value;
      const bounded = Math.min(max ?? Infinity, Math.max(min ?? -Infinity, Number.isFinite(number) ? number : value));
      const base = min ?? 0;
      const snapped = Number((base + Math.round((bounded - base) / step) * step).toPrecision(12));
      const next = Math.min(max ?? Infinity, Math.max(min ?? -Infinity, snapped));
      setDraft(String(next));
      if (next !== value) onValueChange(next);
    };
    const adjust = (direction: 1 | -1) => {
      const input = inputRef.current;
      if (!input || disabled || readOnly) return;
      // Native stepping respects decimal precision, min/max and the step base.
      if (direction > 0) input.stepUp();
      else input.stepDown();
      if (input.value === '') return;
      const next = Number(input.value);
      setDraft(String(next));
      if (next !== value) onValueChange(next);
    };
    const numericDraft = draft.trim() && Number.isFinite(Number(draft)) ? Number(draft) : value;
    const controlName = label || props['aria-label'] || '数值';
    const locked = disabled || readOnly;

    return (
      <div className={clsx('folio-number-control', compact ? 'is-compact' : 'w-full')}>
        {label && <label htmlFor={inputId} className="field-label">{label}</label>}
        <div className={clsx('folio-number-field', error && 'is-invalid', disabled && 'is-disabled')}>
          <button type="button" className="folio-number-step" aria-label={`减少${controlName}`} disabled={locked || (min !== undefined && numericDraft <= min)} onClick={() => adjust(-1)}><Minus size={12} /></button>
          <input
            {...props}
            ref={inputRef}
            id={inputId}
            type="number"
            inputMode={props.inputMode || (Number.isInteger(step) ? 'numeric' : 'decimal')}
            min={min}
            max={max}
            step={step}
            value={draft}
            disabled={disabled}
            readOnly={readOnly}
            aria-invalid={!!error}
            aria-describedby={[props['aria-describedby'], error && `${inputId}-error`].filter(Boolean).join(' ') || undefined}
            className={clsx('studio-field folio-number-input', className)}
            onChange={event => {
              setDraft(event.target.value);
              if (event.target.value !== '' && event.target.validity.valid) onValueChange(Number(event.target.value));
            }}
            onBlur={event => { if (!locked) commit(); onBlur?.(event); }}
          />
          <button type="button" className="folio-number-step" aria-label={`增加${controlName}`} disabled={locked || (max !== undefined && numericDraft >= max)} onClick={() => adjust(1)}><Plus size={12} /></button>
        </div>
        {error && <p id={`${inputId}-error`} className="field-error">{error}</p>}
      </div>
    );
  }
);

NumberInput.displayName = 'NumberInput';
