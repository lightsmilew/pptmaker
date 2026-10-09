"""Cookie authentication, CSRF validation and project ownership boundaries."""
import hmac
import os
import re
import sqlite3
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..storage.auth_repository import AuthRepository, SESSION_COOKIE

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def allowed_origins():
    return [s.strip().rstrip("/") for s in os.getenv("FOLIO_ALLOWED_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000").split(",") if s.strip()]


def check_origin(connection):
    origin = connection.headers.get("origin")
    if origin and origin.rstrip("/") not in allowed_origins():
        raise HTTPException(403, "请求来源不受信任")


async def require_session(request: Request):
    session = AuthRepository().session(request.cookies.get(SESSION_COOKIE))
    if not session:
        raise HTTPException(401, "请先登录 Folio")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        check_origin(request)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf"]):
            raise HTTPException(403, "会话验证失败，请刷新页面后重试")
    return session


async def require_user(session=Depends(require_session)):
    return session["user_id"]


def owned_project(pid, uid):
    from ..storage.memory import memory_store
    project = memory_store.get_project(pid)
    if not project or project.get("owner_id") != uid:
        raise HTTPException(404, "演示文稿不存在")
    return project


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        value = value.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("请输入有效的邮箱")
        return value


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=40)

    @field_validator("display_name")
    @classmethod
    def name_valid(cls, value):
        if not value.strip():
            raise ValueError("请输入你的称呼")
        return value.strip()


def protect_auth(request, email):
    check_origin(request)
    if request.headers.get("x-folio-request") != "1":
        raise HTTPException(403, "请从 Folio 页面提交")
    repo = AuthRepository()
    host = request.client.host if request.client else "unknown"
    if not repo.throttle("ip:"+host, 60) or not repo.throttle("email:"+email, 20):
        raise HTTPException(429, "尝试次数较多，请在 15 分钟后重试")


def session_response(uid, response):
    from .workspace import account_view
    token, csrf, duration = AuthRepository().create_session(uid)
    response.set_cookie(SESSION_COOKIE, token, max_age=duration, httponly=True, samesite="strict",
                        secure=os.getenv("FOLIO_COOKIE_SECURE", "false").lower() == "true", path="/")
    response.headers["Cache-Control"] = "no-store"
    return dict(account=account_view(uid), csrf_token=csrf)


@router.post("/register", status_code=201)
async def register(data: Registration, request: Request, response: Response):
    protect_auth(request, data.email)
    try:
        # CPU-bound password derivation stays off the async request loop.
        import asyncio
        uid = await asyncio.to_thread(AuthRepository().register, data.email, data.password, data.display_name)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "此邮箱已注册，请登录")
    return session_response(uid, response)


@router.post("/login")
async def login(data: Credentials, request: Request, response: Response):
    import asyncio
    protect_auth(request, data.email)
    uid = await asyncio.to_thread(AuthRepository().authenticate, data.email, data.password)
    if not uid:
        raise HTTPException(401, "邮箱或密码不正确")
    return session_response(uid, response)


@router.get("/session")
async def get_session(response: Response, session=Depends(require_session)):
    from .workspace import account_view
    response.headers["Cache-Control"] = "no-store"
    return dict(account=account_view(session["user_id"]), csrf_token=session["csrf"])


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, session=Depends(require_session)):
    from .websocket import manager
    AuthRepository().revoke(request.cookies[SESSION_COOKIE])
    await manager.close_session(session["token_hash"])
    response.delete_cookie(SESSION_COOKIE, path="/")


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


@router.post("/password")
async def change_password(data: PasswordChange, response: Response, session=Depends(require_session)):
    import asyncio
    from .websocket import manager
    valid = await asyncio.to_thread(AuthRepository().change_password, session["user_id"],
                                    data.current_password, data.new_password)
    if not valid:
        raise HTTPException(400, "当前密码不正确")
    await manager.close_user(session["user_id"])
    return session_response(session["user_id"], response)
