"""Audited, read-only administrator access to user presentation artifacts."""
from pathlib import Path
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from .admin import require_admin
from .workspace import project_summary, preview_url
from ..config import settings
from ..storage.memory import memory_store
from ..storage.auth_repository import AuthRepository
from ..storage.admin_repository import AdminRepository

router = APIRouter(prefix="/api/v1/admin/generations", tags=["Administration"])


def presentation(pid):
    project = memory_store.get_project(pid)
    owner = AuthRepository().user((project or {}).get("owner_id"))
    if not re.fullmatch(r"proj_[a-zA-Z0-9_-]+", pid) or not project or not owner or owner["role"] != "user":
        raise HTTPException(404, "演示不存在")
    return project, owner


def image_path(project, page):
    url = preview_url((page.get("preview") or {}).get("image_path"))
    if not url:
        return None
    root = (Path(settings.storage_path) / "previews" / project["id"]).resolve()
    path = (Path(settings.storage_path) / url.removeprefix("/storage/")).resolve()
    return path if path.is_relative_to(root) and path.suffix.lower() == ".png" and path.is_file() else None


@router.get("/{pid}")
async def detail(pid: str, current=Depends(require_admin)):
    project, owner = presentation(pid)
    summary = project_summary(project)
    pages = [dict(page_id=p["page_id"], title=(p.get("content") or {}).get("title") or p.get("title", ""),
                  status=p.get("status"), content=p.get("content") or {},
                  preview_url=f"/api/v1/admin/generations/{pid}/preview/{p['page_id']}" if image_path(project, p) else None)
             for p in project.get("pages") or []]
    AdminRepository().record("admin", current["user_id"], "presentation.viewed", pid)
    return dict(**{**summary, "preview_url": None, "download_url": f"/api/v1/admin/generations/{pid}/download" if summary["download_url"] else None},
                email=owner["email"], spec=project.get("spec") or {}, pages=pages,
                style_selection=project.get("style_selection"))


@router.api_route("/{pid}/preview/{page_id}", methods=["GET", "HEAD"])
async def preview(pid: str, page_id: str, current=Depends(require_admin)):
    project, _ = presentation(pid)
    page = next((p for p in project.get("pages") or [] if p.get("page_id") == page_id), {})
    path = image_path(project, page)
    if not path:
        raise HTTPException(404, "预览尚未生成")
    return FileResponse(path, media_type="image/png")


@router.api_route("/{pid}/download", methods=["GET", "HEAD"])
async def download(pid: str, request: Request, current=Depends(require_admin)):
    project, _ = presentation(pid)
    if not project_summary(project)["download_url"]:
        raise HTTPException(404, "演示尚未完成导出")
    if request.method == "GET":
        AdminRepository().record("admin", current["user_id"], "presentation.downloaded", pid)
    return FileResponse(Path(settings.storage_path) / (pid+".pptx"), filename="Folio-"+pid+".pptx",
                        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
