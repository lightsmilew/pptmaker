"""
REST routes for PPTMaker.

Only the endpoints that can't reasonably live on the WebSocket remain here:
- POST /api/v1/projects            Create a new project (one-shot RPC, no state stream)
- GET  /storage/{filename}         Static file download for generated PPTX / previews

All other project operations (parse, plan, generate, review, render, update)
are exposed over the WebSocket gateway — see app.api.websocket.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from ..api.websocket import WorkflowRunner


router = APIRouter(prefix="/api/v1")


class CreateProjectRequest(BaseModel):
    spec: Optional[Dict[str, Any]] = None
    user_input: Optional[str] = ""
    uploaded_files: Optional[list] = None


@router.post("/projects")
async def create_project(request: CreateProjectRequest) -> Dict[str, Any]:
    """Create a new PPT project. Returns the initial project snapshot."""
    return WorkflowRunner.create_project(
        spec=request.spec,
        user_input=request.user_input or "",
        uploaded_files=request.uploaded_files or [],
    )


# ==================== File Upload (single shot) ====================

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".md", ".txt", ".markdown"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _extract_text(content: bytes, filename: Optional[str]) -> str:
    """Extract plain text from an uploaded file."""
    if not filename:
        return content.decode("utf-8", errors="ignore")

    lowered = filename.lower()
    if lowered.endswith((".md", ".markdown", ".txt")):
        return content.decode("utf-8", errors="ignore")

    if lowered.endswith((".docx", ".doc")):
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

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件过大，最大支持10MB")

    text = _extract_text(content, file.filename)
    return {
        "filename": file.filename,
        "content": text,
        "content_preview": text[:500],
    }
