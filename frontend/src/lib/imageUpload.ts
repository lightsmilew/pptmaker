import { isPreviewImage } from './fileTransfer';

type Purpose = 'reference' | 'support';
const prepared = new WeakMap<File, Partial<Record<Purpose, Promise<File>>>>();

/** Reduce transfer size; the server still validates every decoded image. */
export function prepareImageUpload(file: File, purpose: Purpose): Promise<File> {
  if (!isPreviewImage(file)) return Promise.resolve(file);
  const cached = prepared.get(file) || {};
  if (cached[purpose]) return cached[purpose]!;
  cached[purpose] = compress(file, purpose).catch(error => { delete cached[purpose]; throw error; });
  prepared.set(file, cached);
  return cached[purpose]!;
}

async function compress(file: File, purpose: Purpose): Promise<File> {
  const limit = (purpose === 'support' ? 5 : 10) * 1024 * 1024;
  if (file.size > limit) throw new Error(`图片最大${purpose === 'support' ? 5 : 10} MiB`);
  // Older browsers can send the original; server normalization is authoritative.
  if (typeof createImageBitmap !== 'function') return file;
  const bitmap = await createImageBitmap(file).catch(() => { throw new Error('图片无法读取，请选择有效的 PNG、JPEG 或 WebP'); });
  try {
    if (!bitmap.width || !bitmap.height || bitmap.width * bitmap.height > 16_000_000)
      throw new Error('图片最大1600万像素，请缩小图片后再添加');
    const maxEdge = purpose === 'reference' ? 3200 : 2400;
    const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext('2d');
    if (!context || typeof canvas.toBlob !== 'function') return file;
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    // WebP preserves transparent backgrounds; high-quality references retain OCR detail.
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/webp', purpose === 'reference' ? .94 : .84));
    if (!blob || blob.type !== 'image/webp' || blob.size >= file.size * .9) return file;
    return new File([blob], file.name.replace(/\.[^.]+$/, '') + '.webp', { type:blob.type, lastModified:file.lastModified });
  } finally { bitmap.close(); }
}
