import {createHash} from 'node:crypto';
import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,UUID,dbCheck,HttpError} from '../http.js';
import {rateLimit} from '../limit.js';
import {boundedJson} from '../payload.js';
import {validatePortable,PORTABLE_NOTICE} from '../../../public/portable-pack.js';
async function handle(req){
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{
  const sb=admin(),id=new URL(req.url).searchParams.get('id');if(id&&!UUID.test(id))throw new HttpError(404,'Archive not found');
  if(req.method==='GET'){
   if(!id)return json({archives:dbCheck(await sb.from('campaign_transfers').select('id,name,created_at').eq('user_id',user.id).order('created_at',{ascending:false}).limit(10)),notice:PORTABLE_NOTICE});
   const row=dbCheck(await sb.from('campaign_transfers').select('pack').eq('id',id).eq('user_id',user.id).maybeSingle());if(!row)throw new HttpError(404,'Archive not found');return boundedJson({pack:row.pack,notice:PORTABLE_NOTICE});
  }
  if(req.method==='DELETE'){if(!id)throw new HttpError(400,'Choose an archive');dbCheck(await sb.from('campaign_transfers').delete().eq('id',id).eq('user_id',user.id));return json({ok:true});}
  if(req.method!=='POST')throw new HttpError(405,'Method not allowed');
  if(!await rateLimit('archive-import',user.id,30,3600))throw new HttpError(429,'Import safety limit reached');
  const b=await readJson(req,3100000);if(b.consent!==true||!UUID.test(b.request_id||''))throw new HttpError(400,'Confirm permission to upload and provide a request ID');
  let pack;try{pack=await validatePortable(b.pack);}catch(e){throw new HttpError(400,e.message);}
  const r=dbCheck(await sb.rpc('save_campaign_transfer',{p_uid:user.id,p_request:b.request_id,p_hash:createHash('sha256').update(JSON.stringify(pack)).digest('hex'),p_pack:pack}));
  if(!r.ok)throw new HttpError(409,'Archive not saved: '+r.code,r.code);
  return json({...r,notice:PORTABLE_NOTICE});
 }catch(e){return json({error:e.status?e.message:'Archive operation could not be confirmed. Retry the unchanged import.',code:e.code},e.status||503);}
}
export default serve(handle);
