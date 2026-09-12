import {bannerSvg} from '../cloud/api/_lib/visuals.js';
import {AD_SIZES,runCampaign} from '../cloud/api/_lib/engine.js';
import {vectorQuality,qualityIssues} from '../cloud/public/vector-quality.js';
import {mkdirSync,writeFileSync} from 'node:fs';
const out=process.argv[2];mkdirSync(out,{recursive:true});
const cases=[
 {id:'coffee',product:'Northline Coffee',headline:'A better morning, brewed.',subheadline:'Coffee roasted in small batches',benefits:['Whole beans or ground','Choose your roast'],offer:'250 g · Rs 1,450',cta:'Explore the roasts',primary:'#BB4A2B',secondary:'#F8F1E5'},
 {id:'fitness',product:'Forma Studio',headline:'Make room for movement.',subheadline:'Small-group strength sessions',benefits:['Morning and evening classes','Book a studio visit'],offer:'Intro class · Rs 800',cta:'View the schedule',primary:'#B8EE58',secondary:'#182B23'},
 {id:'service',product:'Haven Property',headline:'Your next chapter starts here.',subheadline:'Explore available homes with a local team',benefits:['View floor plans','Arrange an in-person viewing'],offer:'Viewings by appointment',cta:'Book a viewing',primary:'#315A92',secondary:'#F2F4F6'},
 {id:'urdu',product:'Karak House',headline:'آپ کی صبح، آپ کی چائے',subheadline:'تازہ چائے اور نرم پراٹھا',benefits:['آج ہی آرڈر کریں'],offer:'چائے ۱۵۰ روپے',cta:'آرڈر کریں',primary:'#C85A28',secondary:'#FFF2DB'},
 {id:'hindi',product:'Daily Care',headline:'आपकी रोज़ की देखभाल',subheadline:'अपनी दिनचर्या को सरल बनाएं',benefits:['उत्पाद की जानकारी पढ़ें'],offer:'उपलब्ध विकल्प देखें',cta:'और जानें',primary:'#634286',secondary:'#F6EEF8'},
 {id:'rejected-long',product:'An intentionally overlong sample brand name for fit review',headline:'An intentionally long headline that cannot be assumed to fit every ad format without an explicit review of the final text',subheadline:'Read every eligibility condition before selecting this offer because the important conditions are not optional and must never silently disappear.',benefits:['Appointments available subject to location and service availability','Ask the team for the complete exclusions and eligibility details','Delivery fees and availability vary by address'],offer:'Rs 1,450 only for qualifying new orders before the stated deadline; exclusions and delivery fees apply',cta:'Review the complete eligibility conditions',primary:'#BDBDBD',secondary:'#FFFFFF'}
];
const sampleSizes=[['hero',1200,630],['square',1080,1080],['story',1080,1920],['display',300,250],['strip',320,50]];
const entries=[];
for(const brief of cases)for(const [format,width,height]of sampleSizes){
 const name=brief.id+'-'+format+'.svg',content=bannerSvg({...brief,width,height,style:'editorial-v1',watermark:true,explicitVisualFields:true});
 writeFileSync(out+'/'+name,content);entries.push({id:brief.id,format,name,width,height,issues:qualityIssues(vectorQuality([{name,content}]))});
}
const input={product:'Northline Coffee',benefits:'Small-batch roasting; Whole beans or ground',offer:'250 g · Rs 1,450',cta:'Explore the roasts',provider:'offline',style:'editorial-v1',watermark:true,custom_presets:1,custom_sizes:[{preset:'mobile_banner'}]};
const campaign=await runCampaign(input);writeFileSync(out+'/campaign.json',JSON.stringify({...campaign,id:'00000000-0000-4000-8000-000000000002',name:'Editorial QA',product:input.product,revision:1,revisions:[],lang:'en',created_at:'2026-09-11T00:00:00Z'}));
writeFileSync(out+'/fixtures.json',JSON.stringify({cases,entries,sizes:AD_SIZES},null,2));
console.log(JSON.stringify({renders:entries.length,withWarnings:entries.filter(e=>e.issues.length).length}));
