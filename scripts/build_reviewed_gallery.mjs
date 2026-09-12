// Fictional, reproducible local drafts. Illustrations are NOT product photos,
// clinical evidence or property listings. No AI provider or remote assets.
import {writeFileSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {bannerSvg,measuredTextBox} from '../cloud/api/_lib/visuals.js';
import {vectorQuality} from '../cloud/public/vector-quality.js';
const require=createRequire(new URL('../cloud/package.json',import.meta.url)),sharp=require('sharp');
const root=new URL('../sales/assets/gallery/',import.meta.url);mkdirSync(root,{recursive:true});
globalThis.fetch=()=>{throw new Error('No provider calls in this gallery build');};
const source=(label,body,bg)=>`<svg xmlns="http://www.w3.org/2000/svg" width="600" height="650" viewBox="0 0 600 650"><rect width="600" height="650" fill="${bg}"/>${body}${measuredTextBox(label,[85,300,430,90],42,'#263c36',2,'center')}</svg>`;
const sources={
 coffee:source('NORTHLINE', '<ellipse cx="300" cy="580" rx="190" ry="25" fill="#decbb2"/><path d="M140 110H460L435 575H165Z" fill="#c9ab80"/><path d="M140 110H460L444 155H155Z" fill="#9c7646"/><rect x="165" y="235" width="270" height="240" rx="4" fill="#faf3df"/><path d="M270 420Q315 380 338 427Q300 457 270 420" fill="#935838"/>','#f5eee1'),
 tea:source('KARAK THEORY','<path d="M280 65Q245 100 280 140M330 80Q290 115 325 150" fill="none" stroke="#bdcabd" stroke-width="10" stroke-linecap="round"/><ellipse cx="290" cy="570" rx="205" ry="26" fill="#d1b99b"/><path d="M125 185H465L420 535H170Z" fill="#efe0b7"/><ellipse cx="295" cy="185" rx="170" ry="27" fill="#a06432"/><path d="M458 235Q580 215 540 340Q520 389 445 360" fill="none" stroke="#d5c189" stroke-width="30"/>','#f7eddb'),
 skin:source('BLOOM','<ellipse cx="300" cy="585" rx="175" ry="25" fill="#dfd4cb"/><rect x="180" y="155" width="240" height="420" rx="34" fill="#bd7459"/><rect x="192" y="115" width="216" height="90" rx="12" fill="#463e37"/><rect x="190" y="265" width="220" height="225" rx="4" fill="#faf2e6"/>','#f5ece4'),
};
const photos={};const manifest={schema:1,notice:'Fictional local drafts, generated with the shipped Cloud renderer. Product subjects are deliberately drawn packaging/cup illustrations, not photographs or real brands. No native-language, medical, property, delivery-time or customer-quality approval is implied.',files:[],briefs:{},quality:{}};
for(const [name,svg]of Object.entries(sources)){
 const file=name+'-reference.jpg',bytes=await sharp(Buffer.from(svg)).jpeg({quality:88}).toBuffer();writeFileSync(new URL(file,root),bytes);photos[name]='data:image/jpeg;base64,'+bytes.toString('base64');manifest.files.push({name:file,sha256:createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length});
}
const specs={
 coffee:{product:'Northline Coffee',headline:'Choose your next roast',offer:'Fictional offer: 250 g / Rs 1,450',cta:'Explore the roasts',style:'product-v1',primary:'#9B4028',secondary:'#FAF2E4',product_image:photos.coffee},
 'bold-vector-karak':{product:'Karak Theory',headline:'Make time for a tea break',offer:'Fictional menu: cup / Rs 180',cta:'View the menu',style:'product-v1',primary:'#21604E',secondary:'#F6EDDA',product_image:photos.tea},
 'karak-type':{product:'Karak Theory',headline:'Make time for a tea break',offer:'Fictional menu: cup / Rs 180',cta:'View the menu',style:'offer-v1',primary:'#21604E',secondary:'#F6EDDA'},
 fitness:{product:'Pulse Studio',headline:'Make room for strength',benefits:['Coached beginner sessions','Small-group training'],offer:'Fictional schedule: weekday evenings',cta:'Ask about a first session',style:'service-v1',primary:'#256146',secondary:'#ECF2E5',width:1080,height:1080},
 skin:{product:'Bloom Skincare',headline:'Keep your routine simple',offer:'Fictional pack: 100 ml',cta:'Read the ingredients',style:'product-v1',primary:'#8E4834',secondary:'#FAEFE3',product_image:photos.skin},
 realty:{product:'Northline Homes',headline:'Start with what matters to you',benefits:['Share your space requirements','Ask about current availability'],offer:'Illustrative service ad — not a listing',cta:'Discuss your search',style:'service-v1',primary:'#304D68',secondary:'#EFF2F4'},
 urdu:{product:'کڑک تھیوری',headline:'آج ایک وقفہ لیں',benefits:['دودھ والی چائے'],cta:'مینو دیکھیں',style:'service-v1',primary:'#25614F',secondary:'#F7F0DF'},
 story:{product:'Bloom Skincare',headline:'A little time for your routine',offer:'Fictional pack: 100 ml',cta:'Read the ingredients',style:'product-v1',primary:'#8E4834',secondary:'#FAEFE3',product_image:photos.skin,width:1080,height:1920},
 saas:{product:'Ledgerline',headline:'Keep month-end work in view',benefits:['Organize the close checklist','Discuss your reporting workflow'],cta:'See the workflow',style:'service-v1',primary:'#604793',secondary:'#F2EDF7'},
};
for(const [name,brief]of Object.entries(specs)){
 const input={watermark:false,width:1200,height:630,...brief},svg=bannerSvg(input),file=name+'.svg';writeFileSync(new URL(file,root),svg);manifest.files.push({name:file,sha256:createHash('sha256').update(svg).digest('hex'),bytes:Buffer.byteLength(svg)});manifest.briefs[name]={...input,product_image:input.product_image?'Local reference JPEG, see matching source asset':undefined};manifest.quality[name]=vectorQuality([{name:file,content:svg}]);
}
writeFileSync(new URL('reviewed-manifest.json',root),JSON.stringify(manifest,null,2)+'\n');console.log(JSON.stringify({renders:Object.keys(specs).length,provider_requests:0,manifest:'sales/assets/gallery/reviewed-manifest.json'}));
