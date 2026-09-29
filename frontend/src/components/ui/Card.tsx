// Card component - Soft UI Style

import { forwardRef, HTMLAttributes } from 'react';
import { clsx } from 'clsx';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
  selected?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, hover = false, selected = false, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={clsx(
          'bg-white rounded-3xl shadow-soft-lg p-6 md:p-8',
          'transition-all duration-300 ease-out',
          hover && 'hover:shadow-soft-xl hover:-translate-y-1 cursor-pointer',
          selected && 'ring-2 ring-indigo-500/30 ring-offset-2',
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={clsx('mb-5', className)} {...props} />
  )
);

CardHeader.displayName = 'CardHeader';

export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={clsx('text-xl md:text-2xl font-semibold text-gray-800', className)} {...props} />
  )
);

CardTitle.displayName = 'CardTitle';

export const CardDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={clsx('text-sm text-gray-400 mt-2', className)} {...props} />
  )
);

CardDescription.displayName = 'CardDescription';

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={clsx('', className)} {...props} />
  )
);

CardContent.displayName = 'CardContent';
