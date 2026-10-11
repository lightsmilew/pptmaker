"""User support conversations, ordered messages, images and per-reader receipts."""
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .account_repository import database_path


class SupportRepository:
    def __init__(self, path=None):
        self.path = path or database_path()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS support_conversations (
                    user_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'open', updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS support_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, author_id TEXT NOT NULL,
                    author_role TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL,
                    request_id TEXT NOT NULL, UNIQUE(author_id,request_id));
                CREATE INDEX IF NOT EXISTS support_thread ON support_messages(user_id,id);
                CREATE TABLE IF NOT EXISTS support_images (
                    id TEXT PRIMARY KEY, message_id INTEGER NOT NULL, user_id TEXT NOT NULL,
                    filename TEXT NOT NULL, size INTEGER NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS support_image_message ON support_images(message_id);
                CREATE TABLE IF NOT EXISTS support_attachments (
                    id TEXT PRIMARY KEY, message_id INTEGER NOT NULL, user_id TEXT NOT NULL,
                    filename TEXT NOT NULL, size INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS support_attachment_message ON support_attachments(message_id);
                CREATE TABLE IF NOT EXISTS support_reads (
                    user_id TEXT NOT NULL, reader_id TEXT NOT NULL, last_id INTEGER NOT NULL,
                    PRIMARY KEY(user_id,reader_id));
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def conversation(self, uid, reader, admin=False):
        with self.connect() as db:
            row = db.execute("""SELECT u.id AS user_id,u.email,json_extract(u.profile,'$.display_name') AS display_name,
                COALESCE(c.status,'open') AS status,c.updated_at,
                (SELECT COUNT(*) FROM support_messages m WHERE m.user_id=u.id AND m.author_role=?
                 AND m.id>COALESCE((SELECT last_id FROM support_reads WHERE user_id=u.id AND reader_id=?),0)) AS unread,
                (SELECT MAX(id) FROM support_messages m WHERE m.user_id=u.id) AS last_message_id,
                (SELECT text FROM support_messages m WHERE m.user_id=u.id ORDER BY id DESC LIMIT 1) AS last_text
                FROM users u LEFT JOIN support_conversations c ON c.user_id=u.id WHERE u.id=? AND u.role='user'""",
                ("user" if admin else "admin", reader, uid)).fetchone()
            return dict(row) if row else None

    def inbox(self, reader, q="", page=1, page_size=20):
        with self.connect() as db:
            where = "(u.email LIKE ? OR json_extract(u.profile,'$.display_name') LIKE ?)"
            args = ["%"+q+"%"]*2
            total = db.execute("SELECT COUNT(*) FROM support_conversations c JOIN users u ON c.user_id=u.id WHERE "+where, args).fetchone()[0]
            ids = [r[0] for r in db.execute("SELECT c.user_id FROM support_conversations c JOIN users u ON c.user_id=u.id WHERE "+where+" ORDER BY c.updated_at DESC LIMIT ? OFFSET ?", (*args,page_size,(page-1)*page_size))]
        return dict(items=[self.conversation(uid, reader, True) for uid in ids], total=total, page=page, page_size=page_size)

    def messages(self, uid, before=None, limit=40):
        with self.connect() as db:
            rows = db.execute("SELECT id,author_id,author_role,text,created_at FROM support_messages WHERE user_id=? AND id<? ORDER BY id DESC LIMIT ?", (uid,before or 9223372036854775807,limit+1)).fetchall()
            more = len(rows)>limit
            items = []
            for row in reversed(rows[:limit]):
                item = dict(row)
                item.pop("author_id")
                item["images"] = [dict(r) for r in db.execute("SELECT id,filename,size,width,height FROM support_images WHERE message_id=?", (item["id"],))]
                item["files"] = [dict(r) for r in db.execute("SELECT id,filename,size FROM support_attachments WHERE message_id=?", (item["id"],))]
                items.append(item)
        return dict(items=items, has_more=more, before=items[0]["id"] if items else None)

    def existing(self, author, request_id):
        with self.connect() as db:
            row = db.execute("SELECT id,user_id FROM support_messages WHERE author_id=? AND request_id=?", (author,request_id)).fetchone()
            return dict(row) if row else None

    def send(self, uid, author, role, text, request_id, images, files=()):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Check again inside the transaction for concurrent retries.
            row = db.execute("SELECT id,user_id FROM support_messages WHERE author_id=? AND request_id=?", (author,request_id)).fetchone()
            if row:
                return dict(row), False
            db.execute("INSERT INTO support_conversations VALUES (?,'open',?) ON CONFLICT(user_id) DO UPDATE SET updated_at=excluded.updated_at,status=CASE WHEN ?='user' THEN 'open' ELSE support_conversations.status END", (uid,now,role))
            mid = db.execute("INSERT INTO support_messages(user_id,author_id,author_role,text,created_at,request_id) VALUES (?,?,?,?,?,?)", (uid,author,role,text,now,request_id)).lastrowid
            for img in images:
                db.execute("INSERT INTO support_images VALUES (?,?,?,?,?,?,?)", (img["id"],mid,uid,img["filename"],img["size"],img["width"],img["height"]))
            for file in files:
                db.execute("INSERT INTO support_attachments VALUES (?,?,?,?,?)", (file["id"],mid,uid,file["filename"],file["size"]))
        return dict(id=mid,user_id=uid), True

    def read(self, uid, reader, last_id):
        with self.connect() as db:
            latest = db.execute("SELECT COALESCE(MAX(id),0) FROM support_messages WHERE user_id=?", (uid,)).fetchone()[0]
            if last_id > latest:
                raise ValueError("已读位置无效")
            db.execute("INSERT INTO support_reads VALUES (?,?,?) ON CONFLICT(user_id,reader_id) DO UPDATE SET last_id=MAX(last_id,excluded.last_id)", (uid,reader,last_id))

    def status(self, uid, status):
        with self.connect() as db:
            db.execute("UPDATE support_conversations SET status=?,updated_at=? WHERE user_id=?", (status,datetime.now(timezone.utc).isoformat(),uid))

    def notifications(self, reader, admin=False):
        with self.connect() as db:
            scope = "" if admin else " AND m.user_id=?"
            args = ["user" if admin else "admin",reader]+([] if admin else [reader])
            unread = db.execute("""SELECT COUNT(*) FROM support_messages m WHERE m.author_role=?
                AND m.id>COALESCE((SELECT last_id FROM support_reads WHERE user_id=m.user_id AND reader_id=?),0)"""+scope, args).fetchone()[0]
            incoming = db.execute("SELECT COALESCE(MAX(id),0) FROM support_messages m WHERE m.author_role=?"+scope,
                                  ["user" if admin else "admin"]+([] if admin else [reader])).fetchone()[0]
            row = db.execute("SELECT COALESCE(MAX(id),0) FROM support_messages m WHERE 1=1"+scope, [] if admin else [reader]).fetchone()
            # Include status updates so inboxes refresh even without a new message.
            revision = db.execute("SELECT COALESCE(MAX(updated_at),'') FROM support_conversations"+("" if admin else " WHERE user_id=?"), [] if admin else [reader]).fetchone()[0]
        return dict(unread=unread,last_message_id=row[0],last_incoming_id=incoming,revision=revision)

    def image(self, image_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM support_images WHERE id=?", (image_id,)).fetchone()
            return dict(row) if row else None

    def attachment(self, file_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM support_attachments WHERE id=?", (file_id,)).fetchone()
            return dict(row) if row else None
