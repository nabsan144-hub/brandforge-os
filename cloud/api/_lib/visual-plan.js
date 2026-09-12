// Resolve imagery ONCE before budget reservation. Never serialize this object:
// it contains the operator key. Only publicVisualStatus() is safe to persist.
import {HttpError} from './http.js';
import {resolveImageExecution} from './image-providers.js';
import {aiVisualsProvider,aiVisualsKey,aiVisualsModel} from './visuals_ai.js';

export function visualConfig(){
 const provider=aiVisualsProvider();
 const valid=['gemini','openai','xai'].includes(provider);
 const model=valid?aiVisualsModel():null;
 return {
  enabled:process.env.AI_VISUALS_ENABLED==='true' && valid && !!aiVisualsKey(),
  provider:valid?provider:null,model:valid?model:null,
  fields:['product / brand','industry','audience','tone','brand colors',...(process.env.AI_CAMPAIGN_ENABLED==='true'?['benefits','offer','call to action','proof','prohibited claims','language','separately consented reference images']:[])],
  scope:'AI campaign mode produces three separately composed advertisements when enabled; otherwise image generation covers the hero only.',
  campaignEnabled:process.env.AI_CAMPAIGN_ENABLED==='true',
  referenceImages:['gemini','openai'].includes(provider),
 };
}
export function resolveVisualPlan(input){
 if(input.product_image&&input.artwork_mode!=='campaign')return {enabled:false,state:'not_requested',reason:'APPROVED_PRODUCT_PHOTO'};
 const requested=input.visual_requested===true || input.visuals_ai===true;
 if(input.provider==='offline')return {enabled:false,state:'not_requested',reason:'NO_AI_MODE'};
 if(!requested)return {enabled:false,state:'not_requested'};
 if(input.visuals_ai!==true)return {enabled:false,state:'not_entitled',reason:'PAID_PLAN_REQUIRED'};
 const cfg=visualConfig();
 if(!cfg.enabled&&input.artwork_mode==='campaign')throw new HttpError(503,'AI campaign generation is unavailable. No basic design was substituted.','AI_CAMPAIGN_UNAVAILABLE');
 if(!cfg.enabled)return {enabled:false,state:'not_configured',reason:'VISUALS_UNAVAILABLE'};
 if(input.visual_provider!==cfg.provider)throw new HttpError(409,'The image provider changed or was not confirmed. Refresh the workspace and review image sharing before generating.','VISUAL_CONSENT_REQUIRED');
 if(input.artwork_mode==='campaign'&&process.env.AI_CAMPAIGN_ENABLED!=='true')throw new HttpError(503,'AI campaign generation is not enabled. No basic design was substituted.','AI_CAMPAIGN_UNAVAILABLE');
 if(input.visual_model&&input.visual_model!==cfg.model)throw new HttpError(409,'The image model changed. Refresh and review the current selection.','VISUAL_CONSENT_REQUIRED');
 const references=input.artwork_mode==='campaign'&&input.reference_consent?[input.product_image,input.logo].filter(Boolean):[];
 const execution=resolveImageExecution({provider:cfg.provider,model:cfg.model,key:aiVisualsKey(),referenceImages:references});
 return {enabled:true,state:'requested',provider:execution.provider,model:execution.model,key:execution.key,...(input.artwork_mode==='campaign'?{image_count:3}: {})};
}
export function publicVisualStatus(plan){
 return {mode:'svg',state:plan.state,...(plan.reason?{reason:plan.reason}:{}),...(plan.provider?{provider:plan.provider,model:plan.model}:{}),scope:'hero_only'};
}
