"""Bounded local OCR for reference screenshots; no LLM or external image service."""
import io
import os
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


def extract_image_text(data: bytes) -> tuple[str, str]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {'PNG','JPEG','WEBP'} or source.width*source.height>16000000:
                    raise ValueError('图片支持 PNG、JPEG、WebP，最大1600万像素')
                source.load()
                rgba = ImageOps.exif_transpose(source).convert('RGBA')
                image = Image.new('RGB',rgba.size,'white')
                image.paste(rgba,mask=rgba.getchannel('A'))
                image.thumbnail((3200,3200))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('图片无法读取，请选择有效的 PNG、JPEG 或 WebP') from exc
    executable = os.environ.get('TESSERACT_CMD') or shutil.which('tesseract')
    if not executable and os.name == 'nt':
        candidate = Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Tesseract-OCR'/'tesseract.exe'
        if candidate.is_file():
            executable = str(candidate)
    if not executable:
        return '', '图片已添加，文字识别暂不可用，请补充制作要求。'
    with tempfile.TemporaryDirectory(prefix='folio-ocr-') as directory:
        path = Path(directory)/'reference.png'
        image.save(path,format='PNG')
        try:
            result = subprocess.run([executable,str(path),'stdout','-l','chi_sim+eng','--psm','11'],
                capture_output=True,timeout=30,check=False,env={**os.environ,'OMP_THREAD_LIMIT':'1'})
        except (OSError,subprocess.TimeoutExpired):
            return '', '图片已添加，文字识别未完成，请补充制作要求或换一张清晰截图。'
    if result.returncode:
        return '', '图片已添加，文字识别暂不可用，请补充制作要求。'
    text = result.stdout.decode('utf-8',errors='replace').strip()
    return text, '' if text else '图片已添加，未识别出文字，请补充制作要求。'
