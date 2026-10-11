import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { api } from '@/api/client';
import { adminApi } from '@/api/adminClient';
import { AnnouncementDialog } from '@/components/announcements/AnnouncementDialog';
import { AdminAnnouncements } from '@/components/admin/AdminAnnouncements';
vi.mock('@/api/client',()=>({api:{getAnnouncements:vi.fn(),dismissAnnouncement:vi.fn()}}));
vi.mock('@/api/adminClient',()=>({adminApi:{announcements:vi.fn(),createAnnouncement:vi.fn(),publishAnnouncement:vi.fn(),withdrawAnnouncement:vi.fn()}}));
const click = async (element:HTMLElement) => { await act(async()=>{ await userEvent.click(element); }); };
const type = async (element:HTMLElement,value:string) => { await act(async()=>{ await userEvent.type(element,value); }); };
const notice={id:'n1',title:'秋日创作提醒',body:'新的主题图片已就绪。\n欢迎创作。',revision:1,published_at:'2026-10-10T00:00:00Z',expires_at:null};
beforeEach(()=>{ vi.clearAllMocks(); vi.mocked(api.getAnnouncements).mockResolvedValue({items:[notice],day:'2026-10-10',timezone:'Asia/Shanghai'}); vi.mocked(api.dismissAnnouncement).mockResolvedValue({ok:true,day:'2026-10-10'}); });
it('saves daily dismissal only when checked; shows the next notice',async()=>{
 vi.mocked(api.getAnnouncements).mockResolvedValue({items:[notice,{...notice,id:'n2',title:'第二则公告'}],day:'2026-10-10',timezone:'Asia/Shanghai'});
 render(<AnnouncementDialog sessionKey="s1" />); await screen.findByRole('dialog',{name:notice.title});
 await click(screen.getByRole('checkbox',{name:'当日不再展示'})); await click(screen.getByRole('button',{name:'知道了'}));
 await screen.findByRole('dialog',{name:'第二则公告'}); expect(api.dismissAnnouncement).toHaveBeenCalledWith('n1',1);
 await click(screen.getByRole('button',{name:'知道了'})); await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull());
 expect(api.dismissAnnouncement).toHaveBeenCalledTimes(1);
});
it('keeps a failed dismissal open and clears notices when the account changes',async()=>{
 vi.mocked(api.dismissAnnouncement).mockRejectedValue(new Error('保存失败，请重试'));
 const view=render(<AnnouncementDialog sessionKey="s1" />); await screen.findByText(notice.title);
 await click(screen.getByRole('checkbox',{name:'当日不再展示'})); await click(screen.getByRole('button',{name:'知道了'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('保存失败'); expect(screen.getByRole('dialog')).toBeVisible();
 vi.mocked(api.getAnnouncements).mockResolvedValue({items:[],day:'2026-10-10',timezone:'Asia/Shanghai'});
 view.rerender(<AnnouncementDialog sessionKey="s2" />); await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull());
});
it('renders plain text and shows a notice again after the server day changes',async()=>{
 const body='<script>danger()</script>'; vi.mocked(api.getAnnouncements).mockResolvedValue({items:[{...notice,body}],day:'2026-10-10',timezone:'Asia/Shanghai'});
 render(<AnnouncementDialog sessionKey="s1" />); expect(await screen.findByText(body)).toBeVisible();
 await click(screen.getByRole('button',{name:'知道了'}));
 await act(async()=>{ fireEvent.focus(window); }); await waitFor(()=>expect(api.getAnnouncements).toHaveBeenCalledTimes(2)); expect(screen.queryByRole('dialog')).toBeNull();
 vi.mocked(api.getAnnouncements).mockResolvedValue({items:[notice],day:'2026-10-11',timezone:'Asia/Shanghai'}); await act(async()=>{ fireEvent.focus(window); });
 expect(await screen.findByRole('dialog',{name:notice.title})).toBeVisible();
});
it('saves an administrator draft before offering publish',async()=>{
 vi.mocked(adminApi.announcements).mockResolvedValue({items:[],total:0,page:1,page_size:20});
 vi.mocked(adminApi.createAnnouncement).mockResolvedValue({...notice,status:'draft'});
 render(<AdminAnnouncements />); await screen.findByText('这里还没有公告。写下第一条想传达的消息吧。');
 await click(screen.getByRole('button',{name:'新建公告'})); await type(screen.getByLabelText('公告标题'),'新功能'); await type(screen.getByLabelText('公告内容'),'主题图片已就绪');
 await click(screen.getByRole('button',{name:'保存草稿'}));
 await waitFor(()=>expect(adminApi.createAnnouncement).toHaveBeenCalledWith({title:'新功能',body:'主题图片已就绪',duration_days:null})); expect(adminApi.publishAnnouncement).not.toHaveBeenCalled();
});
