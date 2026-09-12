import {vi} from 'vitest';
export const ids={pro:'pri_'+ '1'.repeat(26),year:'pri_'+ '2'.repeat(26),agency:'pri_'+ '3'.repeat(26),owner:'pri_'+ '4'.repeat(26),source:'pri_'+ '5'.repeat(26),customer:'ctm_'+ '1'.repeat(26),subscription:'sub_'+ '1'.repeat(26)};
export function configure(){
 const vars={PADDLE_API_KEY:'pdl_sandbox_test',PADDLE_ENV:'sandbox',PADDLE_CLIENT_TOKEN:'test_client_token',PADDLE_WEBHOOK_SECRET:'fixture-webhook-secret',BILLING_ACTION_SECRET:'a'.repeat(40),SUPABASE_URL:'https://db.example.test',SUPABASE_SERVICE_ROLE_KEY:'fixture-only',GROQ_API_KEY:'fixture-only',GROQ_INPUT_USD_PER_MTOK:'.1',GROQ_OUTPUT_USD_PER_MTOK:'.1',CLOUD_CHECKOUT_ENABLED:'true',DESKTOP_CHECKOUT_ENABLED:'true',BILLING_RELEASE_VERIFIED:'true',PADDLE_PRICE_PRO:ids.pro,PADDLE_PRICE_PRO_YEARLY:ids.year,PADDLE_PRICE_AGENCY:ids.agency,PADDLE_PRICE_DESKTOP_OWNER:ids.owner,PADDLE_PRICE_DESKTOP_AGENCY_SOURCE:ids.source,DESKTOP_DOWNLOAD_SECRET:'d'.repeat(40),DESKTOP_STORAGE_BUCKET:'private-releases',DESKTOP_OWNER_PATH:'releases/owner.zip',DESKTOP_AGENCY_SOURCE_PATH:'releases/source.zip',DESKTOP_RELEASE_SHA256_OWNER:'a'.repeat(64),DESKTOP_RELEASE_SHA256_AGENCY_SOURCE:'b'.repeat(64),RESEND_API_KEY:'fixture-only',DELIVERY_FROM_EMAIL:'BrandForge <orders@example.test>',BRANDFORGE_APP_URL:'https://app.example.test',BRANDFORGE_MARKETING_URL:'https://www.example.test'};
 for(const [k,v]of Object.entries(vars))vi.stubEnv(k,v);
}
export function paddleServer(){
 const state={customers:new Map(),subscriptions:new Map(),transactions:new Map(),emails:[],calls:[],emailFailure:false,cancelFailure:false,outage:false,priceMismatch:false};
 const response=(data,status=200)=>({ok:status<300,status,json:async()=>({data,meta:{pagination:{has_more:false}}})});
 const prices={ [ids.pro]:[4900,'month'],[ids.year]:[49000,'year'],[ids.agency]:[9900,'month'],[ids.owner]:[19900,null],[ids.source]:[49900,null]};
 const fetcher=vi.fn(async(url,options={})=>{
  const u=new URL(url),method=options.method||'GET',body=options.body?JSON.parse(options.body):undefined;state.calls.push({path:u.pathname,method,body});
  if(u.hostname==='api.resend.com'){if(state.emailFailure)return response(null,500);state.emails.push({body,headers:options.headers});return response({id:'email-fixture'});}
  if(state.outage)throw new Error('Injected Paddle outage');
  const parts=u.pathname.split('/').filter(Boolean);
  if(parts[0]==='prices'){const spec=prices[parts[1]];return response({id:parts[1],status:'active',unit_price:{amount:String(state.priceMismatch?1:spec[0]),currency_code:'USD'},billing_cycle:spec[1]?{interval:spec[1],frequency:1}:null,trial_period:null});}
  if(parts[0]==='customers'){
   if(parts[2]==='portal-sessions')return response({urls:{general:{overview:'https://customer-portal.paddle.com/fixture'}}});
   if(parts[1])return response(state.customers.get(parts[1]));
   if(method==='GET')return response([...state.customers.values()].filter(c=>c.email===u.searchParams.get('email')));
   const c={id:'ctm_'+String(state.customers.size+1).padStart(26,'0'),email:body.email};state.customers.set(c.id,c);return response(c);
  }
  if(parts[0]==='transactions'){
   if(method==='GET'&&!parts[1])return response([...state.transactions.values()].filter(t=>t.customer_id===u.searchParams.get('customer_id')));
   if(method==='POST'){const t={id:'txn_'+String(state.transactions.size+1).padStart(26,'0'),status:'draft',...body};state.transactions.set(t.id,t);return response(t);}
   const t=state.transactions.get(parts[1]);if(method==='PATCH')Object.assign(t,body);return response(t);
  }
  if(parts[0]==='subscriptions'){
   if(!parts[1])return response([...state.subscriptions.values()].filter(s=>s.customer_id===u.searchParams.get('customer_id')));
   const s=state.subscriptions.get(parts[1]);
   if(parts[2]==='preview')return response({currency_code:'USD',immediate_transaction:{details:{totals:{grand_total:'1500',total:'1500'}}},next_transaction:{details:{totals:{grand_total:'9900'}}},next_billed_at:'2026-10-05T00:00:00Z'});
   if(parts[2]==='cancel'){if(state.cancelFailure)return response(null,503);s.status='canceled';s.updated_at=new Date(Date.now()+1000).toISOString();return response(s);}
   if(method==='PATCH'){s.items=body.items.map(i=>({price:{id:i.price_id},quantity:i.quantity}));s.updated_at=new Date(Date.now()+1000).toISOString();return response(s);}
   return response(s);
  }
  throw new Error('Unexpected fixture request: '+url);
 });
 vi.stubGlobal('fetch',fetcher);state.fetcher=fetcher;return state;
}
export async function knownSubscription(sb,state,user,{id=ids.subscription,price=ids.pro,status='active'}={}){
 const customerId=ids.customer;
 state.customers.set(customerId,{id:customerId,email:user.email});
 const subscription={id,customer_id:customerId,status,items:[{price:{id:price},quantity:1}],currency_code:'USD',updated_at:new Date().toISOString()};
 state.subscriptions.set(id,subscription);
 await sb.rpc('apply_subscription',{p_uid:user.id,p_id:id,p_customer:customerId,p_plan:price===ids.agency?'agency':'pro',p_status:status,p_price:price,p_interval:price===ids.year?'year':'month',p_at:subscription.updated_at});
 return subscription;
}
