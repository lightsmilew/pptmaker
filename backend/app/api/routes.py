"""Folio REST endpoints: creation, paginated history, uploads, call diagnostics.

Project detail, metadata, and local account endpoints live in workspace.py.
Workflow operations use the bidirectional WebSocket gateway.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from .auth import require_user, owned_project
from pydantic import BaseModel, field_validator
from typing import Literal

from ..api.websocket import WorkflowRunner


router = APIRouter(prefix="/api/v1")


@router.get("/design/catalog")
async def design_catalog(user_id: str = Depends(require_user)):
    from ..tools.design_catalog import catalog
    return catalog()


@router.get("/llm/usage")
async def llm_usage(project_id: Optional[str] = None, user_id: str = Depends(require_user)) -> Dict[str, Any]:
    """Actual provider token counts and call latency; no source content."""
    from ..llm.telemetry import usage_snapshot
    if project_id:
        owned_project(project_id, user_id)
    return usage_snapshot(project_id, user_id)


class CreateProjectRequest(BaseModel):
    spec: Optional[Dict[str, Any]] = None
    user_input: Optional[str] = ""
    uploaded_files: Optional[list] = None

    @field_validator("spec")
    @classmethod
    def validate_page_count(cls, value):
        from ..contracts.project_input import validate_spec
        return validate_spec(value)


@router.post("/projects")
async def create_project(request: CreateProjectRequest, user_id: str = Depends(require_user)) -> Dict[str, Any]:
    """Create a new PPT project. Returns the initial project snapshot."""
    from ..storage.auth_repository import AuthRepository
    files = []
    seen_uploads = set()
    for item in request.uploaded_files or []:
        if not isinstance(item, dict) or not item.get("upload_id"):
            raise HTTPException(422, "请先添加参考文档")
        upload = AuthRepository().upload(user_id, item["upload_id"])
        if not upload:
            raise HTTPException(404, "参考文档不存在")
        if upload["upload_id"] in seen_uploads:
            continue
        seen_uploads.add(upload["upload_id"])
        files.append(upload)
    user_input = request.user_input or ""
    for upload in files:
        if upload["content"] and upload["content"] not in user_input:
            user_input += f'\n\n【文件内容 - {upload["filename"]}】\n{upload["content"]}'
    return WorkflowRunner.create_project(
        spec=request.spec,
        user_input=user_input,
        uploaded_files=files, owner_id=user_id,
    )

@router.get("/projects")
async def list_projects(q: str = "",status: Literal["all","draft","completed","failed"] = "all",
                        favorite: Optional[bool] = None,archived: bool = False,
                        sort: Literal["updated","created","title"] = "updated",
                        page: int = 1,page_size: int = 12,user_id: str = Depends(require_user)) -> Dict[str, Any]:
    """Paginated metadata; full content is available through GET /projects/{id}."""
    from .workspace import list_project_summaries
    if not 1 <= page_size <= 50 or page < 1:
        raise HTTPException(422,"分页范围无效")
    return list_project_summaries(q[:200],status,favorite,archived,sort,page,page_size,user_id)


# ==================== File Upload (single shot) ====================

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".markdown"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _extract_text(content: bytes, filename: Optional[str]) -> str:
    """Extract plain text from an uploaded file."""
    if not filename:
        return content.decode("utf-8", errors="ignore")

    lowered = filename.lower()
    if lowered.endswith((".md", ".markdown", ".txt")):
        return content.decode("utf-8", errors="ignore")

    if lowered.endswith(".docx"):
        try:
            from docx import Document
            import io

            doc = Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise HTTPException(status_code=500, detail="请安装 python-docx 库来解析 Word 文档")

    if lowered.endswith(".pdf"):
        try:
            import PyPDF2
            import io

            reader = PyPDF2.PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            raise HTTPException(status_code=500, detail="请安装 PyPDF2 库来解析 PDF 文档")

    return content.decode("utf-8", errors="ignore")


@router.post("/upload/parse")
async def upload_and_parse(file: UploadFile = File(...), user_id: str = Depends(require_user)) -> Dict[str, Any]:
    """Upload a file and return its extracted text content."""
    if file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {ext}。支持的格式: PDF, Word, Markdown, TXT",
            )

    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件过大，最大支持10MB")

    try:
        import asyncio
        text = await asyncio.to_thread(_extract_text, content, file.filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "文件无法解析，请确认文件未损坏；扫描 PDF 需要先转成可读取的文本") from exc
    if not text.strip():
        raise HTTPException(400, "未读取到文本，扫描 PDF 请先转换为文本")
    from pathlib import Path
    import uuid
    from ..config import settings
    from ..storage.auth_repository import AuthRepository
    filename = (file.filename or "document.txt").replace("\\", "/").split("/")[-1][:200]
    upload_id = "upload_" + uuid.uuid4().hex
    directory = Path(settings.storage_path) / "uploads" / user_id / upload_id
    directory.mkdir(parents=True, exist_ok=True)
    saved = directory / ("original" + os.path.splitext(filename)[1].lower())
    saved.write_bytes(content)
    AuthRepository().save_upload(user_id, filename, str(saved), text, len(content), upload_id)
    return {
        "upload_id": upload_id,
        "filename": filename,
        "content": text,
        "content_preview": text[:500],
        "size": len(content),
    }
