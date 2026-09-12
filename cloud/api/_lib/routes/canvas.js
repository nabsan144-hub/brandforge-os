import {createHash} from 'node:crypto';
import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {UUID,readJson,dbCheck,HttpError} from '../http.js';
import {rateLimit} from '../limit.js';
import {validateDocument} from '../../../public/canvas/model.js';
async function read(sb,uid,id,version){
 const c=dbCheck(await sb.from('canvas_projects').select('*').eq('id',id).eq('user_id',uid).maybeSingle());if(!c)throw new HttpError(404,'Canvas not found');
 if(version&&version!==c.revision){const v=dbCheck(await sb.from('canvas_versions').select('document').eq('project_id',id).eq('revision',version).maybeSingle());if(!v)throw new HttpError(409,'This replayed version is no longer retained. Open the current project; no new write occurred.');c.document=v.document;c.revision=version;}
 const versions=dbCheck(await sb.from('canvas_versions').select('revision').eq('project_id',id).order('revision',{ascending:false}));return {id:c.id,revision:c.revision,document:c.document,versions:versions.map(v=>v.revision)};
}
async function handler(req){
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{
  const sb=admin(),id=new URL(req.url).searchParams.get('id');if(id&&!UUID.test(id))throw new HttpError(400,'Invalid project');
  if(req.method==='GET')return json(id?await read(sb,user.id,id):{attribution_required:!['pro','agency'].includes(dbCheck(await sb.from('profiles').select('plan').eq('id',user.id).single()).plan),projects:dbCheck(await sb.from('canvas_projects').select('id,name,revision').eq('user_id',user.id).order('updated_at',{ascending:false}).limit(10))});
  if(req.method==='DELETE'){if(!id)throw new HttpError(400,'Choose a project');dbCheck(await sb.from('canvas_projects').delete().eq('id',id).eq('user_id',user.id));return json({ok:true});}
  if(req.method!=='POST')throw new HttpError(405,'Method not allowed');
  if(!await rateLimit('canvas-save',user.id,60,3600))throw new HttpError(429,'Canvas save limit reached. Export locally and retry later.');
  const b=await readJson(req,1050000);
  if(Object.keys(b).some(k=>!['id','revision','request_id','document','restore','consent'].includes(k))||b.consent!==true||!UUID.test(b.request_id||'')||(b.id!==null&&b.id!==undefined&&!UUID.test(b.id))||!Number.isInteger(b.revision)||b.revision<0||(b.restore!==undefined&&(!Number.isInteger(b.restore)||b.restore<1))||(b.restore!==undefined&&b.document!==undefined))throw new HttpError(400,'Provide consent, expected revision and supported fields.');
  if(b.restore===undefined){try{validateDocument(b.document);}catch(e){throw new HttpError(400,e.message);}
   // Decode supplied rasters before storing; no vector/plugin formats or provider calls.
   const {default:sharp}=await import('sharp');
   for(const l of b.document.layers.filter(l=>l.type==='image')){try{const raw=Buffer.from(l.src.split(',')[1],'base64');const image=sharp(raw,{limitInputPixels:4000000,failOn:'warning'}).timeout({seconds:3});const meta=await image.metadata();if(!['png','jpeg'].includes(meta.format)||(meta.pages||1)!==1)throw Error('format');await image.resize(1,1).raw().toBuffer();}catch{throw new HttpError(400,'An image could not be safely decoded. Replace it with a prepared PNG/JPEG.');}}
  }
  const hash=createHash('sha256').update(JSON.stringify(b)).digest('hex');
  const r=dbCheck(await sb.rpc('save_canvas',{p_uid:user.id,p_id:b.id||null,p_revision:b.revision,p_request:b.request_id,p_hash:hash,p_document:b.document||null,p_restore:b.restore??null}));
  if(!r.ok)throw new HttpError(r.code==='NOT_FOUND'?404:409,'Canvas not saved: '+r.code,r.code);
  return json({...await read(sb,user.id,r.id,r.revision),replayed:!!r.replayed});
 }catch(e){return json({error:e.status?e.message:'Canvas save could not be confirmed. Retry unchanged.',code:e.code},e.status||503);}
}
export default serve(handler);
