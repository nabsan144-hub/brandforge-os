import {newDocument,validateDocument} from './model.js';
import {prepareReference} from './import-image.js';
export async function launchCampaign(c){
 const source=c.files?.find(f=>f.name==='canvas_hero.json');
 if(source){
  if(!confirm('Open the saved AI canvas? The artwork and its lettering are raster; add or replace layers here. The original campaign is unchanged.'))return;
  const d=validateDocument(JSON.parse(source.content));sessionStorage.setItem('bf-canvas-handoff',JSON.stringify(d));location.assign('/canvas/');return;
 }
 if(!confirm('Create a separate editable canvas with the hero as a flattened reference and the three text sections? Outlined text is not recovered as editable type. Add or rebuild layers here; the original campaign remains unchanged.'))return;
 const hero=c.files?.find(f=>f.name==='hero_banner.svg');if(typeof hero?.content!=='string')throw Error('Load the original hero files before opening the canvas.');
 const d=newDocument(String(c.name||c.campaign_name||'Campaign canvas').slice(0,80));
 const sections={strategy:typeof c.strategy==='string'?c.strategy:c.strategy?.strategy_text||'',copy:typeof c.copy==='string'?c.copy:c.copy?.copy_text||'',seo:typeof c.seo==='string'?c.seo:c.analysis?.seo_analysis||''};
 for(const k of Object.keys(sections)){if(sections[k].length>20000)throw Error('A text section exceeds the editable transfer limit; retain the original ZIP.');d.sections[k]=sections[k];}
 const bytes=hero.encoding==='base64'?Uint8Array.from(atob(hero.content),x=>x.charCodeAt(0)):hero.content;
 const src=await prepareReference(new File([bytes],'hero.svg',{type:'image/svg+xml'}));
 d.layers.push({id:crypto.randomUUID(),type:'image',src,fit:'contain',anchor:'xMidYMid',x:0,y:0,width:d.width,height:d.height,rotation:0,fill:'#ffffff',opacity:1});validateDocument(d);
 sessionStorage.setItem('bf-canvas-handoff',JSON.stringify(d));location.assign('/canvas/');
}
