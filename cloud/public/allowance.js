// Display guidance only. Server-side reservations remain authoritative.
export const SAVED_PACK_POLICY='A saved pack uses one campaign, including labeled template fallbacks. Failed unsaved work does not. Text edits, downloads and supported deterministic corrections do not use another campaign. Deleting work does not restore usage.';
export function allowanceCopy(me){
 const l=me?.limits||{},u=me?.usage||{},count=x=>Number.isFinite(x)&&x>=0?x:0;
 const lifetime=l.lifetime!=null,limit=lifetime?l.lifetime:l.monthly,used=count(lifetime?u.campaigns_lifetime:u.campaigns_this_month),reserved=count(u.reserved);
 const remaining=Number.isFinite(limit)?Math.max(0,limit-used-reserved):null;
 const period=lifetime?'lifetime':'this UTC calendar month';
 const summary=`${lifetime?'Free':String(me?.plan||'Cloud')} — ${used}${Number.isFinite(limit)?'/'+limit:''} campaigns used ${period}${remaining!==null?' · '+remaining+' available':''}${reserved?' · '+reserved+' in progress':''}`;
 const reset=lifetime?'Free lifetime usage never resets.':'Monthly usage resets on the first day of each month at 00:00 UTC, not your subscription billing date.';
 const daily=Number.isFinite(l.daily)?` At most ${l.daily} campaigns per UTC day; the daily window resets at 00:00 UTC.`:'';
 return {summary,policy:SAVED_PACK_POLICY+' '+reset+daily+' Provider availability and service-wide safety budgets can also limit new work.'};
}
