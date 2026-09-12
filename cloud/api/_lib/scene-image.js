// Keep the native decoder out of text/vector-only cold starts.
let decoder;
async function imageDecoder(){
 if(!decoder)decoder=import('sharp').then(({default:sharp})=>{sharp.cache({memory:8,files:0,items:16});sharp.concurrency(1);return sharp;});
 return decoder;
}

// Bound both compressed input and decoded pixels. Re-encoding strips metadata
// and rejects corrupt/unsupported images before embedding provider bytes in SVG.
export const MAX_SOURCE_SCENE_BYTES = 6_000_000;
export const MAX_SCENE_BYTES = 1_500_000;
export const MAX_SCENE_PIXELS = 16_000_000;
const fail = code => Object.assign(new Error(code === 'VISUAL_TOO_LARGE' ? 'The generated scene exceeds supported limits.' : 'The image provider returned an invalid scene.'), {code});

export async function normalizeScene(data) {
 if (typeof data !== 'string' || !data.length || data.length % 4 || !/^[A-Za-z0-9+/]+={0,2}$/.test(data)) throw fail('VISUAL_BAD_RESPONSE');
 if (data.length > Math.ceil(MAX_SOURCE_SCENE_BYTES / 3) * 4) throw fail('VISUAL_TOO_LARGE');
 const input = Buffer.from(data, 'base64');
 if (input.length > MAX_SOURCE_SCENE_BYTES) throw fail('VISUAL_TOO_LARGE');
 // Do not permit SVG/PDF/vector decoders or arbitrary plugin formats.
 const png = input.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]));
 const jpeg = input[0] === 255 && input[1] === 216 && input[2] === 255;
 const webp = input.subarray(0,4).toString() === 'RIFF' && input.subarray(8,12).toString() === 'WEBP';
 if (!png && !jpeg && !webp) throw fail('VISUAL_BAD_RESPONSE');
 try {
  const sharp=await imageDecoder();
  const pipeline = sharp(input, {limitInputPixels: MAX_SCENE_PIXELS, failOn: 'warning', sequentialRead: true}).timeout({seconds:5});
  const meta = await pipeline.metadata();
  if (!['png','jpeg','webp'].includes(meta.format) || !meta.width || !meta.height || (meta.pages || 1) !== 1) throw fail('VISUAL_BAD_RESPONSE');
  if (meta.width * meta.height > MAX_SCENE_PIXELS) throw fail('VISUAL_TOO_LARGE');
  const {data: output, info} = await pipeline.rotate().resize({width:1536,height:1536,fit:'inside',withoutEnlargement:true})
   .flatten({background:'#ffffff'}).jpeg({quality:82,chromaSubsampling:'4:2:0'}).toBuffer({resolveWithObject:true});
  if (output.length > MAX_SCENE_BYTES) throw fail('VISUAL_TOO_LARGE');
  return {mime:'image/jpeg',data:output.toString('base64'),bytes:output.length,width:info.width,height:info.height,normalized:true};
 } catch (error) {
  if (error.code === 'VISUAL_TOO_LARGE' || error.code === 'VISUAL_BAD_RESPONSE') throw error;
  throw fail(/pixel limit/i.test(error.message || '') ? 'VISUAL_TOO_LARGE' : 'VISUAL_BAD_RESPONSE');
 }
}
