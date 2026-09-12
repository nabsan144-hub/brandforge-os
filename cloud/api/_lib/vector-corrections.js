import {createHash} from 'node:crypto';
import {photoInput,normalizeProductPhoto} from './product-photo.js';
import {bannerSvg,validateVisualText} from './visuals.js';
import {vectorQuality} from '../../public/vector-quality.js';
import {PNG} from 'pngjs';
import {clean,safeUrl,safeLogo,HttpError} from './http.js';
const KEYS={headline:160,subheadline:240,offer:100,cta:60,destination:500};
export function correctionFields(value){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!Object.hasOwn(KEYS,k)&&!['benefits','proof'].includes(k)))throw new HttpError(400,'Supply only the supported visual text fields.');
 const fields={};for(const [key,max]of Object.entries(KEYS)){
  if(typeof value[key]!=='string'||value[key].length>max)throw new HttpError(400,`Visual ${key} is missing or too long.`);
  fields[key]=key==='destination'?safeUrl(value[key]):clean(value[key],max);
 }
 for(const key of ['benefits','proof'])if(Object.hasOwn(value,key)){if(typeof value[key]!=='string'||value[key].length>500)throw new HttpError(400,'Visual '+key+' is too long.');fields[key]=clean(value[key],500);}
 if(!fields.headline||!fields.cta)throw new HttpError(400,'Headline and CTA cannot be empty.');
 validateVisualText({product:fields.headline,benefits:fields.subheadline,offer:fields.offer,cta:fields.cta});
 return fields;
}
const decode=s=>s.replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
const normal=s=>s.replace(/\s+/g,' ').trim().toLocaleUpperCase();
function fieldReport(svg,fields){
 const quality=vectorQuality([{name:'banner.svg',content:svg}])[0];
 if(quality)return Object.fromEntries(Object.entries(fields).map(([k,v])=>{
  if(k==='benefits'){const items=quality.fields.filter(f=>f.field.startsWith('benefit_'));return [k,!v?'empty':items.length&&items.every(f=>f.status==='included')?'included':items.some(f=>f.status==='included')?'check_fit':'omitted'];}
  return [k,k==='destination'?'metadata_only':!v?'empty':quality.fields.find(f=>f.field===k)?.status==='included'?'included':'omitted'];
 }));
 const rendered=new Map();
 for(const m of svg.matchAll(/aria-label="([^"]*)" data-text="([^"]*)"/g)){
  const key=normal(decode(m[2]));rendered.set(key,[...(rendered.get(key)||[]),decode(m[1])]);
 }
 return Object.fromEntries(Object.entries(fields).map(([k,v])=>{
  if(k==='destination')return [k,'metadata_only'];if(!v)return [k,'empty'];
  const lines=rendered.get(normal(v));return [k,!lines?'omitted':normal(lines.join(' '))===normal(v)?'included':'check_fit'];
 }));
}
export function redrawVectors(campaign,fields,layout={}){
 const r=structuredClone(campaign.visual_recipe);
 if(campaign.asset_bundle_id||![1,2].includes(r?.schema)||(campaign.visual_status?.mode==='ai'&&r?.schema!==2)||!Array.isArray(r.formats)||!r.formats.length||r.formats.length>22)throw new HttpError(409,'This pack has no supported saved rendering recipe. Private files must be verified before redraw; historical artwork is not reconstructed by guessing.','VISUAL_CORRECTION_UNSUPPORTED');
 if(!Array.isArray(campaign.files)||campaign.files.some(f=>typeof f.content!=='string'))throw new HttpError(409,'The original visual sources are unavailable.');
 let scene='';
 if(r.schema===2){
  const hero=campaign.files.find(f=>f.name==='hero_banner.svg')?.content||'';
  const sources=[...hero.matchAll(/href="(data:image\/jpeg;base64,[A-Za-z0-9+/]+={0,2})"/g)].map(m=>m[1]).filter(uri=>uri.length<=2_000_100&&createHash('sha256').update(uri).digest('hex')===r.scene_sha256);
  if(sources.length!==1)throw new HttpError(409,'The saved hero scene failed verification. No artwork was replaced.','SCENE_SOURCE_INVALID');
  scene=sources[0];
 }
 if(fields.benefits!==undefined)r.common.benefits=fields.benefits.split(/[,;\n]/).map(s=>s.trim()).filter(Boolean);
 if(fields.proof!==undefined)r.common.proof=fields.proof;
 for(const key of ['logo_position','photo_fit','photo_anchor','product_image','logo'])if(layout[key]!==undefined)r.common[key]=layout[key];
 const originals=new Map(campaign.files.map(f=>[f.name,f]));const updated=new Map(),report=[];
 for(const format of r.formats){
  if(!/^(hero_banner|banner_[a-z0-9_]+)\.svg$/.test(format.name)||!originals.has(format.name)||![format.width,format.height].every(v=>Number.isInteger(v)&&v>=50&&v<=5000)||updated.has(format.name))throw new HttpError(409,'The saved visual format recipe is invalid.');
  const content=bannerSvg({...r.common,...fields,benefits:r.common.benefits,...format,scene:format.name==='hero_banner.svg'?scene:'',explicitVisualFields:true,watermark:r.common.watermark===true});
  updated.set(format.name,{name:format.name,content});report.push({name:format.name,fields:fieldReport(content,fields)});
 }
 // Approved source logos can change; generated concept logos remain historical.
 // No user-supplied dimensions,
 // style, colors, watermark switch, external image or rendering recipe accepted.
 const files=campaign.files.map(f=>{if(f.name==='brand_guidelines.md'&&layout.logo)f={...f,content:f.content.replace(/\n\nCurrent approved logo:[^\n]*/g,'')+'\n\nCurrent approved logo: approved_logo.png is the supplied logo used by this visual revision. Generated concept logos, if included, are separate historical drafts.'};if(f.name==='approved_logo.png'&&layout.logo)return {...f,encoding:'base64',content:layout.logo.split(',')[1]};if(f.name==='approved_product_photo.jpg'&&layout.product_image)return {...f,content:layout.product_image.split(',')[1]};if(f.name==='brand_guidelines.md'&&layout.photo_fit)return {...f,content:f.content.replace('Its full edges are contained in supported formats; small formats may omit it.','The photograph may be contained or cropped according to the selected fit; small formats may omit it.').replace(/\n\nActive photo fit:[^\n]*/g,'')+'\n\nActive photo fit: '+layout.photo_fit+'. Inspect product accuracy and edges before publishing.'};return updated.get(f.name)||f;});
 if(layout.logo&&!files.some(f=>f.name==='approved_logo.png'))files.push({name:'approved_logo.png',encoding:'base64',content:layout.logo.split(',')[1]});
 return {files,fields,recipe:r,report};
}

export function correctionLayout(value={},campaign){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!['logo_position','photo_fit','photo_anchor','product_image','product_image_rights','logo','logo_rights'].includes(k)))throw new HttpError(400,'Unsupported layout control.');
 const layout={};
 if(campaign.visual_status?.mode==='ai'&&(['photo_fit','photo_anchor','product_image'].some(k=>value[k]!==undefined)||value.logo_position==='right'))throw new HttpError(409,'Scene artwork stays fixed. Only text and left/hidden brand logos can be corrected.');
 if(value.logo!==undefined){if(value.logo_rights!==true)throw new HttpError(400,'Confirm permission to use the replacement logo.');if(typeof value.logo!=='string'||value.logo.length>86000||!value.logo)throw new HttpError(400,'Choose a prepared PNG logo under 64 KB.');layout.logo=safeLogo(value.logo);}
 if(value.photo_anchor!==undefined){if(!['top-left','top','top-right','left','center','right','bottom-left','bottom','bottom-right'].includes(value.photo_anchor)||campaign.visual_recipe?.common?.style!=='product-v1')throw new HttpError(400,'Choose a supported Product-first crop anchor.');layout.photo_anchor=value.photo_anchor;}

 if(value.logo_position!==undefined){if(!['left','right','hidden'].includes(value.logo_position))throw new HttpError(400,'Choose a supported logo position.');if(value.logo_position==='right'&&!['product-v1','offer-v1','service-v1','evidence-v1'].includes(campaign.visual_recipe?.common?.style))throw new HttpError(409,'Right-aligned logos require a new composition family.');layout.logo_position=value.logo_position;}
 if(value.photo_fit!==undefined){if(!['contain','crop'].includes(value.photo_fit)||campaign.visual_recipe?.common?.style!=='product-v1')throw new HttpError(400,'Photo fit applies to Product-first only.');layout.photo_fit=value.photo_fit;}
 if(value.product_image!==undefined){layout.product_image=photoInput({...value,style:campaign.visual_recipe?.common?.style});if(!layout.product_image)throw new HttpError(400,'Choose a replacement product photograph.');}
 return layout;
}
export async function normalizeCorrectionLayout(layout){
 const result={...layout};
 if(layout.product_image)result.product_image=await normalizeProductPhoto(layout.product_image);
 if(layout.logo){
  const bytes=PNG.sync.write(PNG.sync.read(Buffer.from(layout.logo.split(',')[1],'base64'),{checkCRC:true}));
  if(bytes.length>64000)throw new HttpError(400,'The normalized logo is too large. Choose a simpler logo.');
  result.logo=safeLogo('data:image/png;base64,'+bytes.toString('base64'));
 }
 return result;
}
