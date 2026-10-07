"""Read/resume presentation history and manage the single local account."""

from copy import deepcopy
from pathlib import Path
from typing import Literal
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..config import settings
from ..storage.memory import memory_store
from ..storage.account_repository import account_repository

router = APIRouter(prefix="/api/v1")


def preview_url(path):
    path = str(path or "").replace("\\", "/")
    marker = path.find("/previews/")
    if marker >= 0:
        return "/storage" + path[marker:]
    return None


def project_summary(project):
    pages = project.get("pages") or []
    metadata = project.get("metadata") or {}
    spec = project.get("spec") or {}
    pid = project["id"]
    output = Path(settings.storage_path) / (pid+".pptx")
    ready = project.get("status") == "completed" and output.is_file()
    return dict(id=pid,title=spec.get("topic") or "未命名演示", audience=spec.get("audience") or "通用受众",
                style=spec.get("style") or "商务简约",status=project.get("status", "idle"),
                page_count=len(pages) or len(project.get("outline") or []) or spec.get("page_count", 8),
                completed_pages=sum(p.get("status") == "completed" for p in pages),
                favorite=bool(metadata.get("favorite")),archived=bool(metadata.get("archived")),
                tags=metadata.get("tags") or [],created_at=project.get("created_at"),updated_at=project.get("updated_at"),
                preview_url=next((url for p in pages if (url:=preview_url((p.get("preview") or {}).get("image_path")))),None),
                download_url=f"/storage/{pid}.pptx" if ready else None,
                file_size=output.stat().st_size if ready else None)


@router.get("/workspace")
async def workspace_overview():
    items = [project_summary(p) for p in memory_store.list_projects()]
    active = [p for p in items if not p["archived"]]
    return dict(name="我的工作空间",mode="local",stats=dict(total=len(active),
                completed=sum(p["status"]=="completed" for p in active),
                favorites=sum(p["favorite"] for p in active),
                in_progress=sum(p["status"] in ("parsing","planning","generating","reviewing","rendering") for p in active),
                archived=sum(p["archived"] for p in items),pages=sum(p["completed_pages"] for p in active),
                storage_bytes=sum(p["file_size"] or 0 for p in active)),
                recent=sorted(active,key=lambda p:p["updated_at"] or "",reverse=True)[:4])


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    project = memory_store.get_project(project_id)
    if not project:
        raise HTTPException(404,"演示文稿不存在")
    result = deepcopy(project)
    result["download_url"] = project_summary(project)["download_url"]
    return result


class MetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None,min_length=1,max_length=120)
    favorite: bool | None = None
    archived: bool | None = None
    tags: list[str] | None = Field(default=None,max_length=8)

    @field_validator("title")
    @classmethod
    def valid_title(cls,value):
        if value is not None and not value.strip():
            raise ValueError("标题不能为空")
        return value.strip() if value is not None else None

    @field_validator("tags")
    @classmethod
    def valid_tags(cls,value):
        if value is None:
            return value
        if any(not item.strip() or len(item.strip()) > 24 for item in value):
            raise ValueError("每个标签需为1至24个字符")
        return list(dict.fromkeys(item.strip() for item in value))


@router.patch("/projects/{project_id}")
async def update_project_metadata(project_id: str, patch: MetadataPatch):
    original = memory_store.get_project(project_id)
    if not original:
        raise HTTPException(404,"演示文稿不存在")
    project = deepcopy(original)
    changes = patch.model_dump(exclude_none=True)
    title = changes.pop("title",None)
    if title is not None:
        project.setdefault("spec",{})["topic"] = title
    project.setdefault("metadata",{}).update(changes)
    memory_store.update_project(project_id,project)
    return project_summary(project)


class PreferencePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: Literal["商务简约","学术简约","科技风","创意活泼","教育培训","金融专业"] | None = None
    page_count: int | None = Field(default=None,ge=1,le=50)
    language: Literal["zh-CN","en"] | None = None


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None,min_length=1,max_length=40)
    email: str | None = Field(default=None,max_length=254)
    company: str | None = Field(default=None,max_length=80)
    occupation: str | None = Field(default=None,max_length=60)
    bio: str | None = Field(default=None,max_length=200)
    timezone: Literal["Asia/Shanghai","UTC","Asia/Tokyo","Europe/London","America/New_York"] | None = None
    preferences: PreferencePatch | None = None

    @field_validator("email")
    @classmethod
    def valid_email(cls,value):
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",value):
            raise ValueError("请输入有效的联系邮箱")
        return value

    @field_validator("display_name")
    @classmethod
    def valid_name(cls,value):
        if value is not None and not value.strip():
            raise ValueError("称呼不能为空")
        return value.strip() if value is not None else None


def account_view():
    from ..llm.config import get_llm_config
    from urllib.parse import urlparse
    repository = account_repository()
    config = get_llm_config()
    provider = config.get_active_config()
    return dict(profile=repository.profile(),membership=repository.membership(),usage=repository.usage(),
                account=dict(mode="local",status="active",email_verified=False,
                             provider_host=urlparse(provider.base_url).hostname, model=provider.model_name,
                             provider_connected=config.is_configured(),authentication="local_workspace"))


@router.get("/account")
async def get_account():
    return account_view()


@router.patch("/account/profile")
async def update_profile(patch: ProfilePatch):
    account_repository().update_profile(patch.model_dump(exclude_none=True))
    return account_view()


@router.get("/account/usage")
async def get_account_usage():
    return account_repository().usage()


@router.get("/account/membership")
async def get_membership():
    return account_repository().membership()


def list_project_summaries(q="",status="all",favorite=None,archived=False,sort="updated",page=1,page_size=12):
    items = [project_summary(p) for p in memory_store.list_projects()]
    items = [p for p in items if p["archived"] == archived and (favorite is None or p["favorite"] == favorite)]
    if q:
        items = [p for p in items if q.casefold() in " ".join([p["title"],p["audience"],p["style"],*p["tags"]]).casefold()]
    if status == "draft":
        items = [p for p in items if p["status"] not in ("completed","failed")]
    elif status != "all":
        items = [p for p in items if p["status"] == status]
    key = "title" if sort == "title" else "created_at" if sort == "created" else "updated_at"
    items.sort(key=lambda p:(p.get(key) or "",p["id"]),reverse=sort!="title")
    return dict(projects=items[(page-1)*page_size:page*page_size],total=len(items),page=page,page_size=page_size)
