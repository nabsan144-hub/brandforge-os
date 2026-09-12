import {describe,it,expect} from 'vitest';
import sharp from 'sharp';
import {randomBytes} from 'node:crypto';
import {normalizeScene,MAX_SOURCE_SCENE_BYTES,MAX_SCENE_BYTES} from '../api/_lib/scene-image.js';
const encoded = bytes => bytes.toString('base64');
describe('untrusted image normalization',()=>{
 it('compresses a real high-entropy PNG above the old limit before embedding',async()=>{
  const image=await sharp(randomBytes(1200*800*3),{raw:{width:1200,height:800,channels:3}}).png().toBuffer();
  expect(image.length).toBeGreaterThan(MAX_SCENE_BYTES);
  const result=await normalizeScene(encoded(image));
  expect(result).toMatchObject({mime:'image/jpeg',width:1200,height:800,normalized:true});
  expect(result.bytes).toBeLessThanOrEqual(MAX_SCENE_BYTES);
  const metadata=await sharp(Buffer.from(result.data,'base64')).metadata();expect(metadata.format).toBe('jpeg');
 });
 it('strips metadata and honors orientation without enlarging a small source',async()=>{
  const image=await sharp({create:{width:80,height:40,channels:3,background:'#aabbcc'}}).jpeg().withMetadata({orientation:6}).toBuffer();
  const result=await normalizeScene(encoded(image));expect(result.width).toBe(40);expect(result.height).toBe(80);
  const metadata=await sharp(Buffer.from(result.data,'base64')).metadata();expect(metadata.exif).toBeUndefined();expect(metadata.orientation).toBeUndefined();
 });
 it('bounds decoded dimensions and does not crop the subject',async()=>{
  const image=await sharp({create:{width:3000,height:2000,channels:3,background:'#334455'}}).png().toBuffer();
  expect(await normalizeScene(encoded(image))).toMatchObject({width:1536,height:1024});
 });
 it('rejects compressed pixel bombs',async()=>{
  const image=await sharp({create:{width:5000,height:4000,channels:3,background:'#000000'}}).png().toBuffer();
  await expect(normalizeScene(encoded(image))).rejects.toMatchObject({code:'VISUAL_TOO_LARGE'});
 });
 it('rejects source bytes over the independent input bound',async()=>{
  await expect(normalizeScene(encoded(Buffer.alloc(MAX_SOURCE_SCENE_BYTES+1)))).rejects.toMatchObject({code:'VISUAL_TOO_LARGE'});
 });
 it('rejects a raster signature attached to corrupt data',async()=>{
  await expect(normalizeScene(encoded(Buffer.from([137,80,78,71,13,10,26,10,0,0,0,0])))).rejects.toMatchObject({code:'VISUAL_BAD_RESPONSE'});
 });
 it.each(['<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a"/></svg>','%PDF-1.7','not an image'])('rejects nonraster decoders: %s',async value=>{
  await expect(normalizeScene(encoded(Buffer.from(value)))).rejects.toMatchObject({code:'VISUAL_BAD_RESPONSE'});
 });
});
