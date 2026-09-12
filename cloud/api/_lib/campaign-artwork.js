import {generateScene} from './visuals_ai.js';
import {HttpError} from './http.js';
import {validateDocument,renderDocument} from '../../public/canvas/model.js';
import sharp from 'sharp';

export const ART_FORMATS=Object.freeze([
 {name:'hero_banner.svg',canvas:'canvas_hero.json',format:'landscape',width:1200,height:630},
 {name:'banner_instagram_square.svg',canvas:'canvas_square.json',format:'square',width:1080,height:1080},
 {name:'banner_fb_story.svg',canvas:'canvas_story.json',format:'story',width:1080,height:1920},
]);
// At most three separately composed images; no implicit cross-provider retry.
export async function campaignArtwork(input,plan,{deadline,signal}={}){
 const refs=input.reference_consent?[input.product_image,input.logo].filter(Boolean):[];
 const controller=new AbortController();
 const shared=AbortSignal.any([controller.signal,signal].filter(Boolean));
 const jobs=ART_FORMATS.map(async f=>{
  const remaining=Math.min(45000,deadline-Date.now());
  if(remaining<=0)throw new HttpError(503,'Image generation deadline reached. No basic design was substituted.','EXECUTION_DEADLINE');
  const result=await generateScene({...input,artwork_mode:'campaign'}, {...plan,format:f.format,referenceImages:refs,timeoutMs:remaining,signal:shared});
  // Portable source is deliberately bounded; this is web artwork, not a 4K master.
  let bytes;
  for(const quality of [85,75,65,55]){
   bytes=await sharp(Buffer.from(result.data,'base64'),{limitInputPixels:16000000}).resize({width:1440,height:1440,fit:'inside',withoutEnlargement:true}).jpeg({quality}).toBuffer();
   if(bytes.length<=220000)break;
  }
  if(bytes.length>220000)throw new HttpError(413,'Artwork exceeds portable-source limits. No basic design was substituted.','VISUAL_TOO_LARGE');
  const d={format:'brandforge-canvas',version:1,name:`${input.product} — ${f.format}`.slice(0,80).replace(/[\uD800-\uDBFF]$/,''),width:f.width,height:f.height,background:input.secondary||'#101820',watermark:!!input.watermark,sections:{strategy:'',copy:'',seo:''},layers:[{id:'ai-artwork',type:'image',x:0,y:0,width:f.width,height:f.height,rotation:0,opacity:1,fill:'#ffffff',src:'data:image/jpeg;base64,'+bytes.toString('base64'),fit:'contain',anchor:'xMidYMid'}]};
  validateDocument(d);
  return {format:f,document:d,provider:result.provider,model:result.model};
 });
 try{return await Promise.all(jobs);}catch(e){controller.abort();await Promise.allSettled(jobs);throw e;}
}
export function artworkFiles(artwork,sections){
 return artwork.flatMap(({format:f,document:d})=>{
  d.sections=Object.fromEntries(['strategy','copy','seo'].map(k=>[k,String(sections[k]||'').slice(0,20000)]));validateDocument(d);
  return [{name:f.name,content:renderDocument(d)},{name:f.canvas,content:JSON.stringify(d)}];
 });
}
