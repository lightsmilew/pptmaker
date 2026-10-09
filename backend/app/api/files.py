"""Private exports and slide previews; every request checks the project owner."""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from .auth import require_user, owned_project
from ..config import settings

router = APIRouter()


@router.api_route("/storage/{filename:path}", methods=["GET", "HEAD"])
async def private_file(filename: str, request: Request, user_id: str = Depends(require_user)):
    root = Path(settings.storage_path).resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or "\\" in filename:
        raise HTTPException(404, "文件不存在")
    parts = Path(filename).parts
    if len(parts) >= 3 and parts[0] == "previews":
        pid = parts[1]
        if path.suffix.lower() != ".png":
            raise HTTPException(404, "文件不存在")
    elif len(parts) == 1 and path.suffix.lower() == ".pptx":
        pid = path.stem
    else:
        raise HTTPException(404, "文件不存在")
    owned_project(pid, user_id)
    if not path.is_file():
        raise HTTPException(404, "文件不存在")
    if request.method == "GET" and path.suffix.lower() == ".pptx":
        from ..storage.admin_repository import AdminRepository
        AdminRepository().record("usage", user_id, "export.downloaded", pid)
    return FileResponse(path, headers={"Cache-Control":"private, no-store", "X-Content-Type-Options":"nosniff"})
