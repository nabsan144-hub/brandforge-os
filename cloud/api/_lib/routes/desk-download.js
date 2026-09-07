import {admin,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson} from '../http.js';
import {desktopDownload} from '../fulfillment.js';
async function handle(req){
 if(req.method!=='POST')return json({error:'Use the private download link in your email.'},405);
 try{const body=await readJson(req,4000),url=await desktopDownload(admin(),body.token);return json({url});}
 catch(e){return json({error:e.status?e.message:'Download is temporarily unavailable.'},e.status||503);}
}
const h=serve(handle);export default h;export const POST=h;
