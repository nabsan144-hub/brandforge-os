import {it,expect,vi,beforeAll,afterAll,beforeEach} from 'vitest';
import {randomUUID} from 'node:crypto';
vi.mock('../api/_lib/sb.js',()=>({admin:vi.fn(),authUser:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
import {admin,authUser} from '../api/_lib/sb.js';
import handler from '../api/_lib/routes/canvas.js';
import {newDocument,validateDocument,renderDocument} from '../public/canvas/model.js';
import {database,request} from './helpers/db.js';
let sb,user;
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);afterAll(()=>sb.close());
beforeEach(async()=>{user=await sb.user('free');authUser.mockResolvedValue(user);});
const body=()=>({id:null,revision:0,request_id:randomUUID(),document:{...newDocument('Coffee'),watermark:false},consent:true});
const save=b=>handler(request('/canvas','POST',b));
it('saves with enforced attribution, replays, rejects stale writes and restores exact content',async()=>{
 const b=body(),first=await save(b);expect(first.status).toBe(200);let c=await first.json();expect(c.document.watermark).toBe(true);
 expect((await (await save(b)).json()).replayed).toBe(true);
 expect((await save({...b,document:{...b.document,name:'Different'}})).status).toBe(409);
 const next={...b,id:c.id,request_id:randomUUID(),revision:1,document:{...c.document,name:'Changed'}};c=await(await save(next)).json();expect(c.revision).toBe(2);
 expect((await save({...next,request_id:randomUUID()})).status).toBe(409);
 const restored=await(await save({id:c.id,revision:2,restore:1,request_id:randomUUID(),consent:true})).json();expect(restored.document.name).toBe('Coffee');expect(restored.revision).toBe(3);
});
it('keeps projects and versions owner-scoped and rejects direct grants',async()=>{
 const c=await(await save(body())).json();const other=await sb.user('pro');authUser.mockResolvedValue(other);
 expect((await handler(request('/canvas?id='+c.id,'GET'))).status).toBe(404);
 expect((await save({id:c.id,revision:1,restore:1,consent:true,request_id:randomUUID()})).status).toBe(404);
 const grants=(await sb.db.query("select has_table_privilege('authenticated','public.canvas_versions','SELECT') as allowed")).rows;expect(grants[0].allowed).toBe(false);
});
it('bounds projects, revisions and account deletion cascades',async()=>{
 let c=await(await save(body())).json();for(let i=1;i<=12;i++)c=await(await save({id:c.id,revision:c.revision,document:{...c.document,name:'Revision '+i},consent:true,request_id:randomUUID()})).json();expect(c.versions).toHaveLength(10);
 for(let i=0;i<9;i++)expect((await save(body())).status).toBe(200);expect((await save(body())).status).toBe(409);
 await sb.db.query('delete from auth.users where id=$1',[user.id]);expect((await sb.db.query('select count(*)::int as n from canvas_projects where user_id=$1',[user.id])).rows[0].n).toBe(0);
});
it('rejects unknown fields, invalid image data, excessive geometry and unconsented imports',async()=>{
 expect((await save({...body(),consent:false})).status).toBe(400);
 expect((await save({...body(),document:{...newDocument(),provider_key:'not accepted'}})).status).toBe(400);
 expect(()=>validateDocument({...newDocument(),width:Infinity})).toThrow();
 const d=newDocument();d.layers=[{id:'x',type:'text',x:0,y:0,width:500,height:100,rotation:0,opacity:1,fill:'#000000',fontSize:24,font:'serif',bold:false,align:'left',direction:'ltr',text:'<script>alert(1)</script>'}];
 const svg=renderDocument(d);expect(svg).not.toContain('<script>');expect(svg).toContain('&lt;script&gt;');
 d.layers[0].type='image';d.layers[0].src='https://evil.invalid/image.png';d.layers[0].fit='crop';d.layers[0].anchor='xMidYMid';expect(()=>validateDocument(d)).toThrow();
});
it('includes all retained canvas source versions in the bounded account-export phase',async()=>{
 const {default:exportAccount}=await import('../api/_lib/routes/me-export.js');const {gunzipSync}=await import('node:zlib');
 await save(body());
 expect((await exportAccount(request('/me/export','GET'))).status).toBe(409);
 const normal=await exportAccount(request('/me/export','GET',undefined,{'X-BrandForge-Canvas':'canvas-v1'}));expect(normal.status).toBe(200);
 const next=JSON.parse(gunzipSync(Buffer.from(await normal.arrayBuffer())).toString());expect(next.next_kind).toBe('canvas');expect(next.has_more).toBe(true);
 const response=await exportAccount(request('/me/export?kind=canvas&page=0','GET'));expect(response.status).toBe(200);const data=JSON.parse(gunzipSync(Buffer.from(await response.arrayBuffer())).toString());expect(data.data.canvas_versions[0].document.format).toBe('brandforge-canvas');expect(data.has_more).toBe(false);
 authUser.mockResolvedValue(await sb.user('pro'));const other=await exportAccount(request('/me/export?kind=canvas','GET'));expect(JSON.parse(gunzipSync(Buffer.from(await other.arrayBuffer())).toString()).total).toBe(0);
});
it('rejects malformed raster headers and invalid XML text before preview',()=>{
 const d=newDocument();d.layers=[{id:'image-1',type:'image',x:0,y:0,width:100,height:100,rotation:0,opacity:1,fill:'#ffffff',fit:'contain',anchor:'xMidYMid',src:'data:image/png;base64,AAAA'}];expect(()=>validateDocument(d)).toThrow();
 d.layers=[];d.sections.copy='Bad\u0000text';expect(()=>validateDocument(d)).toThrow();
});
