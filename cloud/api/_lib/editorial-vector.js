// Versioned opt-in composition. Do not mutate v1 after release to redesign
// saved recipes: add another style version instead. No external assets/models.
export function editorialVector(o,{measure,textBox,ink,image,esc,supported}){
 const {w,h,primary,secondary,logo,label,head,sub,offer,cta}=o;
 const fg=ink(secondary),accentInk=ink(primary);
 const kind=w<180&&h<140?'micro':h<140||w/h>4?'strip':w/h>=1.65?'wide':'stack';
 const scale=Math.min(1,(kind==='wide'||kind==='strip'?600:360)/w);
 const bodyMin=12/scale,headMin=18/scale;
 const p=Math.max(6,Math.min(w,h)*.065),gap=Math.max(6,Math.min(w,h)*.028),inner=w-2*p;
 const rtl=measure(head||label).rtl,align=rtl?'right':'left';
 let svg=`<g data-renderer="editorial-v1"><rect width="${w}" height="${h}" fill="${secondary}"/>`;
 const tag=(field,status,content='',size=0)=>`<g data-quality-field="${field}" data-fit="${status}" data-font-size="${size.toFixed(2)}">${content}</g>`;
 const norm=t=>String(t||'').replace(/\s+/g,' ').trim();
 const list=o.list.map((text,i)=>({text,field:'benefit_'+(i+1)})).filter((item,i)=>{
  if(i>=3){svg+=tag(item.field,'omitted_format');return false;}
  if([norm(head),norm(sub)].includes(norm(item.text))){svg+=tag(item.field,'repeated_in_heading');return false;}return true;
 });
 const omit=(field,text)=>{svg+=tag(field,text?'omitted_format':'empty');};
 function fit(field,text,box,maxSize,minSize=bodyMin,maxLines=2,color=fg,a=align){
  text=String(text||'').trim();if(!text)return tag(field,'empty');
  if(!supported(text))return tag(field,'omitted_unsupported');
  const [, ,width,height]=box;
  // Refuse rather than truncate a price, condition or word. The report keeps
  // deliberate format omission distinct from copy which cannot fit safely.
  for(let size=Math.max(minSize,maxSize);size>=minSize-.001;size=Math.max(minSize,size-.5)){
   const lines=[];let line='';
   for(const word of text.split(/\s+/)){const trial=line?line+' '+word:word;if(line&&measure(trial).width*size>width){lines.push(line);line=word;}else line=trial;}
   if(line)lines.push(line);
   const shapes=lines.map(measure),total=shapes.reduce((v,s)=>v+s.height*size,0)+Math.max(0,lines.length-1)*size*.45;
   if(width>0&&height>0&&lines.length<=maxLines&&shapes.every(s=>s.width*size<=width)&&total<=height){
    return tag(field,'included',textBox(text,box,size,color,maxLines,a),size);
   }
   if(size===minSize)break;
  }
  return tag(field,'omitted_unfit');
 }
 function brand(y,height){
  const lw=logo?Math.min(height,inner*.22):0;
  const lx=rtl?w-p-lw:p;
  if(logo)svg+=image(logo,lx,y,lw,height);
  svg+=fit('brand',label,[p+(logo&&!rtl?lw+gap:0),y,inner-(logo?lw+gap:0),height],Math.min(28/scale,height*.7),bodyMin,2);
 }
 function action(x,y,width,height){
  const copy=fit('cta',cta,[x+gap,y+gap*.4,width-2*gap,height-gap*.8],18/scale,bodyMin,2,accentInk,'center');
  // No empty fake button when its label cannot fit.
  if(copy.includes('data-fit="included"'))svg+=`<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="${Math.min(4,height*.08)}" fill="${primary}"/>`;
  svg+=copy;
 }
 if(kind==='micro'){
  if(logo){svg+=image(logo,p,p,inner,h-2*p);svg+=tag('brand','logo');}
  else svg+=fit('brand',label,[p,p,inner,h-2*p],Math.min(20,h*.4),12,2,fg,'center');
  for(const [f,t]of [['headline',head],['subheadline',sub],['offer',offer],['cta',cta]])omit(f,t);
  list.forEach(t=>omit(t.field,t.text));
 }else if(kind==='strip'){
  const bw=Math.min(inner*.38,240/scale),available=inner-bw-gap;
  // Strips explicitly prioritize brand + action, not a tiny complete poster.
  svg+=fit('brand',label,[p,p,available,h-2*p],24/scale,bodyMin,2);
  action(w-p-bw,p,bw,h-2*p);
  for(const [f,t]of [['headline',head],['subheadline',sub],['offer',offer]])omit(f,t);
  list.forEach(t=>omit(t.field,t.text));
 }else{
  const story=h/w>1.65;
  const top=story?Math.max(p,h*.10):p,bottom=story?Math.max(p,h*.14):p;
  const usable=h-top-bottom,brandH=Math.min(42/scale,usable*.10);
  brand(top,brandH);
  const by=top+brandH+gap*1.6,actionH=Math.min(usable*.20,Math.max(bodyMin*2.8,Math.min(48/scale,usable*.13))),ay=h-bottom-actionH;
  const mainH=ay-gap*1.5-by;
  if(kind==='wide'){
   const leftW=list.length?inner*.62:inner,rightW=inner-leftW-gap*2;
   const hx=rtl?w-p-leftW:p,rx=rtl?p:p+leftW+gap*2;
   svg+=fit('headline',head,[hx,by,leftW,mainH*.63],68/scale,headMin,3);
   svg+=fit('subheadline',sub,[hx,by+mainH*.68,leftW,mainH*.28],23/scale,bodyMin,2);
   // A quiet rule, not a giant colored benefits rectangle or invented icon.
   const ruleX=rtl?w-p-leftW-gap:p+leftW+gap;
   if(list.length)svg+=`<path d="M${ruleX} ${by}v${mainH}" stroke="${fg}" stroke-opacity=".25"/>`;
   const rows=list.length,step=mainH/Math.max(1,rows);
   list.forEach((t,i)=>{svg+=fit(t.field,t.text,[rx,by+i*step,rightW,step-gap],22/scale,bodyMin,3);});
  }else{
   // One aligned reading column; generous story UI margins are advisory,
   // not certification for any platform's constantly changing overlays.
   svg+=fit('headline',head,[p,by,inner,mainH*.34],Math.min(76/scale,w*.095),headMin,3);
   svg+=fit('subheadline',sub,[p,by+mainH*.38,inner,mainH*.16],22/scale,bodyMin,2);
   const start=by+mainH*.59,step=mainH*.38/Math.max(1,list.length);
   list.forEach((t,i)=>{svg+=fit(t.field,t.text,[p,start+i*step,inner,step-gap*.35],20/scale,bodyMin,2);});
  }
  const buttonW=offer?inner*.40:Math.min(inner,Math.max(inner*.48,140/scale));
  const buttonX=rtl?p:w-p-buttonW;
  if(offer){
   const ox=rtl?p+buttonW+gap:p;
   svg+=fit('offer',offer,[ox,ay,inner-buttonW-gap,actionH],25/scale,bodyMin,3);
  }else svg+=tag('offer','empty');
  action(buttonX,ay,buttonW,actionH);
 }
 // Explicit metadata survives standalone source download and raster sources.
 svg=svg.replace(/<g data-quality-field="(benefit_[0-9]+)" data-fit="repeated_in_heading" data-font-size="0.00"><\/g>/g,(tag,field)=>{const text=o.list[Number(field.split('_')[1])-1],source=norm(text)===norm(head)?'headline':'subheadline';const status=svg.match(new RegExp(`data-quality-field="${source}" data-fit="([^"]+)"`))?.[1];return status==='included'?tag:tag.replace('repeated_in_heading',status?.startsWith('omitted_')?status:'omitted_format');});
 return {layout:'editorial-'+kind,svg:svg+`<metadata>${esc('Editorial v1 draft. Review omissions, copy accuracy, actual-size legibility and platform safe areas before publishing. No product image or verified proof is implied.')}</metadata></g>`};
}
