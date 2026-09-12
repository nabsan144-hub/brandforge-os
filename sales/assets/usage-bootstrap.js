import {createUsageMetrics} from './usage-metrics.js';
const c=window.BRANDFORGE_LAUNCH||{};
if(c.first_party_metrics_enabled===true){
 const host=document.createElement('div');host.style.cssText='max-width:900px;margin:20px auto;padding:16px;font:14px/1.6 system-ui';document.querySelector('footer')?.append(host);
 createUsageMetrics({enabled:true,endpoint:c.hosted_url.replace(/\/$/,'')+'/api/usage-metrics',surface:'sales',host});
}
