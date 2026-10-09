"""Separate administrator sessions and privileged server-side operations."""
import asyncio
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import Credentials, PasswordChange, check_origin, protect_auth
from .workspace import account_view
from ..storage.auth_repository import ADMIN_COOKIE, AuthRepository, password_hash
from ..storage.account_repository import account_repository
from ..storage.admin_repository import AdminRepository, DEFAULT_PLANS
from ..storage.memory import memory_store
from .. import admin_config

router = APIRouter(prefix="/api/v1/admin", tags=["Administration"])
config_lock = asyncio.Lock()
ADMIN_PATH = "/api/v1/admin"


async def require_admin(request: Request):
    session = AuthRepository().session(request.cookies.get(ADMIN_COOKIE))
    if not session or session["scope"] != "admin" or session["role"] != "admin":
        raise HTTPException(401, "请从管理入口登录")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        check_origin(request)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf"]):
            raise HTTPException(403, "管理会话验证失败，请刷新页面")
    return session


def admin_session(uid, response):
    token, csrf, duration = AuthRepository().create_session(uid, "admin")
    response.set_cookie(ADMIN_COOKIE, token, max_age=duration, httponly=True, samesite="strict",
                        secure=os.getenv("FOLIO_COOKIE_SECURE", "false").lower() == "true", path=ADMIN_PATH)
    return dict(account=account_view(uid), csrf_token=csrf)


class AdminCredentials(Credentials):
    # Login verifies stored bootstrap credentials; new passwords have a
    # separate policy enforced by the creation and password-change endpoints.
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
async def login(data: AdminCredentials, request: Request, response: Response):
    protect_auth(request, data.email)
    uid = await asyncio.to_thread(AuthRepository().authenticate, data.email, data.password, "admin")
    AdminRepository().login(request, data.email, "admin", uid)
    if not uid:
        raise HTTPException(401, "管理员账号或密码不正确")
    return admin_session(uid, response)


@router.get("/session")
async def session(current=Depends(require_admin)):
    return dict(account=account_view(current["user_id"]), csrf_token=current["csrf"])


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, current=Depends(require_admin)):
    AuthRepository().revoke(request.cookies[ADMIN_COOKIE])
    response.delete_cookie(ADMIN_COOKIE, path=ADMIN_PATH)


@router.post("/password")
async def change_password(data: PasswordChange, response: Response, current=Depends(require_admin)):
    if not await asyncio.to_thread(AuthRepository().change_password, current["user_id"], data.current_password, data.new_password):
        raise HTTPException(400, "当前密码不正确")
    AdminRepository().record("admin", current["user_id"], "admin.password_changed", current["user_id"])
    return admin_session(current["user_id"], response)


def current_month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def period_bounds(period):
    try:
        month = datetime.strptime(period, "%Y-%m").replace(tzinfo=timezone.utc)
        if month.strftime("%Y-%m") != period:
            raise ValueError()
        end = month.replace(year=month.year+(month.month == 12), month=month.month % 12+1)
    except ValueError:
        raise HTTPException(422, "月份格式应为 YYYY-MM")
    return month.isoformat(), end.isoformat()


@router.get("/overview")
async def overview(current=Depends(require_admin)):
    start, end = period_bounds(current_month())
    repo = AdminRepository()
    with repo.connect() as db:
        counts = dict(db.execute("SELECT status,COUNT(*) FROM users WHERE role='user' GROUP BY status").fetchall())
        usage = dict(db.execute("SELECT COUNT(*) AS calls, COALESCE(SUM(input_tokens),0) AS input_tokens, COALESCE(SUM(output_tokens),0) AS output_tokens, COALESCE(SUM(success=0),0) AS failures FROM usage_ledger WHERE created_at>=? AND created_at<?", (start, end)).fetchone())
        failed_logins = db.execute("SELECT COUNT(*) FROM login_records WHERE success=0 AND created_at>=?", (start,)).fetchone()[0]
        recent = [dict(r) for r in db.execute("SELECT a.*,u.email AS actor_email FROM activity_records a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.created_at DESC LIMIT 8")]
    projects = [p for p in memory_store.list_projects() if p.get("owner_id")]
    from ..llm.config import get_llm_config
    config = get_llm_config()
    return dict(period=current_month(), users=sum(counts.values()), active_users=counts.get("active", 0),
                disabled_users=counts.get("disabled", 0), projects=len(projects),
                completed=sum(p.get("status") == "completed" for p in projects),
                running=sum(p.get("status") in {"parsing","planning","generating","reviewing","rendering"} for p in projects),
                failed_logins=failed_logins, usage=usage, provider=config.provider, model=config.get_model_name(),
                provider_connected=config.is_configured(), recent=[{**r, "detail": json.loads(r["detail"])} for r in recent])


def user_view(row):
    profile = json.loads(row["profile"])
    repo = account_repository(row["id"])
    return dict(id=row["id"], email=row["email"], display_name=profile["display_name"], company=profile.get("company", ""),
                created_at=profile["created_at"], status=row["status"], role=row["role"], membership=repo.membership(),
                usage=repo.usage(), output_limit_override=row["output_limit"])


@router.get("/users")
async def users(q: str = Query("", max_length=200), status: Literal["all","active","disabled"] = "all",
                page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=50), current=Depends(require_admin)):
    clause = "role='user' AND (email LIKE ? OR json_extract(profile,'$.display_name') LIKE ?)"
    params = ["%"+q+"%"]*2
    if status != "all":
        clause += " AND status=?"
        params.append(status)
    with AuthRepository().connect() as db:
        count = db.execute("SELECT COUNT(*) FROM users WHERE "+clause, params).fetchone()[0]
        rows = db.execute("SELECT id,email,profile,membership,output_limit,status,role FROM users WHERE "+clause+" ORDER BY json_extract(profile,'$.created_at') DESC LIMIT ? OFFSET ?", (*params, page_size, (page-1)*page_size)).fetchall()
    return dict(items=[user_view(r) for r in rows], total=count, page=page, page_size=page_size)


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(None, min_length=1, max_length=40)
    status: Literal["active","disabled"] | None = None
    tier: Literal["basic","plus","pro","studio"] | None = None
    expires_at: str | None = None
    monthly_output_limit: int | None = Field(None, ge=0, le=1000000000)

    @field_validator("expires_at")
    @classmethod
    def valid_expiry(cls, value):
        if value is None:
            return value
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.replace(tzinfo=date.tzinfo or timezone.utc).isoformat()

    @field_validator("display_name")
    @classmethod
    def valid_name(cls, value):
        if value is not None and not value.strip():
            raise ValueError("称呼不能为空")
        return value.strip() if value else value


def ordinary_user(uid):
    user = AuthRepository().user(uid)
    if not user or user["role"] != "user":
        raise HTTPException(404, "用户账号不存在")
    return user


@router.patch("/users/{uid}")
async def update_user(uid: str, data: UserPatch, current=Depends(require_admin)):
    ordinary_user(uid)
    changes = data.model_dump(exclude_unset=True)
    if any(changes.get(k) is None for k in ("status","tier","display_name") if k in changes):
        raise HTTPException(422, "账号状态、等级和称呼不能为空")
    with AuthRepository().connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT profile,membership FROM users WHERE id=?", (uid,)).fetchone()
        profile, membership = json.loads(row["profile"]), json.loads(row["membership"])
        if "display_name" in changes:
            profile["display_name"] = changes["display_name"]
        membership.update({k: v for k, v in changes.items() if k in ("tier", "expires_at")})
        db.execute("UPDATE users SET profile=?,membership=? WHERE id=?", (json.dumps(profile, ensure_ascii=False), json.dumps(membership), uid))
        if "monthly_output_limit" in changes:
            db.execute("UPDATE users SET output_limit=? WHERE id=?", (changes["monthly_output_limit"], uid))
        if "status" in changes:
            db.execute("UPDATE users SET status=? WHERE id=?", (changes["status"], uid))
        if changes.get("status") == "disabled":
            db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    if changes.get("status") == "disabled":
        from .websocket import manager
        for pid, task in list(manager.workflow_tasks.items()):
            if (memory_store.get_project(pid) or {}).get("owner_id") == uid:
                task.cancel()
        await manager.close_user(uid)
    AdminRepository().record("admin", current["user_id"], "user.updated", uid, {"fields": list(changes)})
    with AuthRepository().connect() as db:
        return user_view(db.execute("SELECT id,email,profile,membership,output_limit,status,role FROM users WHERE id=?", (uid,)).fetchone())


@router.post("/users/{uid}/revoke-sessions", status_code=204)
async def revoke_sessions(uid: str, current=Depends(require_admin)):
    ordinary_user(uid)
    with AuthRepository().connect() as db:
        db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    from .websocket import manager
    await manager.close_user(uid)
    AdminRepository().record("admin", current["user_id"], "user.sessions_revoked", uid)


@router.post("/users/{uid}/reset-password")
async def reset_password(uid: str, current=Depends(require_admin)):
    ordinary_user(uid)
    password = secrets.token_urlsafe(24)
    hashed = await asyncio.to_thread(password_hash, password)
    with AuthRepository().connect() as db:
        db.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed, uid))
        db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    from .websocket import manager
    await manager.close_user(uid)
    AdminRepository().record("admin", current["user_id"], "user.password_reset", uid)
    return {"temporary_password": password}


class PlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=40)
    description: str = Field(max_length=120)
    monthly_output_limit: int = Field(ge=0, le=1000000000)
    max_pages: int = Field(ge=1, le=50)
    concurrency: int = Field(ge=1, le=8)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        if not value.strip():
            raise ValueError("等级名称不能为空")
        return value.strip()


@router.get("/memberships")
async def memberships(current=Depends(require_admin)):
    return {"items": AdminRepository().plans()}


@router.patch("/memberships/{tier}")
async def update_membership(tier: str, data: PlanPatch, current=Depends(require_admin)):
    if tier not in [p[0] for p in DEFAULT_PLANS]:
        raise HTTPException(404, "会员等级不存在")
    return AdminRepository().update_plan(tier, data.model_dump(), current["user_id"])


@router.get("/config")
async def configuration(current=Depends(require_admin)):
    return admin_config.config_view()


class ConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str = Field(min_length=64, max_length=64)
    changes: dict[str, str]


@router.patch("/config")
async def update_configuration(data: ConfigPatch, current=Depends(require_admin)):
    async with config_lock:
        from .websocket import manager
        if (any(not task.done() for task in manager.workflow_tasks.values()) or
                any(p.get("status") in {"parsing","planning","generating","reviewing","rendering"} for p in memory_store.list_projects())):
            raise HTTPException(409, "有演示正在制作，请完成后再修改模型配置")
        result = admin_config.update_environment(data.changes, data.revision)
        AdminRepository().record("admin", current["user_id"], "config.updated", detail={"fields": list(data.changes)})
        return result


@router.post("/provider/balance")
async def balance(current=Depends(require_admin)):
    from ..llm.config import get_llm_config
    config = get_llm_config()
    cfg = config.get_active_config()
    if config.provider != "openai" or urlparse(cfg.base_url).hostname != "api.deepseek.com":
        return {"supported": False, "available": None, "balances": [], "message": "当前供应商未提供可用的余额查询接口；应用额度可在账号列表中查看。"}
    if not cfg.api_key:
        raise HTTPException(400, "请先配置供应商 API Key")
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get("https://api.deepseek.com/user/balance", headers={"Authorization": "Bearer "+cfg.api_key})
            response.raise_for_status()
            result = response.json()
        if not isinstance(result["is_available"], bool):
            raise ValueError()
        balances = []
        for row in result["balance_infos"][:10]:
            if row["currency"] not in ("CNY", "USD"):
                raise ValueError()
            values = {key: str(Decimal(str(row[key]))) for key in ("total_balance", "granted_balance", "topped_up_balance")}
            if any(not Decimal(v).is_finite() for v in values.values()):
                raise ValueError()
            balances.append({"currency": row["currency"], **values})
    except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidOperation):
        raise HTTPException(502, "余额查询失败，请检查接口连接与密钥权限")
    AdminRepository().record("admin", current["user_id"], "provider.balance_queried")
    return {"supported": True, "available": result["is_available"], "balances": balances,
            "checked_at": datetime.now(timezone.utc).isoformat(), "message": "DeepSeek 供应商余额"}


@router.post("/provider/models")
async def provider_models(current=Depends(require_admin)):
    from ..llm.config import get_llm_config
    config = get_llm_config()
    cfg = config.get_active_config()
    if not cfg.api_key:
        raise HTTPException(400, "请先配置供应商 API Key")
    admin_config.validate({config.provider.upper()+"_BASE_URL": cfg.base_url})
    url = cfg.base_url.rstrip("/")+"/models"
    headers = {"Authorization": "Bearer "+cfg.api_key} if config.provider == "openai" else {"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01"}
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            result = response.json()
        models = sorted({str(row["id"])[:200] for row in result["data"][:200]})
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(502, "模型查询失败，此接口可能未开放模型目录")
    AdminRepository().record("admin", current["user_id"], "provider.models_queried")
    return {"models": models, "provider": config.provider, "checked_at": datetime.now(timezone.utc).isoformat()}


@router.get("/usage")
async def usage(period: str = "", current=Depends(require_admin)):
    period = period or current_month()
    start, end = period_bounds(period)
    with AdminRepository().connect() as db:
        summary = dict(db.execute("SELECT COUNT(*) AS calls,COALESCE(SUM(input_tokens),0) AS input_tokens,COALESCE(SUM(output_tokens),0) AS output_tokens,COALESCE(SUM(cached_tokens),0) AS cached_tokens,COALESCE(SUM(reasoning_tokens),0) AS reasoning_tokens,COALESCE(SUM(cache_hit),0) AS cache_hits,COALESCE(SUM(success=0),0) AS failures,COALESCE(SUM(usage_reported=1),0) AS reported_calls FROM usage_ledger WHERE created_at>=? AND created_at<?", (start, end)).fetchone())
        models = [dict(r) for r in db.execute("SELECT provider,model,COUNT(*) AS calls,SUM(input_tokens) AS input_tokens,SUM(output_tokens) AS output_tokens FROM usage_ledger WHERE created_at>=? AND created_at<? GROUP BY provider,model ORDER BY output_tokens DESC", (start, end))]
        daily = [dict(r) for r in db.execute("SELECT substr(created_at,1,10) AS date,COUNT(*) AS calls,SUM(output_tokens) AS output_tokens FROM usage_ledger WHERE created_at>=? AND created_at<? GROUP BY date ORDER BY date", (start, end))]
    return {"period": period, "summary": summary, "models": models, "daily": daily,
            "provider_cache_hit_rate": summary["cached_tokens"]/summary["input_tokens"] if summary["input_tokens"] else None}


@router.get("/records")
async def records(kind: Literal["login","usage","generation","admin","calls"] = "login", q: str = Query("", max_length=200),
                  page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50), current=Depends(require_admin)):
    repo = AdminRepository()
    with repo.connect() as db:
        if kind == "login":
            source, clause, columns = "login_records r", "(r.email LIKE ? OR r.ip LIKE ?)", "r.*"
        elif kind == "calls":
            source, clause, columns = "usage_ledger r LEFT JOIN users u ON u.id=r.user_id", "(COALESCE(u.email,'') LIKE ? OR COALESCE(r.model,'') LIKE ?)", "r.*,u.email"
        else:
            source, clause, columns = "activity_records r LEFT JOIN users u ON u.id=r.actor_id", "r.category=? AND (COALESCE(u.email,'') LIKE ? OR COALESCE(r.target_id,'') LIKE ? OR r.action LIKE ?)", "r.*,u.email"
        params = ["%"+q+"%"]*2 if kind in ("login","calls") else [kind]+["%"+q+"%"]*3
        total = db.execute("SELECT COUNT(*) FROM "+source+" WHERE "+clause, params).fetchone()[0]
        items = [dict(r) for r in db.execute("SELECT "+columns+" FROM "+source+" WHERE "+clause+" ORDER BY r.created_at DESC LIMIT ? OFFSET ?", (*params, page_size, (page-1)*page_size))]
    for item in items:
        if "detail" in item:
            item["detail"] = json.loads(item["detail"])
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/generations")
async def generations(q: str = Query("", max_length=200), status: str = "all", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50), current=Depends(require_admin)):
    with AuthRepository().connect() as db:
        emails = {r["id"]: r["email"] for r in db.execute("SELECT id,email FROM users")}
    items = [dict(id=p["id"], email=emails.get(p.get("owner_id"), ""), title=(p.get("spec") or {}).get("topic", "未命名演示"),
                  status=p.get("status", "idle"), pages=len(p.get("pages") or []), created_at=p.get("created_at"), updated_at=p.get("updated_at"))
             for p in memory_store.list_projects() if p.get("owner_id")]
    items = [i for i in items if (status == "all" or i["status"] == status) and q.casefold() in (i["title"]+i["email"]).casefold()]
    items.sort(key=lambda i: i["updated_at"] or "", reverse=True)
    return {"items": items[(page-1)*page_size:page*page_size], "total": len(items), "page": page, "page_size": page_size}
