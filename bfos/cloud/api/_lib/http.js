import {PNG} from 'pngjs';
export class HttpError extends Error {
  constructor(status, message, code = 'REQUEST_FAILED') { super(message); this.status = status; this.code = code; }
}
export async function readBody(req,maxBytes=32000){
 const declared=Number(req.headers?.get?.('content-length')||0);
 if(Number.isFinite(declared)&&declared>maxBytes)throw new HttpError(413,'Request is too large.');
 let raw;
 if(req.body?.getReader){
  const reader=req.body.getReader(),chunks=[];let size=0;
  for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;
   if(size>maxBytes){await reader.cancel();throw new HttpError(413,'Request is too large.');}
   chunks.push(Buffer.from(value));
  }
  raw=Buffer.concat(chunks).toString('utf8');
 }else raw=typeof req.text==='function'?await req.text():JSON.stringify(await req.json());
 if(Buffer.byteLength(raw,'utf8')>maxBytes)throw new HttpError(413,'Request is too large.');
 return raw;
}
export async function readJson(req,maxBytes=32000){
 let value;
 try{value=JSON.parse(await readBody(req,maxBytes));}catch(e){if(e instanceof HttpError)throw e;throw new HttpError(400,'Invalid JSON.');}
 if(!value||typeof value!=='object'||Array.isArray(value))throw new HttpError(400,'Expected a JSON object.');
 return value;
}
export function clean(value, max = 500) { return String(value ?? '').replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, '').replace(/<\/?[A-Za-z][^<>]*>/g, ' ').replace(/<(?:script|style|iframe|object|embed|img|svg|a|form|input|meta|link)\b[^>]*$/gi, ' ').trim().slice(0, max); }
export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export function safeHex(value, fallback = '#E8B54A') { return /^#[0-9a-f]{6}$/i.test(String(value)) ? value : fallback; }
export function safeUrl(value){
 if(!value)return '';
 try{const u=new URL(value);if(u.protocol==='https:'&&!u.username&&!u.password&&u.href.length<=500)return u.href;}catch{}
 throw new HttpError(400,'Destination must be an HTTPS URL of at most 500 characters, without embedded credentials.');
}
export function safeLogo(value) {
  if (!value) return '';
  if (typeof value !== 'string' || !/^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(value)) throw new HttpError(400,'Logo must be a PNG image.');
  const b=Buffer.from(value.split(',')[1],'base64');
  if (b.length>64000 || b.length<33 || b.subarray(0,8).toString('hex')!=='89504e470d0a1a0a' || !b.readUInt32BE(16) || !b.readUInt32BE(20) || b[28]!==0 || b.readUInt32BE(16)>512 || b.readUInt32BE(20)>512) throw new HttpError(400,'Logo must be a PNG under 64 KB and 512 pixels.');
  try{
    let offset=8;
    while(offset+12<=b.length){const length=b.readUInt32BE(offset),type=b.subarray(offset+4,offset+8).toString();if(offset+length+12>b.length||(type==='IHDR'&&offset!==8))throw new Error('Invalid PNG chunks');offset+=length+12;if(type==='IEND')break;}
    PNG.sync.read(b,{checkCRC:true});
  }catch{throw new HttpError(400,'Logo is not a complete supported PNG. Use the upload control to convert it.');}
  return value;
}
export function dbCheck(result, message = 'Could not save. Please retry.') { if (result?.error) throw new HttpError(503, message, result.error.code || 'DATABASE_UNAVAILABLE'); return result?.data; }
