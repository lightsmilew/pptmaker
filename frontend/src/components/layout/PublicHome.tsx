import { useEffect, useState } from 'react';
import { ArrowRight, ArrowUpRight, Check, Eye, EyeOff, FileText, FolderOpen, LayoutTemplate, LockKeyhole, Quote, Sparkles } from 'lucide-react';
import { Button, Input } from '@/components/ui';
import { Brand } from './StudioShell';
import { api, type AuthSession } from '@/api/client';
import './public.css';

const styles = [
  { name:'商务简约', color:'#29483e', paper:'#faf9f6', title:'好想法，\n值得被看见。', label:'EDITORIAL / 01' },
  { name:'学术简约', color:'#234b70', paper:'#f7f9fb', title:'让研究，\n清晰地展开。', label:'RESEARCH / 02' },
  { name:'科技风', color:'#b8dacf', paper:'#17242c', title:'下一步，\n从这里开始。', label:'MIDNIGHT / 03' },
];
const features = [
  { icon:FileText, title:'从你已有的内容开始', text:'写下一段想法，或导入 PDF、Word、Markdown 与 TXT。把散落的资料放在一起，找到表达的主线。' },
  { icon:LayoutTemplate, title:'让内容找到合适的版式', text:'十六种演示风格，按受众与页数组织结构。标题、要点、图表和演讲备注，各有自己的位置。' },
  { icon:FolderOpen, title:'每一次表达，都有迹可循', text:'在自己的工作空间预览、下载与整理作品。搜索、收藏、标签和归档，让下一次创作更轻松。' },
];

export function PublicHome({ onAuthenticated, signedIn = false, onEnter }: {
  onAuthenticated: (session: AuthSession, registered?: boolean) => void; signedIn?: boolean; onEnter?: () => void;
}) {
  const [registering,setRegistering] = useState(window.location.hash === '#/register');
  const [email,setEmail] = useState(''); const [password,setPassword] = useState(''); const [name,setName] = useState('');
  const [confirm,setConfirm] = useState(''); const [showPassword,setShowPassword] = useState(false);
  const [busy,setBusy] = useState(false); const [error,setError] = useState(''); const [style,setStyle] = useState(0);
  useEffect(() => { const update = () => { setRegistering(window.location.hash === '#/register'); setError(''); }; window.addEventListener('hashchange',update); return () => window.removeEventListener('hashchange',update); }, []);
  useEffect(() => { document.title = registering ? '写下你的第一章 — Folio' : 'Folio — Ideas deserve a beautiful stage.'; }, [registering]);
  const switchMode = (value: boolean) => { setRegistering(value); setError(''); setPassword(''); setConfirm(''); window.location.hash = value ? '/register' : '/login'; };
  const focusAuth = (value: boolean) => { switchMode(value); document.getElementById('welcome-form')?.scrollIntoView({ behavior:'smooth', block:'center' }); };
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    if (registering && password !== confirm) { setError('两次输入的密码不一致'); return; }
    setBusy(true);
    try { onAuthenticated(registering ? await api.register(email,password,name.trim()) : await api.login(email,password),registering); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const theme = styles[style];
  return <div className="public-site">
    <header className="public-header"><Brand href="#/" /><nav aria-label="了解 Folio"><a href="#features" onClick={e => { e.preventDefault(); document.getElementById('features')?.scrollIntoView({behavior:'smooth'}); }}>功能</a><a href="#how-it-works" onClick={e => { e.preventDefault(); document.getElementById('how-it-works')?.scrollIntoView({behavior:'smooth'}); }}>如何开始</a><a href="#questions" onClick={e => { e.preventDefault(); document.getElementById('questions')?.scrollIntoView({behavior:'smooth'}); }}>常见问题</a></nav><div className="public-header-actions">{signedIn ? <Button onClick={onEnter}>进入工作台 <ArrowUpRight size={14} /></Button> : <><button className="text-link" onClick={() => focusAuth(false)}>登录</button><Button size="sm" onClick={() => focusAuth(true)}>开始创作 <ArrowUpRight size={14} /></Button></>}</div></header>
    <main>
      <section className="public-hero">
        <div className="public-hero-copy"><p className="eyebrow"><span /> A QUIET SPACE FOR BIG IDEAS</p><h1>让想法展开。<br /><em>让表达动人。</em></h1><p className="hero-description">从零散的笔记，到一份有条理的演示。<br />Folio 帮你整理内容、铺陈故事，<br className="desktop-break" />把时间留给真正想说的话。</p><div className="hero-note"><span className="tiny-rule" /><span>你的内容，你的节奏，你的作品。</span></div>
          <div className="hero-sample" style={{background:theme.paper,color:theme.color}} aria-label={`${theme.name}样式预览`}><div className="hero-sample-top"><span>{theme.label}</span><span>Folio.</span></div><strong>{theme.title}</strong><div className="hero-sample-bottom"><span>一次清晰表达的开始</span><span>01 — 04</span></div><div className="hero-sample-band" /></div>
          <div className="public-theme-switch" aria-label="预览演示风格">{styles.map((s,i) => <button key={s.name} onClick={() => setStyle(i)} aria-pressed={style===i}><span style={{background:s.color}} />{s.name}{style===i && <Check size={12} />}</button>)}<span>样式示意</span></div>
        </div>
        <aside className="public-auth" id="welcome-form"><span className="auth-kicker">YOUR NEXT CHAPTER</span>{signedIn ? <><h2>欢迎回来。</h2><p>你的想法与作品，正在工作空间里等你。</p><Button onClick={onEnter}>继续创作 <ArrowRight size={15} /></Button></> : <><div className="auth-tabs"><button aria-pressed={!registering} className={!registering ? 'active' : ''} onClick={() => switchMode(false)}>登录</button><button aria-pressed={registering} className={registering ? 'active' : ''} onClick={() => switchMode(true)}>创建账号</button></div><h2>{registering ? '写下你的第一章。' : '欢迎回来。'}</h2><p>{registering ? '为你的想法，留一处自己的空间。' : '登录 Folio，继续上一次的灵感。'}</p><form onSubmit={submit}>
          {registering && <Input label="怎么称呼你" autoComplete="nickname" required maxLength={40} value={name} onChange={e => setName(e.target.value)} placeholder="你的名字" disabled={busy} />}
          <Input label="登录邮箱" type="email" autoComplete="username" required maxLength={254} value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" disabled={busy} />
          <div className="password-field"><Input label="密码" type={showPassword ? 'text' : 'password'} autoComplete={registering ? 'new-password' : 'current-password'} required minLength={10} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} placeholder="至少 10 个字符" disabled={busy} /><button type="button" aria-label={showPassword ? '隐藏密码' : '显示密码'} onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div>
          {registering && <Input label="确认密码" type="password" autoComplete="new-password" required minLength={10} maxLength={128} value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="再次输入密码" disabled={busy} />}
          {error && <p className="studio-error" role="alert">{error}</p>}
          <Button type="submit" isLoading={busy}>{registering ? '创建账号，开始创作' : '登录，展开想法'} <ArrowRight size={15} /></Button>
        </form><div className="auth-footnote"><LockKeyhole size={14} /><span>从一个想法开始，<br />展开你的下一次表达。</span></div></>}
          <div className="auth-margin-note"><Quote size={19} /><p>好内容，<br />值得好好呈现。</p><span>LET YOUR IDEAS UNFOLD.</span></div>
        </aside>
      </section>
      <div className="public-format-strip"><span>从熟悉的材料开始</span><div><span>PDF</span><span>Word</span><span>Markdown</span><span>TXT</span><span>一段灵感</span></div><span>以可编辑 PowerPoint 交付 <ArrowUpRight size={14} /></span></div>
      <section className="public-section" id="features"><div className="public-section-heading"><p className="eyebrow">MADE FOR YOUR IDEAS</p><h2>从内容到演示，<br />少一点忙乱，多一点从容。</h2><p>让工具处理结构与版式。<br />让你专注观点、故事和听众。</p></div><div className="public-feature-grid">{features.map((f,i) => <article key={f.title}><div className="feature-top"><f.icon size={23} strokeWidth={1.4} /><span>0{i+1}</span></div><h3>{f.title}</h3><p>{f.text}</p></article>)}</div></section>
      <section className="public-process" id="how-it-works"><div className="public-section-heading"><p className="eyebrow">A SIMPLE, THOUGHTFUL FLOW</p><h2>三步，把想法展开成页。</h2><p>从一份材料开始，走向一次清晰的表达。</p></div><ol>{[{title:'放入你的内容',text:'写下主题与要求，或把参考文档拖入制作工作台。'}, {title:'选一种表达方式',text:'决定听众、页数和风格，让大纲与页面围绕内容展开。'}, {title:'预览，然后带走',text:'查看页面与演讲备注，下载可编辑的 PowerPoint，继续打磨。'}].map((s,i) => <li key={s.title}><span className="process-number">0{i+1}</span><div><h3>{s.title}</h3><p>{s.text}</p></div><ArrowRight size={19} /></li>)}</ol></section>
      <section className="public-section public-use-cases"><div className="public-section-heading"><p className="eyebrow">EVERY STORY HAS ITS STAGE</p><h2>不同的场合，同样清晰。</h2></div><div>{[{name:'汇报与提案',en:'PRESENT WITH PURPOSE',text:'把进展、洞察与下一步，讲成一个有重点的故事。',mark:'01'}, {name:'研究与分享',en:'MAKE KNOWLEDGE CLEAR',text:'让复杂的概念有层次，让关键结论被看见。',mark:'02'}, {name:'课程与教学',en:'GIVE IDEAS ROOM',text:'从知识框架到课堂要点，为理解留出空间。',mark:'03'}].map(c => <article key={c.name}><span>{c.mark}</span><small>{c.en}</small><h3>{c.name}</h3><p>{c.text}</p></article>)}</div></section>
      <section className="public-faq" id="questions"><div className="public-section-heading"><p className="eyebrow">BEFORE YOU BEGIN</p><h2>开始前，你可能想知道。</h2></div><div>{[{q:'我需要先写好完整的大纲吗？',a:'不用。可以先写下主题、听众和关键观点，也可以上传现有文档。Folio 会根据内容规划演示结构；具体要求越清楚，内容越贴近你的目标。'}, {q:'生成的文件可以继续编辑吗？',a:'可以。导出格式为 .pptx，文字、基础形状、表格和支持的图表可在 PowerPoint 中继续编辑。网页提供预览和演讲备注。'}, {q:'支持哪些文件？',a:'支持可提取文本的 PDF、DOCX、Markdown 和 TXT，单文件最大 10 MiB。扫描 PDF 需先转换为文本，暂不支持旧版 .doc。'}, {q:'制作完成后，如何获得演示文件？',a:'先在网页查看页面预览，再点击“下载 PowerPoint”带走作品。文件不会自动下载，你可以按自己的节奏继续打磨。'}].map(f => <details key={f.q}><summary>{f.q}<span>+</span></summary><p>{f.a}</p></details>)}</div></section>
      <section className="public-final-cta"><div><p className="eyebrow">LET YOUR IDEAS UNFOLD.</p><h2>下一次好表达，<br />从你的一个想法开始。</h2></div><Button onClick={signedIn ? onEnter : () => focusAuth(true)}>开始你的第一份演示 <ArrowUpRight size={16} /></Button></section>
    </main><footer className="public-footer"><Brand href="#/" /><p>好内容，值得好好呈现。</p><span>Folio — Let your ideas unfold.</span><a className="text-link" href="#/admin/login">管理入口</a></footer>
  </div>;
}
