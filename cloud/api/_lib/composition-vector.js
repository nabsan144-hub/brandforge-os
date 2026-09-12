// New opt-in versioned families. Older renderers are deliberately untouched.
export const COMPOSITION_STYLES=['product-v1','offer-v1','service-v1','evidence-v1'];
export function chooseComposition(input){
 if(input.product_image)return 'product-v1';
 if(String(input.proof||'').trim())return 'evidence-v1';
 if(String(input.offer||'').trim())return 'offer-v1';
 if(String(input.benefits||'').trim())return 'service-v1';
 return 'editorial-v1';
}
export function compositionVector(o,{measure,textBox,ink,image,esc,supported}){
 const {w,h,style,primary,secondary,logo,label,head,sub,offer,cta,proof,product_image,logo_position='left',photo_fit='contain',photo_anchor='center'}=o;
 const anchor=({'top-left':'xMinYMin',top:'xMidYMin','top-right':'xMaxYMin',left:'xMinYMid',center:'xMidYMid',right:'xMaxYMid','bottom-left':'xMinYMax',bottom:'xMidYMax','bottom-right':'xMaxYMax'})[photo_anchor]||'xMidYMid';
 const fg=ink(secondary),accent=ink(primary),scale=Math.max(1,w/600),min=12*scale;
 const small=h<150||w/h>4,story=h/w>1.65;
 const p=Math.max(6,Math.min(w,h)*.065),g=Math.max(5,Math.min(w,h)*.025),inner=w-2*p;
 const top=story?Math.max(p,h*.10):p,bottom=story?Math.max(p,h*.14):p;
 const align=measure(head||label).rtl?'right':'left';
 let svg=`<g data-renderer="${style}"><rect width="${w}" height="${h}" fill="${secondary}"/>`;
 const tag=(field,status,content='',size=0)=>`<g data-quality-field="${field}" data-fit="${status}" data-font-size="${size.toFixed(2)}">${content}</g>`;
 const omit=(field,text)=>tag(field,text?'omitted_format':'empty');
 function fit(field,text,box,maxSize,lines=3,color=fg,a=align){
  text=String(text||'').trim();if(!text)return tag(field,'empty');
  if(!supported(text))return tag(field,'omitted_unsupported');
  const floor=small?10:Math.max(min,w*(story?14:12)/360);
  for(let size=Math.max(floor,maxSize);size>=floor;size=Math.max(floor,size-.5)){
   const parts=[];let line='';
   for(const word of text.split(/\s+/)){const next=line?line+' '+word:word;if(line&&measure(next).width*size>box[2]){parts.push(line);line=word;}else line=next;}
   if(line)parts.push(line);
   const shapes=parts.map(measure),height=shapes.reduce((v,s)=>v+s.height*size,0)+Math.max(0,parts.length-1)*size*.45;
   if(box[2]>0&&box[3]>0&&parts.length<=lines&&shapes.every(s=>s.width*size<=box[2])&&height<=box[3])return tag(field,'included',textBox(text,box,size,color,lines,a),size);
   if(size===floor)break;
  }
  return tag(field,'omitted_unfit');
 }
 // Tiny formats prioritize the actual offer, not a decorative brand badge.
 // Deliberate omissions are exported; no partial price/terms are ever printed.
 if(small){
  const main=offer||head||label;
  svg+=fit(offer?'offer':'headline',main,[p,p,inner*.65-g,h-2*p],Math.min(24,h*.35),2);
  svg+=fit('cta',cta,[p+inner*.65,p,inner*.35,h-2*p],Math.min(18,h*.30),2);
  if(offer)svg+=omit('headline',head);else svg+=omit('offer',offer);
  svg+=omit('brand',label)+omit('subheadline',sub)+omit('proof',proof)+omit('product_image',product_image);
  o.list.forEach((x,i)=>svg+=omit('benefit_'+(i+1),x));
  return {layout:style+'-compact',svg:svg+'</g>'};
 }
 const brandH=Math.min(48*scale,(h-top-bottom)*.09),logoW=logo?brandH:0;
 if(logo)svg+=image(logo,logo_position==='right'?w-p-logoW:p,top,logoW,brandH);
 svg+=fit('brand',label,[p+(logo&&logo_position!=='right'?logoW+g:0),top,inner-(logo?logoW+g:0),brandH],24*scale,2);
 const y=top+brandH+g*1.6,actionH=Math.min(58*scale,(h-top-bottom)*.14),ay=h-bottom-actionH;
 const available=ay-g*1.5-y;
 // A simple action on the customer's accent: never a universal gold/glass pill.
 const action=fit('cta',cta,[p+g,ay+g*.25,inner-2*g,actionH-g*.5],22*scale,2,accent,'center');
 if(action.includes('data-fit="included"'))svg+=`<rect x="${p}" y="${ay}" width="${inner}" height="${actionH}" rx="3" fill="${primary}"/>`;
 svg+=action;
 if(style==='product-v1'){
  const wide=w/h>=1.45,iw=wide?inner*.47:inner,ih=wide?available:available*.46;
  const ix=wide?p+inner-iw:p,iy=wide?y:y+available-ih;
  // Contain rather than cover: product edges are retained, never cropped away.
  if(/^data:image\/jpeg;base64,[A-Za-z0-9+/]+={0,2}$/.test(product_image||'')){
   svg+=`<rect x="${ix}" y="${iy}" width="${iw}" height="${ih}" fill="#FFFFFF"/>`+tag('product_image','included',(photo_fit==='crop'?`<svg x="${ix}" y="${iy}" width="${iw}" height="${ih}" overflow="hidden"><image href="${esc(product_image)}" width="${iw}" height="${ih}" preserveAspectRatio="${anchor} slice" aria-label="Cropped approved photograph"/></svg>`:`<image href="${esc(product_image)}" x="${ix}" y="${iy}" width="${iw}" height="${ih}" preserveAspectRatio="xMidYMid meet" aria-label="Approved product photograph"/>`));
  }else svg+=tag('product_image','omitted_unfit');
  const tw=wide?inner-iw-2*g:inner,th=wide?available:available-ih-g;
  svg+=fit('headline',head,[p,y,tw,th*.52],48*scale,3);
  svg+=fit('offer',offer,[p,y+th*.58,tw,th*.40],25*scale,3);
  svg+=omit('subheadline',sub)+omit('proof',proof);o.list.forEach((x,i)=>svg+=omit('benefit_'+(i+1),x));
 }else if(style==='offer-v1'){
  svg+=`<rect x="${p}" y="${y}" width="${inner}" height="${available*.58}" fill="${primary}"/>`;
  svg+=fit('offer',offer,[p+g,y+g,inner-2*g,available*.58-2*g],58*scale,4,accent,'center');
  svg+=fit('headline',head,[p,y+available*.65,inner,available*.32],30*scale,3);
  svg+=omit('subheadline',sub)+omit('proof',proof)+omit('product_image',product_image);o.list.forEach((x,i)=>svg+=omit('benefit_'+(i+1),x));
 }else if(style==='evidence-v1'){
  svg+=fit('headline',head,[p,y,inner,available*.26],42*scale,3);
  svg+=`<path d="M${p} ${y+available*.34}H${w-p}" stroke="${fg}" stroke-opacity=".3"/>`;
  svg+=fit('proof',proof,[p,y+available*.39,inner,available*.34],24*scale,4);
  svg+=fit('offer',offer,[p,y+available*.80,inner,available*.18],20*scale,2);
  svg+=omit('subheadline',sub)+omit('product_image',product_image);o.list.forEach((x,i)=>svg+=omit('benefit_'+(i+1),x));
 }else{
  svg+=fit('headline',head,[p,y,inner,available*.34],48*scale,3);
  const list=o.list.filter(Boolean).slice(0,2),step=available*.27/Math.max(1,list.length);
  list.forEach((x,i)=>{svg+=fit('benefit_'+(i+1),x,[p,y+available*.42+i*step,inner,step-g*.3],22*scale,2);});
  o.list.slice(2).forEach((x,i)=>svg+=omit('benefit_'+(i+3),x));
  svg+=fit('offer',offer,[p,y+available*.76,inner,available*.22],23*scale,3);
  svg+=omit('subheadline',sub)+omit('proof',proof)+omit('product_image',product_image);
 }
 return {layout:style+(story?'-story':w>h?'-wide':'-stack'),svg:svg+`<metadata>${esc('Draft composition. Fit diagnostics report omitted content, not advertising approval. Product photos are resized and contained, never sent to a model. Supplied proof is not independently verified.')}</metadata></g>`};
}
