// Tabs component - Soft UI Style

import { forwardRef } from 'react';
import * as TabsPrimitive from '@radix-ui/react-tabs';
import { clsx } from 'clsx';

export const Tabs = TabsPrimitive.Root;

export const TabsList = forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={clsx(
      'inline-flex h-12 p-1.5 bg-gray-100 rounded-2xl gap-1',
      className
    )}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

export const TabsTrigger = forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={clsx(
      'inline-flex items-center justify-center whitespace-nowrap px-5 py-2.5 rounded-xl text-sm font-medium',
      'text-gray-500 transition-all duration-200',
      'hover:text-gray-700',
      'focus:outline-none focus:ring-2 focus:ring-indigo-500/50',
      'disabled:pointer-events-none disabled:opacity-50',
      'data-[state=active]:bg-white data-[state=active]:text-gray-800 data-[state=active]:shadow-soft-sm',
      className
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

export const TabsContent = forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={clsx(
      'mt-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50',
      className
    )}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;
