import {it,expect} from 'vitest';
import {PGlite} from '@electric-sql/pglite';
import {readFileSync,readdirSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
const directory=new URL('../../supabase/migrations/',import.meta.url);
const migrations=readdirSync(directory).filter(x=>x.endsWith('.sql')).sort();
const bootstrap=`create schema auth;create table auth.users(id uuid primary key,email text);create function auth.uid() returns uuid language sql stable as $$select null::uuid$$;create role anon;create role authenticated;create role service_role bypassrls;grant usage on schema public,auth to anon,authenticated,service_role;`;
const sql=f=>readFileSync(new URL(f,directory),'utf8').replace('create extension if not exists pgcrypto;','');
// Separate worker: two simultaneous WASM engines exceed a small CI VM's RAM.
 it('upgrade preserves larger known monthly usage and closes legacy waitlist grants',async()=>{
  const old=new PGlite();await old.exec(bootstrap);for(const m of migrations.slice(0,6))await old.exec(sql(m));const uid=randomUUID();
  await old.query('insert into auth.users values($1,$2)',[uid,'legacy@example.test']);await old.query("insert into usage_monthly values($1,to_char(now(),'YYYYMM'),50)",[uid]);
  await old.exec('alter table waitlist disable row level security;grant all on waitlist to anon,authenticated;');
  for(const m of migrations.slice(6))await old.exec(sql(m));
  expect((await old.query('select generation_totals($1) t',[uid])).rows[0].t.campaigns_this_month).toBe(50);
  expect((await old.query("select has_table_privilege('anon','waitlist','SELECT') p")).rows[0].p).toBe(false);
  await old.close();
 },30000);
