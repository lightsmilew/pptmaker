"""Document parser tools."""

import os
from typing import Dict, Any, Optional
from pathlib import Path


class DocumentParser:
    """Parse various document formats for PPT content extraction."""

    SUPPORTED_FORMATS = [".pdf", ".docx", ".doc", ".txt", ".md"]

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a document and extract structured content.

        Returns:
            Dict with keys: title, sections, content
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {ext}")

        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            return self._parse_docx(file_path)
        elif ext in [".txt", ".md"]:
            return self._parse_text(file_path)
        else:
            raise ValueError(f"Cannot parse: {file_path}")

    def _parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """Parse PDF document."""
        try:
            import PyPDF2

            content = []
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content.append(text.strip())

            return self._extract_structure("\n\n".join(content))
        except ImportError:
            # Fallback to text extraction
            return self._parse_text(file_path.replace(".pdf", ".txt"))

    def _parse_docx(self, file_path: str) -> Dict[str, Any]:
        """Parse Word document."""
        try:
            from docx import Document

            doc = Document(file_path)
            content = []

            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    content.append(text)

            return self._extract_structure("\n\n".join(content))
        except ImportError:
            raise ImportError("python-docx is required to parse Word documents")

    def _parse_text(self, file_path: str) -> Dict[str, Any]:
        """Parse plain text or Markdown."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return self._extract_structure(content)

    def _extract_structure(self, content: str) -> Dict[str, Any]:
        """Extract structure from raw text content."""
        lines = content.split("\n")
        title = ""
        sections = []
        current_section = {"title": "", "content": []}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # First non-empty line is usually the title
            if not title:
                title = line
                continue

            # Detect section headers (various formats)
            if self._is_header(line):
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"title": line, "content": []}
            else:
                current_section["content"].append(line)

        if current_section["content"]:
            sections.append(current_section)

        return {
            "title": title,
            "sections": sections,
            "content": content,
            "outline": [s["title"] for s in sections if s["title"]],
        }

    def _is_header(self, line: str) -> bool:
        """Detect if a line is a section header."""
        # Markdown headers
        if line.startswith("#"):
            return True

        # Numbered headers like "1. Section"
        if len(line) < 50 and line[0].isdigit() and "." in line[:5]:
            return True

        # All caps or short lines ending with colon
        if len(line) < 40 and line.isupper():
            return True
        if line.endswith("：") or line.endswith(":"):
            return True

        return False


class PPTOpener:
    """Open and analyze existing PPT files."""

    def open(self, file_path: str) -> Dict[str, Any]:
        """
        Open an existing PPT and extract structure.

        Returns:
            Dict with slides, themes, and structure info
        """
        try:
            from pptx import Presentation
        except ImportError:
            return {"error": "python-pptx is required"}

        prs = Presentation(file_path)

        slides = []
        for i, slide in enumerate(prs.slides):
            slide_content = {
                "index": i,
                "title": "",
                "shapes": [],
                "text_content": [],
            }

            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text = shape.text.strip()
                    if text:
                        slide_content["text_content"].append(text)
                        if not slide_content["title"] and len(text) < 100:
                            slide_content["title"] = text

            slides.append(slide_content)

        return {
            "slide_count": len(prs.slides),
            "slide_width": prs.slide_width.inches,
            "slide_height": prs.slide_height.inches,
            "slides": slides,
        }
