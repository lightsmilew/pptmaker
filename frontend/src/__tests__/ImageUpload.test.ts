import { afterEach, expect, it, vi } from 'vitest';
import { prepareImageUpload } from '@/lib/imageUpload';
import { studioTitles, adminTitles, publicTitle } from '@/lib/pageTitles';
import { api, setSessionCsrf } from '@/api/client';
import { supportApi } from '@/api/supportClient';

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function canvas(size = 100, width = 4000, height = 3000) {
  const close = vi.fn(), drawImage = vi.fn();
  vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue({width,height,close}));
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({drawImage} as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function(callback, type) { callback(new Blob(['x'.repeat(size)], {type})); });
  return {close,drawImage};
}
it('compresses reference images at high quality, scales without distortion and reuses retry preparation', async () => {
  const {close,drawImage} = canvas(); const file = new File(['x'.repeat(2000)], 'reference.png', {type:'image/png'});
  const result = await prepareImageUpload(file, 'reference');
  expect(result.name).toBe('reference.webp'); expect(result.size).toBe(100);
  expect(drawImage.mock.calls[0].slice(1)).toEqual([0,0,3200,2400]);
  expect(HTMLCanvasElement.prototype.toBlob).toHaveBeenCalledWith(expect.any(Function),'image/webp',.94);
  expect(await prepareImageUpload(file, 'reference')).toBe(result); expect(close).toHaveBeenCalledTimes(1);
});
it('uses a smaller support bound and never replaces an image with a larger encoding', async () => {
  const {drawImage} = canvas(2000); const file = new File(['x'.repeat(1000)],'shot.png',{type:'image/png'});
  expect(await prepareImageUpload(file,'support')).toBe(file);
  expect(drawImage.mock.calls[0].slice(1)).toEqual([0,0,2400,1800]);
});
it('keeps non-image files intact and falls back when bitmap decoding is unavailable', async () => {
  vi.stubGlobal('createImageBitmap', undefined);
  const text = new File(['notes'],'notes.txt'); const image = new File(['png'],'shot.png');
  expect(await prepareImageUpload(text,'support')).toBe(text);
  expect(await prepareImageUpload(image,'reference')).toBe(image);
});
it('rejects excessive pixels and releases decoded memory', async () => {
  const {close} = canvas(100,8000,4000);
  await expect(prepareImageUpload(new File(['image'],'large.png'),'support')).rejects.toThrow('1600万像素');
  expect(close).toHaveBeenCalledTimes(1);
});
it('gives every public, studio and admin page an English browser title', () => {
  for (const title of [...Object.values(studioTitles),...Object.values(adminTitles),publicTitle(false),publicTitle(true)]) {
    expect(title).not.toMatch(/[\u3400-\u9fff]/); expect(title.length).toBeGreaterThan(5);
  }
});
it.each(['reference','support'] as const)('does not transmit a %s image after an account switch during compression', async purpose => {
  const {close} = canvas(); let finish:(value:unknown)=>void = () => {};
  vi.stubGlobal('createImageBitmap',vi.fn().mockReturnValue(new Promise(resolve=>{ finish=resolve; })));
  const fetch = vi.fn(); vi.stubGlobal('fetch',fetch); setSessionCsrf('start-'+purpose);
  const file=new File(['x'.repeat(2000)],'private.png',{type:'image/png'});
  const sending=purpose==='reference' ? api.uploadAndParse(file) : supportApi().send('','',[file],'image-request-0001');
  setSessionCsrf('changed-'+purpose); finish({width:3000,height:2000,close});
  await expect(sending).rejects.toThrow(/账号已/); expect(fetch).not.toHaveBeenCalled();
});
