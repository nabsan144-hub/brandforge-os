// Supabase-shaped adapter over real PostgreSQL (PGlite), not invented RPC
// outcomes. Used to exercise the actual handlers and migration functions.
import {PGlite} from '@electric-sql/pglite';
import {readFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
const quote=x=>'"'+String(x).replaceAll('"','""')+'"';
const value=x=>x&&typeof x==='object'?JSON.stringify(x):x;
export async function database(){
 const db=new PGlite();
 await db.exec("create schema auth;create table auth.users(id uuid primary key,email text);create function auth.uid() returns uuid language sql stable as $$select null::uuid$$;create role anon;create role authenticated;create role service_role bypassrls;grant usage on schema public,auth to anon,authenticated,service_role;");
 await db.exec(readFileSync(new URL('../../schema.sql',import.meta.url),'utf8').replace('create extension if not exists pgcrypto;',''));
 const calls=[],faults=new Map();
 class Query{
  constructor(table){this.table=table;this.filters=[];this.orders=[];this.cols='*';this.op='select';this.options={};}
  select(cols='*',opts={}){this.cols=cols;this.options=opts;this.returning=true;return this;}
  eq(k,v){this.filters.push([k,'=',v]);return this;}
  neq(k,v){this.filters.push([k,'<>',v]);return this;}
  gt(k,v){this.filters.push([k,'>',v]);return this;}
  gte(k,v){this.filters.push([k,'>=',v]);return this;}
  lt(k,v){this.filters.push([k,'<',v]);return this;}
  lte(k,v){this.filters.push([k,'<=',v]);return this;}
  is(k,v){this.filters.push([k,'is',v]);return this;}
  in(k,v){this.filters.push([k,'in',v]);return this;}
  ilike(k,v){this.filters.push([k,'ilike',v]);return this;}
  order(k,v={}){this.orders.push([k,v.ascending!==false]);return this;}
  range(a,b){this.offset=a;this.maximum=b-a+1;return this;}
  limit(n){this.maximum=n;return this;}
  insert(v){this.op='insert';this.payload=v;return this;}
  update(v){this.op='update';this.payload=v;return this;}
  delete(){this.op='delete';return this;}
  upsert(v,opts={}){this.op='insert';this.payload=v;this.conflict=opts.onConflict;return this;}
  single(){this.singleMode='required';return this;}
  maybeSingle(){this.singleMode='optional';return this;}
  then(resolve,reject){if(!this.promise)this.promise=this.execute();return this.promise.then(resolve,reject);}
  async execute(){
   calls.push({table:this.table,op:this.op,filters:this.filters,payload:this.payload});
   try{
    const vals=[],bind=v=>{vals.push(value(v));return '$'+vals.length;};
    const where=this.filters.map(([k,op,v])=>op==='is'?quote(k)+' IS '+(v===null?'NULL':'NOT NULL'):op==='in'?(v.length?quote(k)+' IN ('+v.map(bind).join(',')+')':'false'):quote(k)+' '+op+' '+bind(v)).join(' AND ');
    const columns=this.cols==='*'?'*':this.cols.split(',').map(quote).join(',');
    const condition=where?' WHERE '+where:'';let text,count;
    if(this.options.count==='exact')count=Number((await db.query('select count(*) n from public.'+quote(this.table)+condition,vals)).rows[0].n);
    if(this.op==='select')text='select '+columns+' from public.'+quote(this.table)+condition;
    else if(this.op==='delete')text='delete from public.'+quote(this.table)+condition;
    else if(this.op==='update')text='update public.'+quote(this.table)+' set '+Object.entries(this.payload).map(([k,v])=>quote(k)+'='+bind(v)).join(',')+condition;
    else{
     const rows=Array.isArray(this.payload)?this.payload:[this.payload],keys=Object.keys(rows[0]);
     text='insert into public.'+quote(this.table)+'('+keys.map(quote).join(',')+') values '+rows.map(row=>'('+keys.map(k=>bind(row[k])).join(',')+')').join(',');
     if(this.conflict)text+=' on conflict ('+this.conflict.split(',').map(quote).join(',')+') do update set '+keys.map(k=>quote(k)+'=excluded.'+quote(k)).join(',');
    }
    if(this.op==='select'){
     if(this.orders.length)text+=' ORDER BY '+this.orders.map(([k,a])=>quote(k)+(a?' ASC':' DESC')).join(',');
     if(this.maximum!==undefined)text+=' LIMIT '+this.maximum;if(this.offset)text+=' OFFSET '+this.offset;
    }else if(this.returning)text+=' RETURNING '+columns;
    const result=await db.query(text,vals);const rows=result.rows;
    if(this.singleMode==='required'&&rows.length!==1)return {data:null,error:{code:'PGRST116',message:'Expected one row'}};
    return {data:this.options.head?null:this.singleMode?rows[0]||null:this.op==='select'||this.returning?rows:null,error:null,count};
   }catch(e){return {data:null,error:{code:e.code,message:e.message}};}
  }
 }
 const sb={
  db,calls,from:table=>new Query(table),
  failNextRpc:(name,after=false)=>faults.set(name,{after}),
  async rpc(name,args={}){
   calls.push({rpc:name,args});const fault=faults.get(name);if(fault)faults.delete(name);
   try{
    if(fault&&!fault.after)throw new Error('Injected database failure');
    const keys=Object.keys(args),r=await db.query(`select public.${quote(name)}(${keys.map((k,i)=>quote(k)+' => $'+(i+1)).join(',')}) result`,keys.map(k=>value(args[k])));
    if(fault)throw new Error('Injected lost response after commit');
    return {data:r.rows[0].result,error:null};
   }catch(e){return {data:null,error:{code:e.code,message:e.message}};}
  },
  auth:{admin:{async deleteUser(uid){try{await db.query('delete from auth.users where id=$1',[uid]);return {data:{user:null},error:null};}catch(e){return {error:e};}}}},
  storage:{getBucket:async()=>({data:{public:false},error:null}),from:()=>({createSignedUrl:async()=>({data:{signedUrl:'https://storage.example.test/private.zip?signature=test'},error:null})})},
  async user(plan='free'){const id=randomUUID(),email=id+'@example.test';await db.query('insert into auth.users values($1,$2)',[id,email]);if(plan!=='free')await db.query('update profiles set plan=$1 where id=$2',[plan,id]);return {id,email,email_confirmed_at:new Date().toISOString()};},
  close:()=>db.close(),
 };
 return sb;
}
export function request(path,method='GET',body,headers={}){return new Request('https://app.example.test/api'+path,{method,headers:{'Content-Type':'application/json',...headers},...(body===undefined?{}:{body:JSON.stringify(body)})});}
