import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { StudioShell } from '@/components/layout/StudioShell';

it('provides branded direct mobile navigation with a clear current page and no drawer controls', () => {
  const navigate=vi.fn(); render(<StudioShell section="settings" onNavigate={navigate} onNew={vi.fn()} account={null} hasProject={false}>内容</StudioShell>);
  expect(document.querySelector('.mobile-brand img')).toHaveAttribute('src','/folio-mark.svg');
  expect(document.querySelector('.topbar-breadcrumb strong')).toHaveTextContent('创作方案');
  expect(screen.queryByRole('button',{name:'打开导航菜单'})).toBeNull();
  const mobile=screen.getByRole('navigation',{name:'工作台页面导航'});
  expect(within(mobile).getByRole('button',{name:'前往创作方案'})).toHaveAttribute('aria-current','page');
  fireEvent.click(within(mobile).getByRole('button',{name:'前往我的工作空间'}));
  expect(navigate).toHaveBeenCalledWith('workspace');
});
it('keeps the mobile logout in the account page and carries unread state into navigation', () => {
  const logout=vi.fn(); render(<StudioShell section="account" onNavigate={vi.fn()} onNew={vi.fn()} onLogout={logout} account={null} hasProject={false} supportUnread={3}>账号内容</StudioShell>);
  expect(document.querySelector('.mobile-unread')).toHaveTextContent('3');
  fireEvent.click(screen.getByRole('button',{name:'退出当前账号'})); expect(logout).toHaveBeenCalledTimes(1);
});
it('offers every admin destination and the active presentation from the mobile navigation', () => {
  const {rerender}=render(<StudioShell section="admin-announcements" mode="admin" onNavigate={vi.fn()} onNew={vi.fn()} account={null} hasProject={false}>管理内容</StudioShell>);
  const mobile=screen.getByRole('navigation',{name:'管理页面导航'});
  expect(within(mobile).getAllByRole('button')).toHaveLength(9);
  expect(within(mobile).getByRole('button',{name:'前往公告管理'})).toHaveAttribute('aria-current','page');
  rerender(<StudioShell section="project" onNavigate={vi.fn()} onNew={vi.fn()} account={null} hasProject projectTitle="一份很长的演示标题">演示内容</StudioShell>);
  expect(screen.getByRole('button',{name:'前往当前演示'})).toHaveAttribute('aria-current','page');
});
