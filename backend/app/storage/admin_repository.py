"""Membership policy and content-free, durable administration records."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from .account_repository import database_path

DEFAULT_PLANS = [
    ("basic", "普通会员", 50000, 20, 1, "适合日常表达与轻量创作"),
    ("plus", "Folio Plus", 150000, 35, 2, "为经常创作的人多留一些空间"),
    ("pro", "Folio Pro", 500000, 50, 3, "适合完整提案与密集创作"),
    ("studio", "Folio Studio", 2000000, 50, 6, "为高频制作与工作室而设"),
]


class AdminRepository:
    def __init__(self, path=None):
        self.path = path or database_path()
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS membership_plans (
                    tier TEXT PRIMARY KEY, name TEXT NOT NULL, monthly_output_limit INTEGER NOT NULL,
                    max_pages INTEGER NOT NULL, concurrency INTEGER NOT NULL, description TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS activity_records (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, category TEXT NOT NULL,
                    actor_id TEXT, action TEXT NOT NULL, target_id TEXT, detail TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS activity_date ON activity_records(category,created_at);
                CREATE TABLE IF NOT EXISTS login_records (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, user_id TEXT, email TEXT NOT NULL,
                    scope TEXT NOT NULL, success INTEGER NOT NULL, ip TEXT NOT NULL, user_agent TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS login_date ON login_records(created_at);
            """)
            db.executemany("INSERT OR IGNORE INTO membership_plans VALUES (?,?,?,?,?,?)", DEFAULT_PLANS)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def plans(self):
        with self.connect() as db:
            items = {r["tier"]: dict(r) for r in db.execute("SELECT * FROM membership_plans")}
        return [items[tier] for tier, *_ in DEFAULT_PLANS]

    def plan(self, tier):
        return next((p for p in self.plans() if p["tier"] == tier), self.plans()[0])

    def update_plan(self, tier, changes, actor):
        with self.connect() as db:
            db.execute("UPDATE membership_plans SET name=?,monthly_output_limit=?,max_pages=?,concurrency=?,description=? WHERE tier=?",
                       (changes["name"], changes["monthly_output_limit"], changes["max_pages"], changes["concurrency"], changes["description"], tier))
        self.record("admin", actor, "membership.plan_updated", tier, {"fields": list(changes)})
        return self.plan(tier)

    def record(self, category, actor, action, target=None, detail=None):
        with self.connect() as db:
            db.execute("INSERT INTO activity_records VALUES (?,?,?,?,?,?,?)",
                       (uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(), category, actor, action,
                        target, json.dumps(detail or {}, ensure_ascii=False)))

    def login(self, request, email, scope, uid=None):
        with self.connect() as db:
            db.execute("INSERT INTO login_records VALUES (?,?,?,?,?,?,?,?)",
                       (uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(), uid, email, scope, bool(uid),
                        (request.client.host if request.client else "unknown")[:128], request.headers.get("user-agent", "")[:300]))


def enforce_pages(uid, count):
    if not uid:
        return
    from .account_repository import account_repository
    from fastapi import HTTPException
    maximum = account_repository(uid).membership()["limits"]["max_pages"]
    if count > maximum:
        raise HTTPException(403, f"当前会员最多支持 {maximum} 页，请减少页数或联系管理员调整权益")
