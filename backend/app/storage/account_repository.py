"""A persistent local identity, entitlements, and content-free usage ledger."""

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path


class QuotaExceeded(ValueError):
    pass


def database_path():
    return os.getenv("FOLIO_DB") or os.getenv("PPTMAKER_DB", "storage/pptmaker.sqlite3")


class AccountRepository:
    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS local_account (id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS usage_ledger (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, project_id TEXT,
                    role TEXT, model TEXT, input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL, cached_tokens INTEGER NOT NULL,
                    reasoning_tokens INTEGER NOT NULL, success INTEGER NOT NULL,
                    cache_hit INTEGER NOT NULL, duration_ms REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS usage_date ON usage_ledger(created_at);
                CREATE TABLE IF NOT EXISTS output_reservations (id TEXT PRIMARY KEY, tokens INTEGER NOT NULL, created_at REAL NOT NULL);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def profile(self):
        with self.connect() as db:
            row = db.execute("SELECT data FROM local_account WHERE id='local'").fetchone()
            if row:
                return json.loads(row[0])
            profile = dict(account_id="local_"+uuid.uuid4().hex[:12], display_name="Folio 创作者",
                           email="", company="", occupation="", bio="", timezone="Asia/Shanghai",
                           created_at=datetime.now(timezone.utc).isoformat(),
                           preferences=dict(style="商务简约", page_count=8, language="zh-CN"))
            db.execute("INSERT OR IGNORE INTO local_account VALUES ('local',?)", (json.dumps(profile, ensure_ascii=False),))
            return json.loads(db.execute("SELECT data FROM local_account WHERE id='local'").fetchone()[0])

    def update_profile(self, patch):
        self.profile()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            profile = json.loads(db.execute("SELECT data FROM local_account WHERE id='local'").fetchone()[0])
            preferences = patch.pop("preferences", None)
            profile.update(patch)
            if preferences:
                profile["preferences"].update(preferences)
            profile["updated_at"] = datetime.now(timezone.utc).isoformat()
            db.execute("UPDATE local_account SET data=? WHERE id='local'", (json.dumps(profile, ensure_ascii=False),))
        return profile

    def membership(self):
        tier = os.getenv("FOLIO_MEMBERSHIP", "local").lower()
        tier = tier if tier in ("local", "plus") else "local"
        expires = os.getenv("FOLIO_MEMBERSHIP_EXPIRES_AT") or None
        active = True
        if expires:
            try:
                expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                active = expiry.replace(tzinfo=expiry.tzinfo or timezone.utc) > datetime.now(timezone.utc)
            except ValueError:
                active = False
        vip = tier == "plus" and active
        return dict(tier=tier, name="Folio Plus" if vip else "Folio Local", is_vip=vip,
                    status="active" if active else "expired", expires_at=expires,
                    managed_by="local_configuration", billing_mode="own_api_key",
                    features=["可编辑 PowerPoint 导出", "六种演示主题", "历史与收藏", "文档导入", "真实用量记录"],
                    limits=dict(max_pages=50, concurrency=max(1,min(8,int(os.getenv("PPT_CONCURRENCY","3"))))))

    def usage(self):
        now = datetime.now(timezone.utc)
        start = now.replace(day=1,hour=0,minute=0,second=0,microsecond=0).isoformat()
        next_month = now.replace(year=now.year+(now.month==12), month=now.month%12+1,day=1,
                                 hour=0,minute=0,second=0,microsecond=0).isoformat()
        with self.connect() as db:
            rows = db.execute("SELECT input_tokens,output_tokens,cached_tokens,reasoning_tokens,success,cache_hit,duration_ms FROM usage_ledger WHERE created_at>=?", (start,)).fetchall()
            daily = db.execute("SELECT substr(created_at,1,10),SUM(output_tokens),COUNT(*) FROM usage_ledger WHERE created_at>=? GROUP BY substr(created_at,1,10)",(start,)).fetchall()
            total_calls = db.execute("SELECT COUNT(*) FROM usage_ledger").fetchone()[0]
            db.execute("DELETE FROM output_reservations WHERE created_at<?", (time.time()-1800,))
            reserved = db.execute("SELECT COALESCE(SUM(tokens),0) FROM output_reservations").fetchone()[0]
        sums = [sum(row[i] for row in rows) for i in range(7)]
        limit = max(0,int(os.getenv("FOLIO_MONTHLY_OUTPUT_LIMIT", "0"))) or None
        return dict(period=now.strftime("%Y-%m"),period_start=start,resets_at=next_month,
                    calls=len(rows), lifetime_calls=total_calls, input_tokens=sums[0], output_tokens=sums[1],
                    cached_input_tokens=sums[2], reasoning_tokens=sums[3], successful_calls=sums[4],
                    response_cache_hits=sums[5], duration_ms=round(sums[6],1),
                    provider_cache_hit_rate=sums[2]/sums[0] if sums[0] else None,
                    daily=[dict(date=day,output_tokens=count,calls=calls) for day,count,calls in daily],
                    quota=dict(unit="output_tokens",limit=limit,used=sums[1],reserved=reserved,
                               remaining=max(0,limit-sums[1]-reserved) if limit is not None else None,
                               source="local_budget", is_unlimited=limit is None))

    def reserve_output(self, call_id, requested):
        """Reserve output capacity atomically so parallel calls cannot overspend it."""
        limit = max(0,int(os.getenv("FOLIO_MONTHLY_OUTPUT_LIMIT", "0")))
        if not limit:
            return requested
        month = datetime.now(timezone.utc).replace(day=1,hour=0,minute=0,second=0,microsecond=0).isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM output_reservations WHERE created_at<?", (time.time()-1800,))
            used = db.execute("SELECT COALESCE(SUM(output_tokens),0) FROM usage_ledger WHERE created_at>=?", (month,)).fetchone()[0]
            reserved = db.execute("SELECT COALESCE(SUM(tokens),0) FROM output_reservations").fetchone()[0]
            if limit-used-reserved < requested:
                raise QuotaExceeded("本月输出额度不足以完成当前步骤，请调整本地预算或等待下月重置")
            db.execute("INSERT INTO output_reservations VALUES (?,?,?)", (call_id,requested,time.time()))
        return requested

    def record_usage(self, record):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO usage_ledger VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (record["call_id"],record["created_at"],record.get("project_id"),record.get("role"),record.get("model"),
                        record.get("input_tokens",0) or 0,record.get("output_tokens",0) or 0,
                        record.get("cached_input_tokens",0) or 0,record.get("reasoning_tokens",0) or 0,
                        bool(record.get("success")),bool(record.get("response_cache_hit")),record.get("duration_ms",0)))
            db.execute("DELETE FROM output_reservations WHERE id=?", (record["call_id"],))


@lru_cache(maxsize=8)
def _repository(path):
    return AccountRepository(path)


def account_repository():
    return _repository(database_path())
