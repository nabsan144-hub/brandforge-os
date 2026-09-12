// Fetch only an owner-authorized immutable bundle, never persist its signed URL.
const MAX_BYTES=20_000_000;
const sha=async data=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),x=>x.toString(16).padStart(2,'0')).join('');
function bytesOf(file){
 if(typeof file?.content!=='string'||(file.encoding!==undefined&&file.encoding!=='base64'))throw new Error('Invalid private file encoding.');
 if(file.encoding==='base64'){
  if(!/^[A-Za-z0-9+/]*={0,2}$/.test(file.content)||file.content.length%4)throw new Error('Invalid private file encoding.');
  return Uint8Array.from(atob(file.content),x=>x.charCodeAt(0));
 }
 return new TextEncoder().encode(file.content);
}
export async function hydrateCampaign(campaign,requestJSON,supabaseUrl,fetcher=fetch){
 if(!campaign.asset_bundle_id){
  if((campaign.files||[]).some(f=>typeof f.content!=='string'))throw new Error('Campaign files are incomplete. Contact support; no export was created.');
  return campaign;
 }
 const fail=()=>new Error('Private file verification failed. Retry opening the campaign; no files were exported.');
 const auth=await requestJSON('/campaigns/'+encodeURIComponent(campaign.id)+'/assets');
 const url=new URL(auth.url),origin=new URL(supabaseUrl);
 if(origin.protocol!=='https:'||url.protocol!=='https:'||url.origin!==origin.origin||url.username||url.password)throw fail();
 if(auth.schema!==1||!Number.isInteger(auth.bytes)||auth.bytes<1||auth.bytes>MAX_BYTES||!/^[a-f0-9]{64}$/.test(auth.sha256))throw fail();
 const response=await fetcher(url.href,{credentials:'omit',redirect:'error',cache:'no-store',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(60000)});
 if(!response.ok||!response.body?.getReader)throw new Error('Private download expired or failed. Retry opening the campaign.');
 const reader=response.body.getReader(),chunks=[];let size=0;
 try{
  for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>auth.bytes||size>MAX_BYTES)throw fail();chunks.push(value);}
 }catch(e){await reader.cancel().catch(()=>{});throw e;}finally{reader.releaseLock();}
 if(size!==auth.bytes)throw fail();
 const data=new Uint8Array(size);let offset=0;for(const chunk of chunks){data.set(chunk,offset);offset+=chunk.length;}
 if(await sha(data)!==auth.sha256)throw fail();
 let bundle;try{bundle=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(data));}catch{throw fail();}
 const manifest=campaign.files;
 if(bundle.schema!==1||!Array.isArray(bundle.files)||!Array.isArray(manifest)||!manifest.length||manifest.length>64||bundle.files.length!==manifest.length)throw fail();
 const names=new Set();
 for(let i=0;i<manifest.length;i++){
  const file=bundle.files[i],m=manifest[i];
  if(!/^[\p{L}\p{N}][\p{L}\p{N}._-]{0,119}$/u.test(file?.name||'')||names.has(file.name)||file.name!==m.name||(file.encoding||'utf8')!==m.encoding||m.storage!=='bundle')throw fail();
  names.add(file.name);const bytes=bytesOf(file);
  if(bytes.length>8_000_000||bytes.length!==m.bytes||await sha(bytes)!==m.sha256)throw fail();
 }
 return {...campaign,files:bundle.files};
}
export async function hydrateAccountExport(payload,requestJSON,supabaseUrl,fetcher=fetch){
 const campaigns=[];
 // Sequential: keep each response <=20MB and avoid a burst of downloads.
 for(const campaign of payload.data?.campaigns||[])campaigns.push(await hydrateCampaign(campaign,requestJSON,supabaseUrl,fetcher));
 return {...payload,data:{...payload.data,campaigns},files_included:true};
}
