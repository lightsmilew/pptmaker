"""Licensed, offline thematic photos. Unknown IDs never become file paths."""
import io
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'photos'


@lru_cache(maxsize=1)
def photos():
    try:
        rows = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {row['id']: row for row in rows
            if Path(row['filename']).name == row['filename'] and (ROOT / row['filename']).is_file()}


def resolve(photo_id):
    return photos().get(photo_id) if isinstance(photo_id, str) else None


def planner_catalog():
    return '\n'.join(f"{pid}: {row.get('caption') or row['title'][:100]}（{row['category_name']}）"
                     for pid, row in photos().items())


def assign_images(outline, enabled):
    """Only sparse narrative pages get photos; duplicates/unknown IDs degrade safely."""
    budget = max(1, (len(outline) + 1) // 2)
    used = set()
    for item in outline:
        pid = item.get('image_id')
        eligible = (enabled and item.get('page_type') in {'cover', 'content', 'conclusion', 'thankyou'}
                    and len(item.get('key_points', [])) <= 4
                    and str(item.get('suggest_layout') or '').lower() not in {'comparison', 'timeline', 'two_column', '对比', '流程'}
                    and len(used) < budget and isinstance(pid, str) and pid not in used and resolve(pid))
        item['image_id'] = pid if eligible else None
        if eligible:
            used.add(pid)
    return outline


def crop_photo(photo_id, width, height):
    from PIL import Image, ImageOps
    row = resolve(photo_id)
    if not row:
        return None
    try:
        with Image.open(ROOT / row['filename']) as source:
            return ImageOps.fit(source.convert('RGB'), (max(1, int(width)), max(1, int(height))),
                                method=Image.Resampling.LANCZOS, centering=(.5, .5))
    except (OSError, ValueError):
        return None


def picture_stream(photo_id, width, height):
    image = crop_photo(photo_id, round(width * 120), round(height * 120))
    if image is None:
        return None
    stream = io.BytesIO()
    image.save(stream, 'JPEG', quality=92)
    stream.seek(0)
    return stream


def credit(photo_id):
    row = resolve(photo_id)
    if not row:
        return ''
    return (f"主题配图（示意，不作为事实或数据依据）：{row['title']}\n"
            f"作者：{row['author']}\n来源：{row['source_url']}\n"
            f"许可：{row['license']} · {row['license_url']}\n"
            "处理：居中裁剪与缩放。图片及其裁剪版本遵循上述许可。")
