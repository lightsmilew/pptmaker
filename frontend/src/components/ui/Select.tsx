import { forwardRef, useId, ComponentPropsWithoutRef } from 'react';
import * as SelectPrimitive from '@radix-ui/react-select';
import { clsx } from 'clsx';
import { Check, ChevronDown, ChevronUp } from 'lucide-react';
import './controls.css';

export interface SelectProps extends Omit<ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>, 'value' | 'defaultValue' | 'onChange' | 'children'> {
  label?: string;
  options: { value: string; label: string; disabled?: boolean }[];
  error?: string;
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  name?: string;
  required?: boolean;
  autoComplete?: string;
}

export const Select = forwardRef<HTMLButtonElement, SelectProps>(
  ({ className, label, options, error, id, value, defaultValue, onValueChange, placeholder, name, required, autoComplete, disabled, form, ...props }, ref) => {
    const fieldId = useId();
    const inputId = id || fieldId;
    return (
      <div className="w-full">
        {label && <label htmlFor={inputId} className="field-label">{label}</label>}
        <SelectPrimitive.Root value={value} defaultValue={defaultValue} onValueChange={onValueChange} name={name} required={required} autoComplete={autoComplete} disabled={disabled} form={form}>
          <SelectPrimitive.Trigger
            {...props}
            ref={ref}
            id={inputId}
            aria-invalid={!!error}
            aria-describedby={[props['aria-describedby'], error && `${inputId}-error`].filter(Boolean).join(' ') || undefined}
            className={clsx('studio-field folio-select-trigger', error && 'field-invalid', className)}
          >
            <SelectPrimitive.Value placeholder={placeholder} />
            <SelectPrimitive.Icon asChild><ChevronDown size={14} className="folio-select-chevron" /></SelectPrimitive.Icon>
          </SelectPrimitive.Trigger>
          <SelectPrimitive.Portal>
            <SelectPrimitive.Content className="folio-select-menu" position="popper" align="start" sideOffset={5} collisionPadding={12}>
              <SelectPrimitive.ScrollUpButton className="folio-select-scroll"><ChevronUp size={13} /></SelectPrimitive.ScrollUpButton>
              <SelectPrimitive.Viewport className="folio-select-viewport">
                {options.map(option => (
                  <SelectPrimitive.Item key={option.value} value={option.value} disabled={option.disabled} className="folio-select-option">
                    <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
                    <SelectPrimitive.ItemIndicator className="folio-select-check"><Check size={13} /></SelectPrimitive.ItemIndicator>
                  </SelectPrimitive.Item>
                ))}
              </SelectPrimitive.Viewport>
              <SelectPrimitive.ScrollDownButton className="folio-select-scroll"><ChevronDown size={13} /></SelectPrimitive.ScrollDownButton>
            </SelectPrimitive.Content>
          </SelectPrimitive.Portal>
        </SelectPrimitive.Root>
        {error && <p id={`${inputId}-error`} className="field-error">{error}</p>}
      </div>
    );
  }
);

Select.displayName = 'Select';
