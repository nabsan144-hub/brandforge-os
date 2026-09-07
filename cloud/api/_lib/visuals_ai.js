// Cloud AI artwork scenes (owner-approved v1.8, 2026-09-07).
// The operator chooses the image provider — nothing here is locked to one.
//   AI_VISUALS_PROVIDER = gemini | openai | xai   (default: gemini)
//   gemini: AI_VISUALS_KEY (or GEMINI_API_KEY); model AI_VISUAL_MODEL
//           (default gemini-3.1-flash-image-preview; 3-pro lane via env)
//   openai: AI_VISUALS_OPENAI_KEY (or OPENAI_API_KEY); model AI_VISUAL_MODEL
//           (default gpt-image-1; gpt-image-1-mini via env)
//   xai:    AI_VISUALS_XAI_KEY (or XAI_API_KEY); model AI_VISUAL_MODEL
//           (default grok-imagine-image-2.0; grok-2-image via env)
// Customers never supply a key. Deterministic SVG remains the zero-key fallback.
export function aiVisualsProvider(){ return (process.env.AI_VISUALS_PROVIDER||'gemini').toLowerCase(); }
export function aiVisualsKey(){
 switch(aiVisualsProvider()){
  case 'openai':return process.env.AI_VISUALS_OPENAI_KEY||process.env.OPENAI_API_KEY||'';
  case 'xai':return process.env.AI_VISUALS_XAI_KEY||process.env.XAI_API_KEY||'';
  default:return process.env.AI_VISUALS_KEY||process.env.GEMINI_API_KEY||'';
 }
}
export const AI_VISUAL_MODEL = process.env.AI_VISUAL_MODEL
 || {openai:'gpt-image-1',xai:'grok-imagine-image-2.0'}[aiVisualsProvider()] || 'gemini-3.1-flash-image-preview';

const STYLE = {
  'specialty coffee':'warm golden rim light, steam, dark wooden surfaces, shallow depth of field',
  'skincare & beauty':'soft diffused morning light, stone and ceramic textures, clean minimal styling',
  'fashion & apparel':'directional studio light, fabric texture detail, editorial composition',
  'fintech & finance':'clean architectural geometry, deep shadows, restrained confident palette',
  'saas & tech':'soft gradient light, glass and brushed metal, airy minimal composition',
  'cafés & restaurants':'warm ambient light, handcrafted surfaces, appetizing natural detail',
};
const MOOD = {
  premium:'premium, calm, editorial', luxury:'luxurious, moody, high-contrast',
  playful:'bright, friendly, energetic', bold:'bold, confident, dramatic', minimal:'minimal, airy, precise',
};

export function scenePrompt(input){
 const style=STYLE[(input.industry||'').toLowerCase()]||'cinematic commercial photography, soft natural light';
 const mood=MOOD[(input.tone||'').toLowerCase()]||'premium and calm';
 const subject=`${input.product} — ${input.industry||'a brand'} for ${input.audience||'its customers'}`;
 return [
  `Create one premium marketing scene for the brand "${subject}".`,
  `Style: ${style}. Mood: ${mood}.`,
  `Colour language: primary ${input.primary||'#E8B54A'}, background ${input.secondary||'#0F172A'} — keep the palette restrained and on-brand.`,
  'Composition: wide 16:9; keep the left third as clean negative space for headline copy; no text at all.',
  'Photorealistic commercial quality, crisp focal subject, believable light and shadow.',
  'No text, no words, no letters, no numbers, no logos, no watermark, no signboards, no packaging mockups with type.',
 ].join(' ');
}

async function callGemini(prompt,key,model,timeoutMs){
 const url=`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
 const body={contents:[{role:'user',parts:[{text:prompt}]}],generationConfig:{responseModalities:['TEXT','IMAGE'],temperature:.7}};
 const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':key},body:JSON.stringify(body),signal:AbortSignal.timeout(timeoutMs)});
 if(!r.ok)throw Object.assign(new Error('Visual provider request failed'),{code:r.status===429?'VISUAL_RATE_LIMIT':r.status===400?'VISUAL_BAD_REQUEST':'VISUAL_PROVIDER_ERROR'});
 const j=await r.json();
 const part=(j.candidates||[])[0]?.content?.parts?.find(p=>p.inlineData&&p.inlineData.data);
 if(!part)throw Object.assign(new Error('The visual provider returned no image.'),{code:'VISUAL_EMPTY'});
 return {mime:part.inlineData.mimeType||'image/png',data:part.inlineData.data};
}
async function callOpenAI(prompt,key,model,timeoutMs){
 const r=await fetch('https://api.openai.com/v1/images/generations',{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${key}`},body:JSON.stringify({model,prompt,size:'1024x1024',quality:'high',n:1,response_format:'b64_json'}),signal:AbortSignal.timeout(timeoutMs)});
 if(!r.ok)throw Object.assign(new Error('Visual provider request failed'),{code:r.status===429?'VISUAL_RATE_LIMIT':r.status===400?'VISUAL_BAD_REQUEST':'VISUAL_PROVIDER_ERROR'});
 const j=await r.json();
 const data=j.data&&j.data[0]&&j.data[0].b64_json;
 if(!data)throw Object.assign(new Error('The visual provider returned no image.'),{code:'VISUAL_EMPTY'});
 return {mime:'image/png',data};
}
async function callXAI(prompt,key,model,timeoutMs){
 const r=await fetch('https://api.x.ai/v1/images/generations',{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${key}`},body:JSON.stringify({model,prompt,n:1,response_format:'b64_json',aspect_ratio:'16:9',resolution:'1k'}),signal:AbortSignal.timeout(timeoutMs)});
 if(!r.ok)throw Object.assign(new Error('Visual provider request failed'),{code:r.status===429?'VISUAL_RATE_LIMIT':r.status===400?'VISUAL_BAD_REQUEST':'VISUAL_PROVIDER_ERROR'});
 const j=await r.json();
 const data=j.data&&j.data[0]&&j.data[0].b64_json;
 if(!data)throw Object.assign(new Error('The visual provider returned no image.'),{code:'VISUAL_EMPTY'});
 return {mime:'image/jpeg',data}; // xAI returns JPEG payloads
}

export async function generateScene(input,{key='',timeoutMs=45000}={}){
 const provider=aiVisualsProvider(),model=AI_VISUAL_MODEL;
 const prompt=scenePrompt(input);
 const out=provider==='openai'?await callOpenAI(prompt,key||aiVisualsKey(),model,timeoutMs)
          :provider==='xai'?await callXAI(prompt,key||aiVisualsKey(),model,timeoutMs)
          :await callGemini(prompt,key||aiVisualsKey(),model,timeoutMs);
 const bytes=Math.floor(out.data.length*0.75);
 if(bytes>4.5*1024*1024)throw Object.assign(new Error('The generated scene is too large.'),{code:'VISUAL_TOO_LARGE'});
 return {mime:out.mime,data:out.data,bytes,provider,model};
}
