import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import App from '@/App';
import { adminApi, setAdminCsrf } from '@/api/adminClient';
import { api } from '@/api/client';

vi.mock('@/hooks/useWebSocket',()=>({ useWebSocket:vi.fn() }));
vi.mock('@/api/client',()=>({ setSessionCsrf:vi.fn(),api:{ getSession:vi.fn(),logout:vi.fn() } }));
vi.mock('@/api/adminClient',()=>({ setAdminCsrf:vi.fn(),adminApi:{ session:vi.fn(),login:vi.fn(),logout:vi.fn(),overview:vi.fn() } }));

const account = { profile:{ account_id:'dedicated-admin',display_name:'验收管理员' }, membership:{ name:'普通会员' }, account:{ role:'admin' } };
beforeEach(()=>{
  vi.clearAllMocks(); window.location.hash='/admin/login';
  vi.mocked(api.getSession).mockRejectedValue(new Error('请先登录 Folio'));
  vi.mocked(adminApi.session).mockRejectedValue(new Error('请从管理入口登录'));
});

it('uses the dedicated login and can return to the public homepage without an admin redirect loop',async()=>{
  render(<App />);
  await screen.findByRole('heading',{name:'进入管理中心'});
  expect(api.getSession).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('link',{name:'返回 Folio'}));
  // jsdom's hash navigation is observed asynchronously, as in the browser.
  await screen.findByRole('textbox',{name:'登录邮箱'});
  await waitFor(()=>expect(window.location.hash).toBe('#/login'));
  expect(screen.queryByRole('textbox',{name:'管理员邮箱'})).not.toBeInTheDocument();
});

it('authenticates and expires the admin session independently of the user session',async()=>{
  vi.mocked(adminApi.login).mockResolvedValue({ account,csrf_token:'admin-csrf' } as unknown as Awaited<ReturnType<typeof adminApi.login>>);
  vi.mocked(adminApi.overview).mockResolvedValue({ period:'2026-10',users:0,active_users:0,disabled_users:0,projects:0,completed:0,running:0,failed_logins:0,usage:{ calls:0,input_tokens:0,output_tokens:0,failures:0 },provider:'openai',model:'unconfigured',provider_connected:false,recent:[] });
  render(<App />);
  fireEvent.change(await screen.findByRole('textbox',{name:'管理员邮箱'}),{target:{value:'admin@example.test'}});
  fireEvent.change(screen.getByLabelText('密码'),{target:{value:'smile'}});
  expect(screen.getByLabelText('密码')).toHaveAttribute('minlength','1');
  fireEvent.click(screen.getByRole('button',{name:'登录管理中心'}));
  await screen.findByRole('heading',{name:'让每一份创作，有序展开。'});
  expect(adminApi.login).toHaveBeenCalledWith('admin@example.test','smile');
  expect(setAdminCsrf).toHaveBeenCalledWith('admin-csrf');
  expect(api.getSession).not.toHaveBeenCalled();
  act(()=>window.dispatchEvent(new Event('folio-admin-expired')));
  await screen.findByRole('heading',{name:'进入管理中心'});
  expect(window.location.hash).toBe('#/admin/login');
  expect(api.logout).not.toHaveBeenCalled();
});
