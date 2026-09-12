// Interim containment until private object-storage delivery replaces inline SVG.
// Budgets refer to UTF-8 JSON bytes (including base64), not decoded image bytes.
import {HttpError} from './http.js';
export const MAX_CAMPAIGN_JSON_BYTES=3_000_000;
export const MAX_FUNCTION_BODY_BYTES=4_000_000; // margin below Vercel's 4.5 MB cap
export function assertCampaignPayload(campaign){
 if(Buffer.byteLength(JSON.stringify(campaign),'utf8')>MAX_CAMPAIGN_JSON_BYTES)
  throw new HttpError(413,'This campaign is too large to save safely. Reduce selected formats or simplify the brief. No campaign allowance was consumed.','CAMPAIGN_PAYLOAD_LIMIT');
}
export function boundedJson(value){
 const body=JSON.stringify(value);
 if(Buffer.byteLength(body,'utf8')>MAX_FUNCTION_BODY_BYTES)
  throw new HttpError(413,'This older campaign is too large for inline delivery. Try account export or contact support. Your saved content has not changed.','LEGACY_PAYLOAD_LIMIT');
 return new Response(body,{headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
}
