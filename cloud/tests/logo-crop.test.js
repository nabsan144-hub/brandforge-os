import {it,expect,vi,afterEach} from 'vitest';
import sharp from 'sharp';
import {logoDimensions,normalizedLogo} from '../public/workspace-tools.js';
import {correctionLayout,normalizeCorrectionLayout} from '../api/_lib/vector-corrections.js';
afterEach(()=>vi.unstubAllGlobals());
it('reads PNG/JPEG/WebP dimensions before browser logo decoding',async()=>{
 for(const format of ['png','jpeg','webp']){
  const bytes=await sharp({create:{width:80,height:40,channels:3,background:'#287656'}}).toFormat(format).toBuffer();
  expect(logoDimensions(bytes)).toEqual({width:80,height:40});
 }
});
it('rejects a pixel-bomb logo before creating an object URL or image',async()=>{
 const b=Buffer.alloc(24);Buffer.from([137,80,78,71,13,10,26,10]).copy(b);b.writeUInt32BE(100000,16);b.writeUInt32BE(100000,20);
 const create=vi.fn();vi.stubGlobal('URL',{createObjectURL:create});
 await expect(normalizedLogo({type:'image/png',size:b.length,arrayBuffer:async()=>b})).rejects.toThrow('4 million');expect(create).not.toHaveBeenCalled();
});
it('removes PNG metadata while preserving alpha in a validated replacement logo',async()=>{
 const png=await sharp({create:{width:40,height:40,channels:4,background:{r:1,g:2,b:3,alpha:.5}}}).withMetadata().png().toBuffer();
 const layout=correctionLayout({logo:'data:image/png;base64,'+png.toString('base64'),logo_rights:true},{});
 const normalized=await normalizeCorrectionLayout(layout);const meta=await sharp(Buffer.from(normalized.logo.split(',')[1],'base64')).metadata();
 expect(meta.hasAlpha).toBe(true);expect(meta.icc).toBeUndefined();expect(meta.exif).toBeUndefined();
});
