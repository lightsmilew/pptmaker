/** Browser titles stay English, including presentations with a Chinese topic. */
export const studioTitles: Record<string, string> = {
  home: 'Folio — Let your ideas unfold.',
  settings: 'Creative direction — Folio',
  workspace: 'Your collection of ideas — Folio',
  account: 'Your creative rhythm — Folio',
  project: 'Your presentation, unfolding — Folio',
  support: 'A conversation worth having — Folio',
};
export const adminTitles: Record<string, string> = {
  overview: 'Behind the pages', users: 'People & accounts', memberships: 'Room to create',
  models: 'Models & connections', usage: 'Usage & allowances', records: 'Activity journal',
  account: 'Administrator account', support: 'Creator conversations', announcements: 'News for creators',
};
export const publicTitle = (registering: boolean) => registering
  ? 'Begin your first chapter — Folio' : 'Folio — Ideas deserve a beautiful stage.';
