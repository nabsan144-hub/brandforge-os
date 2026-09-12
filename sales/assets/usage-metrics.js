// No event, session identifier or analytics request before explicit opt-in.
export function createUsageMetrics({enabled,endpoint,surface,host}){
 const key='bf-optional-metrics-v1';let state=null;const pending=new Set();
 if(!enabled||!host)return {event(){}};
 const label=document.createElement('label'),box=document.createElement('input'),copy=document.createElement('span');box.type='checkbox';box.style.width='auto';copy.textContent='Optional usage counts: share feature-event names with BrandForge, not campaign text, names or keys. Off by default. Uncheck to stop future events.';label.append(box,copy);host.append(label);
 try{state=JSON.parse(localStorage.getItem(key)||'null');box.checked=state?.consent===true;}catch{}
 async function event(name){
  if(!box.checked||!state?.consent)return;
  try{
   const day=new Date().toISOString().slice(0,10);if(state.day!==day){state={...state,day,events:{}};}
   if(state.events?.[name])return;const id=crypto.randomUUID();state.events={...state.events,[name]:id};localStorage.setItem(key,JSON.stringify(state));
   const session=state.session,controller=new AbortController();pending.add(controller);
   const undo=()=>{if(box.checked&&state?.session===session&&state.day===day&&state.events?.[name]===id){delete state.events[name];localStorage.setItem(key,JSON.stringify(state));}};
   try{const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,session:state.session,event:name,surface,consent:true}),credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',signal:AbortSignal.any([controller.signal,AbortSignal.timeout(5000)])});
   if(!r.ok)undo();}catch{undo();}finally{pending.delete(controller);}
  }catch{ /* telemetry never blocks or changes the product action */ }
 }
 box.onchange=()=>{if(box.checked){state={consent:true,session:crypto.randomUUID(),day:new Date().toISOString().slice(0,10),events:{}};try{localStorage.setItem(key,JSON.stringify(state));}catch{}event('visit');}else{for(const c of pending)c.abort();pending.clear();state=null;try{localStorage.removeItem(key);}catch{}}};
 if(box.checked){const returning=state.day!==new Date().toISOString().slice(0,10);event('visit');if(returning)event('return_visit');}
 return {event};
}
