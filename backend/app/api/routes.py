"""Folio REST endpoints: creation, paginated history, uploads, call diagnostics.

Project detail, metadata, and local account endpoints live in workspace.py.
Workflow operations use the bidirectional WebSocket gateway.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, field_validator
from typing import Literal

from ..api.websocket import WorkflowRunner


router = APIRouter(prefix="/api/v1")


@router.get("/llm/usage")
async def llm_usage(project_id: Optional[str] = None) -> Dict[str, Any]:
    """Actual provider token counts and call latency; no source content."""
    from ..llm.telemetry import usage_snapshot
    return usage_snapshot(project_id)


class CreateProjectRequest(BaseModel):
    spec: Optional[Dict[str, Any]] = None
    user_input: Optional[str] = ""
    uploaded_files: Optional[list] = None

    @field_validator("spec")
    @classmethod
    def validate_page_count(cls, value):
        if value and value.get("page_count") is not None:
            count = value["page_count"]
            if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 50:
                raise ValueError("演示页数需为1至50的整数")
        return value


@router.post("/projects")
async def create_project(request: CreateProjectRequest) -> Dict[str, Any]:
    """Create a new PPT project. Returns the initial project snapshot."""
    return WorkflowRunner.create_project(
        spec=request.spec,
        user_input=request.user_input or "",
        uploaded_files=request.uploaded_files or [],
    )

@router.get("/projects")
async def list_projects(q: str = "",status: Literal["all","draft","completed","failed"] = "all",
                        favorite: Optional[bool] = None,archived: bool = False,
                        sort: Literal["updated","created","title"] = "updated",
                        page: int = 1,page_size: int = 12) -> Dict[str, Any]:
    """Paginated metadata; full content is available through GET /projects/{id}."""
    from .workspace import list_project_summaries
    if not 1 <= page_size <= 50 or page < 1:
        raise HTTPException(422,"分页范围无效")
    return list_project_summaries(q[:200],status,favorite,archived,sort,page,page_size)


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
async def upload_and_parse(file: UploadFile = File(...)) -> Dict[str, Any]:
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
        text = _extract_text(content, file.filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "文件无法解析，请确认文件未损坏；扫描 PDF 需要先转成可读取的文本") from exc
    return {
        "filename": file.filename,
        "content": text,
        "content_preview": text[:500],
    }
