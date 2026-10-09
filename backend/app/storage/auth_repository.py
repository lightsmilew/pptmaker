"""Server-owned identities and revocable opaque sessions, stored beside projects."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from .account_repository import database_path, AccountRepository

user_context = ContextVar("folio_user", default=None)
SESSION_COOKIE = "folio_session"
ADMIN_COOKIE = "folio_admin_session"


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(32)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3,
                            maxmem=64*1024*1024, dklen=64).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password, stored):
    _, salt, _ = stored.split("$")
    return hmac.compare_digest(password_hash(password, salt), stored)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class AuthRepository:
    def __init__(self, path=None):
        self.path = path or database_path()
        AccountRepository(self.path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                    profile TEXT NOT NULL, membership TEXT NOT NULL, output_limit INTEGER,
                    status TEXT NOT NULL DEFAULT 'active');
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf TEXT NOT NULL,
                    expires_at REAL NOT NULL, created_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS session_user ON sessions(user_id);
                CREATE TABLE IF NOT EXISTS auth_attempts (key TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS attempt_key ON auth_attempts(key, created_at);
                CREATE TABLE IF NOT EXISTS uploads (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, filename TEXT NOT NULL,
                    path TEXT NOT NULL, content TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT NOT NULL);
            """)
            db.execute("BEGIN IMMEDIATE")
            if "role" not in {r[1] for r in db.execute("PRAGMA table_info(users)")}:
                db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
            if "scope" not in {r[1] for r in db.execute("PRAGMA table_info(sessions)")}:
                db.execute("ALTER TABLE sessions ADD COLUMN scope TEXT NOT NULL DEFAULT 'user'")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def register(self, email, password, display_name, *, _role="user"):
        uid = "user_" + uuid.uuid4().hex
        profile = dict(account_id=uid, display_name=display_name, email=email, company="", occupation="",
                       bio="", timezone="Asia/Shanghai", created_at=datetime.now(timezone.utc).isoformat(),
                       preferences=dict(style="商务简约", page_count=8, language="zh-CN", layout_mode="auto", content_density="balanced"))
        hashed = password_hash(password)
        with self.connect() as db:
            db.execute("INSERT INTO users(id,email,password_hash,profile,membership,role) VALUES (?,?,?,?,?,?)",
                       (uid, email, hashed, json.dumps(profile, ensure_ascii=False), json.dumps({"tier":"basic"}), _role))
        return uid

    def create_admin(self, email, password, display_name="Folio 管理员"):
        """Create a distinct identity; a duplicate address fails without changing its owner."""
        return self.register(email, password, display_name, _role="admin")

    def authenticate(self, email, password, scope="user"):
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        # Spend the same password-hashing work for an unknown address.
        stored = row["password_hash"] if row else "scrypt$" + "00"*32 + "$" + "00"*64
        valid = verify_password(password, stored)
        return row["id"] if valid and row and row["status"] == "active" and row["role"] == scope else None

    def user(self, uid):
        with self.connect() as db:
            row = db.execute("SELECT id,email,status,role FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None

    def create_session(self, uid, scope="user"):
        user = self.user(uid)
        if not user or user["status"] != "active" or user["role"] != scope:
            raise ValueError("账号与会话入口不匹配")
        token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        duration = max(1, min(30, int(os.getenv("FOLIO_SESSION_DAYS", "7")))) * 86400
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (time.time(),))
            db.execute("INSERT INTO sessions(token_hash,user_id,csrf,expires_at,created_at,scope) VALUES (?,?,?,?,?,?)",
                       (token_hash(token), uid, csrf, time.time()+duration, time.time(), scope))
        return token, csrf, duration

    def session(self, token):
        if not token or len(token) > 256:
            return None
        with self.connect() as db:
            row = db.execute("SELECT s.*,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user_id "
                             "WHERE token_hash=? AND expires_at>? AND u.status='active'",
                             (token_hash(token), time.time())).fetchone()
        return dict(row) if row else None

    def revoke(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))

    def change_password(self, uid, current, new):
        with self.connect() as db:
            row = db.execute("SELECT password_hash FROM users WHERE id=?", (uid,)).fetchone()
            if not row or not verify_password(current, row[0]):
                return False
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash(new), uid))
            db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
        return True

    def throttle(self, key, limit):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM auth_attempts WHERE created_at<?", (time.time()-900,))
            count = db.execute("SELECT COUNT(*) FROM auth_attempts WHERE key=?", (key,)).fetchone()[0]
            if count >= limit:
                return False
            db.execute("INSERT INTO auth_attempts VALUES (?,?)", (key, time.time()))
        return True

    def save_upload(self, uid, filename, path, content, size, upload_id):
        with self.connect() as db:
            db.execute("INSERT INTO uploads VALUES (?,?,?,?,?,?,?)", (upload_id,uid,filename,path,content,size,
                       datetime.now(timezone.utc).isoformat()))

    def upload(self, uid, upload_id):
        with self.connect() as db:
            row = db.execute("SELECT id AS upload_id,filename,content,size FROM uploads WHERE id=? AND user_id=?",
                             (upload_id, uid)).fetchone()
        return dict(row) if row else None
