// Server-owned adapter registry. No arbitrary URL or client-supplied endpoint.
// Capabilities describe IMPLEMENTED adapters, not everything a vendor advertises.
const ADAPTERS=Object.freeze({
 gemini:Object.freeze({id:'gemini',defaultModel:'gemini-3-pro-image',keyNames:['AI_VISUALS_KEY','GEMINI_API_KEY'],textToImage:true,referenceImages:true,formats:['landscape','square','story']}),
 openai:Object.freeze({id:'openai',defaultModel:'gpt-image-2.5-sunburst',keyNames:['AI_VISUALS_OPENAI_KEY','OPENAI_API_KEY'],textToImage:true,referenceImages:true,formats:['landscape','square','story']}),
 xai:Object.freeze({id:'xai',defaultModel:'grok-imagine-image-2.0',keyNames:['AI_VISUALS_XAI_KEY','XAI_API_KEY'],textToImage:true,referenceImages:false,formats:['landscape','square','story']}),
});
const failure=(code,message)=>Object.assign(new Error(message),{code});
export function configuredImageProvider(){return (process.env.AI_VISUALS_PROVIDER||'gemini').trim().toLowerCase();}
export function imageAdapter(provider){
 if(typeof provider!=='string'||!Object.hasOwn(ADAPTERS,provider))throw failure('VISUAL_PROVIDER_UNSUPPORTED','Unsupported image provider; no other service was selected.');
 const a=ADAPTERS[provider];return {...a,keyNames:[...a.keyNames],formats:[...a.formats]};
}
export function imageProviderKey(provider=configuredImageProvider()){
 const a=imageAdapter(provider);return a.keyNames.map(k=>process.env[k]||'').find(Boolean)||'';
}
export function imageProviderModel(provider=configuredImageProvider()){
 const a=imageAdapter(provider);
 // An explicit provider must not inherit a different provider's configured model.
 return (provider===configuredImageProvider()?process.env.AI_VISUAL_MODEL:'')||a.defaultModel;
}
export function resolveImageExecution({provider=configuredImageProvider(),key,model,format='landscape',referenceImages=[]}={}){
 const a=imageAdapter(provider);
 if(!a.formats.includes(format))throw failure('VISUAL_CAPABILITY_UNSUPPORTED','This adapter does not yet implement the requested format.');
 if(!Array.isArray(referenceImages))throw failure('VISUAL_BAD_REQUEST','Invalid reference image list.');
 if(referenceImages.length&&!a.referenceImages)throw failure('VISUAL_CAPABILITY_UNSUPPORTED','Reference-image generation is not implemented by this adapter; references were not sent.');
 for(const ref of referenceImages)if(typeof ref!=='string'||ref.length>450000||!/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/.test(ref))throw failure('VISUAL_BAD_REQUEST','Invalid or oversized prepared reference image.');
 if(referenceImages.length>2)throw failure('VISUAL_BAD_REQUEST','At most two approved reference images are supported.');
 const selectedModel=model===undefined?imageProviderModel(provider):model;
 if(typeof selectedModel!=='string'||! /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(selectedModel))throw failure('VISUAL_MODEL_UNSUPPORTED','Invalid image model identifier.');
 const selectedKey=key===undefined?imageProviderKey(provider):key;
 if(typeof selectedKey!=='string'||!selectedKey.trim())throw failure('VISUAL_KEY_REQUIRED','The selected image provider needs its own configured key.');
 return Object.freeze({provider,model:selectedModel,key:selectedKey,format});
}
export function publicImageAdapters(){return Object.keys(ADAPTERS).map(provider=>{
 const {keyNames,...a}=imageAdapter(provider);return a;
});}
