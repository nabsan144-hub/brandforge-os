import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,clean,safeHex,safeLogo,safeUrl,UUID,HttpError,dbCheck} from '../http.js';
import {pickLang} from '../i18n.js';
import {rateLimit} from '../limit.js';
async function handle(req){
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);const sb=admin();
 try{
  if(!req.method||req.method==='GET'){
   const id=new URL(req.url,'https://brandforge.local').searchParams.get('id');
   if(id){if(!UUID.test(id))throw new HttpError(404,'Brand not found');const brand=dbCheck(await sb.from('brand_profiles').select('*').eq('id',id).eq('user_id',user.id).maybeSingle());if(!brand)throw new HttpError(404,'Brand not found');return json(brand);}
   return json({brands:dbCheck(await sb.from('brand_profiles').select('id,name,updated_at').eq('user_id',user.id).order('updated_at',{ascending:false}).limit(100))||[]});
  }
  if(!['POST','DELETE'].includes(req.method))throw new HttpError(405,'Method not allowed');
  if(!await rateLimit('brand-save',user.id,100,86400))throw new HttpError(429,'Daily brand edit limit reached.');
  const b=await readJson(req,150000);
  if(req.method==='DELETE'){
   if(!UUID.test(b.id||''))throw new HttpError(400,'Invalid brand ID.');
   dbCheck(await sb.from('brand_profiles').delete().eq('id',b.id).eq('user_id',user.id));return json({ok:true});
  }
  const name=clean(b.name||b.product_name,80);if(!name)throw new HttpError(400,'Name this brand.');
  const data={};for(const [k,n] of Object.entries({product_name:80,industry:80,audience:120,benefits:500,tone:120,proof:500,avoided:500,offer:200,cta:40}))data[k]=clean(b[k],n);
  Object.assign(data,{primary_color:safeHex(b.primary_color),secondary_color:safeHex(b.secondary_color,'#0F172A'),lang:pickLang(b.lang),url:safeUrl(b.url),logo:safeLogo(b.logo)});
  if(b.id&&!UUID.test(b.id))throw new HttpError(400,'Invalid brand ID.');
  const id=dbCheck(await sb.rpc('save_brand',{p_uid:user.id,p_id:b.id||null,p_name:name,p_data:data}),'Could not save brand. Check the 100-brand workspace limit.');
  return json({id,name,data});
 }catch(e){return json({error:e.status?e.message:'Could not save brand.'},e.status||503);}
}
const h=serve(handle);export default h;export const GET=h;export const POST=h;export const DELETE=h;
