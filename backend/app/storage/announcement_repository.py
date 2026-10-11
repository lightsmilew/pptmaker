"""Administrator notices and per-user daily dismissal receipts."""
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .account_repository import database_path


def now():
    return datetime.now(timezone.utc)


def display_day():
    return now().astimezone(timezone(timedelta(hours=8))).date().isoformat()


class AnnouncementRepository:
    def __init__(self,path=None):
        self.path=path or database_path()
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS announcements (
                    id TEXT PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',duration_days INTEGER,
                    created_at TEXT NOT NULL,updated_at TEXT NOT NULL,published_at TEXT,
                    expires_at TEXT,revision INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS announcement_dismissals (
                    user_id TEXT NOT NULL,announcement_id TEXT NOT NULL,revision INTEGER NOT NULL,
                    day TEXT NOT NULL,PRIMARY KEY(user_id,announcement_id));
            ''')

    def connect(self):
        db=sqlite3.connect(self.path,timeout=15); db.row_factory=sqlite3.Row
        return db

    def list(self,status='all',page=1):
        with self.connect() as db:
            where='' if status=='all' else ' WHERE status=?'
            args=[] if status=='all' else [status]
            total=db.execute('SELECT COUNT(*) FROM announcements'+where,args).fetchone()[0]
            rows=db.execute('SELECT * FROM announcements'+where+' ORDER BY updated_at DESC,id DESC LIMIT 20 OFFSET ?',[*args,(page-1)*20])
            return dict(items=[dict(row) for row in rows],total=total,page=page,page_size=20)

    def get(self,aid):
        with self.connect() as db:
            row=db.execute('SELECT * FROM announcements WHERE id=?',(aid,)).fetchone()
            return dict(row) if row else None

    def save(self,title,body,duration_days,aid=None):
        stamp=now().isoformat(); aid=aid or 'notice_'+uuid.uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT status FROM announcements WHERE id=?',(aid,)).fetchone()
            if existing and existing['status']=='published':
                raise ValueError('请先撤回公告再修改')
            if existing:
                db.execute("UPDATE announcements SET title=?,body=?,duration_days=?,status='draft',updated_at=? WHERE id=?",(title,body,duration_days,stamp,aid))
            else:
                db.execute("INSERT INTO announcements(id,title,body,duration_days,created_at,updated_at) VALUES (?,?,?,?,?,?)",(aid,title,body,duration_days,stamp,stamp))
        return self.get(aid)

    def publish(self,aid,published):
        stamp=now()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM announcements WHERE id=?',(aid,)).fetchone()
            if not row: return None
            # Repeated submission is idempotent; it must not bypass daily receipts.
            if published and row['status']=='published': return dict(row)
            if published:
                expires=(stamp+timedelta(days=row['duration_days'])).isoformat() if row['duration_days'] else None
                db.execute("UPDATE announcements SET status='published',published_at=?,expires_at=?,updated_at=?,revision=revision+1 WHERE id=?",(stamp.isoformat(),expires,stamp.isoformat(),aid))
            else:
                db.execute("UPDATE announcements SET status='withdrawn',updated_at=? WHERE id=?",(stamp.isoformat(),aid))
        return self.get(aid)

    def active(self,uid):
        with self.connect() as db:
            rows=db.execute('''SELECT a.id,a.title,a.body,a.published_at,a.expires_at,a.revision FROM announcements a
                WHERE a.status='published' AND (a.expires_at IS NULL OR a.expires_at>?)
                AND NOT EXISTS (SELECT 1 FROM announcement_dismissals d WHERE d.user_id=?
                    AND d.announcement_id=a.id AND d.revision=a.revision AND d.day=?)
                ORDER BY a.published_at DESC,a.id DESC''',(now().isoformat(),uid,display_day()))
            return [dict(row) for row in rows]

    def dismiss(self,uid,aid,revision):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM announcements WHERE id=? AND status='published' AND revision=?",(aid,revision)).fetchone()
            if not row or (row['expires_at'] and row['expires_at']<=now().isoformat()): return False
            db.execute('''INSERT INTO announcement_dismissals VALUES (?,?,?,?) ON CONFLICT(user_id,announcement_id)
                DO UPDATE SET revision=excluded.revision,day=excluded.day''',(uid,aid,revision,display_day()))
        return True
