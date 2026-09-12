// Desktop ownership has no hosted-compute entitlement.
export const PLAN_META = {
 free: {id:'free',name:'Free',price_label:'$0',tagline:'Try a complete Cloud pack before subscribing.',features:['3 campaigns total, not reset by deletion','Watermarked visuals','Hero + 1 preset per run','Editable copy, brand profiles and ZIP export']},
 pro: {id:'pro',name:'Pro',price_label:'$49/mo',yearly_label:'$490/year',price_env:'PADDLE_PRICE_PRO',tagline:'For a founder or solo marketer.',features:['50 campaigns per calendar month · up to 20/day','No watermark · 10 banner presets per run','Editable copy, brand profiles and ZIP export','Email support']},
 agency: {id:'agency',name:'Agency',price_label:'$99/mo',price_env:'PADDLE_PRICE_AGENCY',tagline:'More capacity for client work, with predictable limits.',features:['300 campaigns per calendar month · up to 50/day','No watermark · 21 presets and custom sizes','2 concurrent generations · reusable client brands','Priority email support']},
};
export function publicPlans(){return Object.values(PLAN_META).map(p=>({...p}));}
export function effectivePlan(profile){
 if(!profile || !PLAN_META[profile.plan]) return 'free';
 // Past-due customers keep read/export access. Generation pauses immediately;
 // no unbounded grace period or silent new Free allowance.
 return profile.plan;
}
