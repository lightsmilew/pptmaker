/** Clipboard files may be exposed through files or items, depending on the browser. */
export function transferFiles(data: Pick<DataTransfer, 'files' | 'items'>): File[] {
  const files = Array.from(data.files || []);
  if (files.length) return files;
  return Array.from(data.items || []).filter(item => item.kind === 'file')
    .map(item => item.getAsFile()).filter((file): file is File => file !== null);
}

export const referenceAccept = '.pdf,.docx,.pptx,.md,.markdown,.txt,.csv,.png,.jpg,.jpeg,.webp';
export const isReference = (file: File) => /\.(pdf|docx|pptx|md|markdown|txt|csv|png|jpe?g|webp)$/i.test(file.name);
export const isPreviewImage = (file: File) => ['image/png','image/jpeg','image/webp'].includes(file.type)
  || /\.(png|jpe?g|webp)$/i.test(file.name);
