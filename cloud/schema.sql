-- GENERATED from supabase/migrations. Run: node cloud/scripts/sync-schema.mjs

-- ============================================================================
-- BrandForge OS Cloud — initial schema (migration 0001)
-- Run in the Supabase SQL editor, or `supabase db push`.
--
-- SECURITY MODEL (read this before changing any policy)
-- ---------------------------------------------------------------------------
-- * Money/quota tables (usage_monthly, paddle_events, delivery_log) are
--   READ-ONLY to their owner. Only the service role (Vercel handlers) may
--   write them, so a signed-in user cannot grant themselves a paid plan or
--   forge an audit trail with the public anon key.
-- * campaigns: users may SELECT only their own rows. Writes/deletes are
--   service-role-only so the quota path cannot be bypassed.
-- * profiles / user_api_keys: owner-readable; writes go through the server
--   handler (encryption + validation cannot be bypassed).
-- * The quota functions are `security definer` and `REVOKE`d from
--   public/anon/authenticated — they can only be called via service_role.
-- ============================================================================

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- profiles — one row per user (plan, billing, contact)
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users on delete cascade,
  email text,
  plan text not null default 'free',
  plan_status text not null default 'active',
  paddle_customer_id text,
  paddle_subscription_id text,
  billing_updated_at timestamptz,
  whatsapp_phone text,
  created_at timestamptz not null default now()
);

alter table public.profiles add column if not exists email text;
alter table public.profiles add column if not exists paddle_customer_id text;
alter table public.profiles add column if not exists paddle_subscription_id text;
alter table public.profiles add column if not exists billing_updated_at timestamptz;
alter table public.profiles add column if not exists whatsapp_phone text;
create index if not exists idx_profiles_email on public.profiles(email);

-- ---------------------------------------------------------------------------
-- campaigns — generated output per user
-- ---------------------------------------------------------------------------
create table if not exists public.campaigns (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  name text not null,
  product text not null,
  industry text not null default 'General',
  audience text not null default '',
  strategy text,
  copy text,
  seo text,
  research_live boolean not null default false,
  provider text not null default 'offline',
  files jsonb not null default '[]',
  lang text not null default 'en',
  benefits text not null default '',
  created_at timestamptz not null default now()
);

alter table public.campaigns add column if not exists lang text not null default 'en';
alter table public.campaigns add column if not exists benefits text not null default '';

-- ---------------------------------------------------------------------------
-- usage_monthly — atomic quota counter (one row per user per month)
-- ---------------------------------------------------------------------------
create table if not exists public.usage_monthly (
  user_id uuid not null references auth.users on delete cascade,
  yyyymm text not null,
  campaign_count integer not null default 0,
  primary key (user_id, yyyymm)
);

-- ---------------------------------------------------------------------------
-- user_api_keys — BYOK keys, AES-256-GCM encrypted at rest (server-only)
-- ---------------------------------------------------------------------------
create table if not exists public.user_api_keys (
  user_id uuid not null references auth.users on delete cascade,
  provider text not null,
  encrypted_key text not null,
  key_prefix text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, provider)
);

-- ---------------------------------------------------------------------------
-- paddle_events — webhook idempotency (dedupe notifications)
-- ---------------------------------------------------------------------------
create table if not exists public.paddle_events (
  event_id text primary key,
  received_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- delivery_log — WhatsApp delivery audit + per-hour rate-limit bookkeeping
-- ---------------------------------------------------------------------------
create table if not exists public.delivery_log (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  campaign_id uuid not null references campaigns(id) on delete cascade,
  provider text not null,
  status text not null default 'reserved',
  created_at timestamptz not null default now()
);
alter table public.delivery_log add column if not exists status text not null default 'reserved';
create index if not exists idx_delivery_log_user_created on public.delivery_log(user_id, created_at desc);


-- ============================================================================
-- BrandForge OS Cloud — seed (migration 0002)
-- ----------------------------------------------------------------------------
-- Backfill `profiles` for users who already exist in auth.users. The signup
-- trigger (created in 0003) only fires for NEW signups, so without this an
-- existing account would log in to a dashboard with no profile row.
-- Safe to re-run (idempotent).
-- ============================================================================

insert into public.profiles (id, email)
select u.id, lower(u.email)
  from auth.users u
on conflict (id) do update set email = excluded.email;


-- ============================================================================
-- BrandForge OS Cloud — row-level security + quota functions + signup trigger
-- (migration 0003)
-- ============================================================================

-- ---- RLS: enable on all application tables --------------------------------
alter table public.profiles        enable row level security;
alter table public.campaigns       enable row level security;
alter table public.usage_monthly   enable row level security;
alter table public.user_api_keys   enable row level security;
alter table public.paddle_events   enable row level security;
alter table public.delivery_log    enable row level security;

-- ---- profiles: owner reads own row ----------------------------------------
drop policy if exists "own profile" on public.profiles;
create policy "own profile" on public.profiles
  for select using (auth.uid() = id);

-- ---- campaigns: owner reads own rows; writes are service-role-only --------
drop policy if exists "own campaigns read" on public.campaigns;
create policy "own campaigns read" on public.campaigns
  for select using (auth.uid() = user_id);
-- No INSERT/UPDATE/DELETE policy on campaigns. The Vercel handlers
-- authenticate the user, enforce quotas and then write with the server-only
-- key; allowing direct authenticated inserts would bypass limits.

-- ---- usage_monthly: owner reads own counter ------------------------------
drop policy if exists "own usage" on public.usage_monthly;
create policy "own usage" on public.usage_monthly
  for select using (auth.uid() = user_id);

-- ---- user_api_keys: owner reads own (redacted) rows -----------------------
drop policy if exists "own keys" on public.user_api_keys;
create policy "own keys" on public.user_api_keys
  for select using (auth.uid() = user_id);

-- ---- delivery_log: owner reads own deliveries -----------------------------
drop policy if exists "own deliveries" on public.delivery_log;
create policy "own deliveries" on public.delivery_log
  for select using (auth.uid() = user_id);

-- ============================================================================
-- Quota functions
-- ----------------------------------------------------------------------------
-- Atomic plan-quota accounting (fixes the TOCTOU race in the old
-- count-then-insert flow, which let concurrent requests exceed limits).
-- These are `security definer` and only callable by service_role.
-- ============================================================================

-- reserve a campaign slot; increments the monthly counter, then checks both
-- the lifetime and monthly caps and rolls back on violation — all inside one
-- transaction, so two concurrent runs cannot both pass.
drop function if exists public.reserve_campaign_slot(uuid, text, int, int);
create or replace function public.reserve_campaign_slot(
  uid uuid,
  yyyymm text,
  lifetime_limit int,
  monthly_limit int
) returns jsonb language plpgsql security definer set search_path = public as $$
declare
  cnt int;
  lifetime int;
  ret jsonb;
begin
  insert into public.usage_monthly as um (user_id, yyyymm, campaign_count)
  values ($1, $2, 1)
  on conflict on constraint usage_monthly_pkey
  do update set campaign_count = um.campaign_count + 1
  returning campaign_count into cnt;

  -- Lifetime must count ALL campaigns ever created, not just this month's
  -- counter (the old check used `cnt`, so a Free user could exceed the 3
  -- lifetime cap by simply waiting for a new month).
  select count(*) into lifetime from public.campaigns as c where c.user_id = $1;

  if $3 is not null and lifetime > $3 then
    update public.usage_monthly um
       set campaign_count = um.campaign_count - 1
     where um.user_id = $1 and um.yyyymm = $2;
    ret := jsonb_build_object('ok', false, 'code', 'LIMIT_LIFETIME', 'count', lifetime);
  elsif $4 is not null and cnt > $4 then
    update public.usage_monthly um
       set campaign_count = um.campaign_count - 1
     where um.user_id = $1 and um.yyyymm = $2;
    ret := jsonb_build_object('ok', false, 'code', 'LIMIT_MONTHLY', 'count', cnt);
  else
    ret := jsonb_build_object('ok', true, 'count', cnt);
  end if;
  return ret;
end $$;

drop function if exists public.release_campaign_slot(uuid, text);
create or replace function public.release_campaign_slot(uid uuid, yyyymm text)
returns void language plpgsql security definer set search_path = public as $$
begin
  update public.usage_monthly um
     set campaign_count = greatest(0, um.campaign_count - 1)
   where um.user_id = $1 and um.yyyymm = $2;
end $$;

-- Lifetime enforcement must happen AFTER the campaign row exists — the
-- reserve-time count raced because insert runs in a later transaction. An
-- advisory xact lock serializes concurrent enforcers per user, and if the cap
-- is exceeded the just-inserted campaign is deleted.
drop function if exists public.enforce_lifetime_cap(uuid, uuid, int);
create or replace function public.enforce_lifetime_cap(uid uuid, cid uuid, lifetime_limit int)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  lifetime int;
begin
  perform pg_advisory_xact_lock(hashtext('vg_lifetime_' || $1::text));
  select count(*) into lifetime from public.campaigns as c where c.user_id = $1;
  if $3 is not null and lifetime > $3 then
    delete from public.campaigns where id = $2 and user_id = $1;
    return jsonb_build_object('ok', false, 'count', lifetime - 1);
  end if;
  return jsonb_build_object('ok', true, 'count', lifetime);
end $$;

-- Reserve a delivery attempt under a per-user advisory lock. Counting first
-- and inserting after the provider call allowed concurrent requests to all
-- observe the same remaining allowance and exceed the 10/hour limit.
drop function if exists public.reserve_delivery_slot(uuid, uuid, text, int);
create or replace function public.reserve_delivery_slot(uid uuid, cid uuid, p text, max_per_hour int)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  recent_count int;
  reservation_id uuid := gen_random_uuid();
begin
  if $4 is null or $4 < 1 then
    return jsonb_build_object('ok', false, 'code', 'INVALID_LIMIT');
  end if;
  perform pg_advisory_xact_lock(hashtext('vg_delivery_' || $1::text));
  select count(*) into recent_count
    from public.delivery_log
   where user_id = $1 and created_at >= now() - interval '1 hour';
  if recent_count >= $4 then
    return jsonb_build_object('ok', false, 'code', 'LIMIT_HOURLY', 'count', recent_count);
  end if;
  insert into public.delivery_log (id, user_id, campaign_id, provider, status)
  values (reservation_id, $1, $2, $3, 'reserved');
  return jsonb_build_object('ok', true, 'id', reservation_id);
end $$;

-- These security-definer quota functions are called only by the trusted
-- service-role client. Do not expose arbitrary uid/cid arguments to browsers.
revoke execute on function public.reserve_campaign_slot(uuid, text, int, int) from public, anon, authenticated;
revoke execute on function public.release_campaign_slot(uuid, text) from public, anon, authenticated;
revoke execute on function public.enforce_lifetime_cap(uuid, uuid, int) from public, anon, authenticated;
revoke execute on function public.reserve_delivery_slot(uuid, uuid, text, int) from public, anon, authenticated;
grant execute on function public.reserve_campaign_slot(uuid, text, int, int) to service_role;
grant execute on function public.release_campaign_slot(uuid, text) to service_role;
grant execute on function public.enforce_lifetime_cap(uuid, uuid, int) to service_role;
grant execute on function public.reserve_delivery_slot(uuid, uuid, text, int) to service_role;

-- ============================================================================
-- auto-create profile on signup
-- ============================================================================
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email) values (new.id, lower(new.email))
  on conflict (id) do update set email = excluded.email;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert or update of email on auth.users
  for each row execute function public.handle_new_user();


-- ============================================================================
-- BrandForge OS Cloud — BYOK primary-key repair (migration 0004)
-- ----------------------------------------------------------------------------
-- user_api_keys stores ONE key PER provider, so its primary key is
-- (user_id, provider). Installs created with the old single-column
-- PK (user_id) could not save a second provider's key (PK violation the
-- ON CONFLICT target couldn't absorb). This repairs existing installs.
-- Idempotent: only fires when the PK is still exactly PRIMARY KEY (user_id).
-- ============================================================================

do $$
begin
  if exists (
    select 1 from pg_constraint
    where conname = 'user_api_keys_pkey'
      and contype = 'p'
      and pg_get_constraintdef(oid) = 'PRIMARY KEY (user_id)'
  ) then
    alter table public.user_api_keys drop constraint user_api_keys_pkey;
    alter table public.user_api_keys add primary key (user_id, provider);
  end if;
end $$;


-- ============================================================================
-- BrandForge OS Cloud — waitlist table (migration 0005)
-- ----------------------------------------------------------------------------
-- The marketing waitlist used to post to FormSubmit.co with a placeholder inbox
-- (YOUR-EMAIL@gmail.com), so every signup was silently lost (audit §1.1/§1.4).
-- This gives the cloud /api/waitlist endpoint a real table to write into.
-- The public HTTP endpoint uses the service role. RLS is ENABLED with no
-- browser policies; explicit revoked grants provide a second boundary.
-- Idempotent — safe to re-run.
-- ============================================================================

create table if not exists public.waitlist (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  tier text not null default 'undecided' check (tier in ('owner','agency_source','undecided')),
  created_at timestamptz not null default now()
);
create index if not exists idx_waitlist_created on public.waitlist(created_at desc);

alter table public.waitlist enable row level security;
revoke all on public.waitlist from public,anon,authenticated;
grant select,insert,update,delete on public.waitlist to service_role;


-- ============================================================================
-- BrandForge OS Cloud — distributed rate limiting (migration 0006)
-- ----------------------------------------------------------------------------
-- Replaces the optional Upstash Redis counter with the Supabase Postgres we
-- already own, so per-IP / per-user rate limits work across every Vercel
-- serverless function with NO second provider, NO extra cost, and no Upstash
-- one-free-database constraint. Upstash remains only an optional opt-in
-- fallback in cloud/api/_lib/limit.js.
--
-- `bf_rate_limit` is a SINGLE atomic INSERT ... ON CONFLICT DO UPDATE, so two
-- concurrent requests can never double-count or race past the limit. Rows are
-- expired in place (n resets to 1 when expires_at passes, sliding-window-ish
-- fixed window), and `bf_rate_limit_gc()` sweeps long-dead rows for storage
-- hygiene (call it from a scheduled/pg_cron job, or invoke occasionally).
--
-- The function is `security definer` and only callable by service_role (the
-- trusted serverless client), so browsers and the anon key can neither read
-- nor abuse it. Idempotent — safe to re-run.
-- ============================================================================

create table if not exists public.rate_limits (
  bucket_key text primary key,
  n integer not null default 0,
  expires_at timestamptz not null default now()
);
create index if not exists idx_rate_limits_expires on public.rate_limits(expires_at);

-- Atomic fixed-window counter. Returns true while n <= lim, false after.
create or replace function public.bf_rate_limit(
  bucket text,
  key text,
  lim integer,
  win integer
) returns boolean
language sql
security definer
set search_path = public
as $$
  with upsert as (
    insert into public.rate_limits as r (bucket_key, n, expires_at)
    values (
      'bf:' || bucket || ':' || left(key, 80),
      1,
      now() + make_interval(secs => greatest(win, 1))
    )
    on conflict (bucket_key) do update
      set n = case when r.expires_at <= now() then 1 else r.n + 1 end,
          expires_at = case when r.expires_at <= now() then excluded.expires_at else r.expires_at end
    returning n
  )
  select n <= lim from upsert;
$$;

-- Garbage-collect windows that ended more than a day ago. Returns rows deleted.
create or replace function public.bf_rate_limit_gc() returns integer
language sql
security definer
set search_path = public
as $$
  with deleted as (
    delete from public.rate_limits
    where expires_at < now() - interval '1 day'
    returning 1
  )
  select count(*)::integer from deleted;
$$;

-- service_role only — same blast radius as the quota functions in 0003.
revoke execute on function public.bf_rate_limit(text, text, int, int) from public, anon, authenticated;
revoke execute on function public.bf_rate_limit_gc() from public, anon, authenticated;
grant execute on function public.bf_rate_limit(text, text, int, int) to service_role;
grant execute on function public.bf_rate_limit_gc() to service_role;

revoke all on table public.rate_limits from public, anon, authenticated;
grant all on table public.rate_limits to service_role;


-- v1.4: storage deletion is NOT a refund of consumed generation.
-- Apply after 0001..0006. All mutations are server-only.
alter table public.waitlist enable row level security;
revoke all on public.waitlist from public, anon, authenticated;
grant select, insert, update, delete on public.waitlist to service_role;
-- Encrypted keys are also server-only: the browser uses /api/me/keys.
revoke all on public.user_api_keys from public, anon, authenticated;
grant select, insert, update, delete on public.user_api_keys to service_role;

create table if not exists public.generation_usage (
  id uuid primary key,
  user_id uuid not null references auth.users on delete cascade,
  campaign_id uuid references public.campaigns(id) on delete set null,
  input_hash text not null default '',
  status text not null check (status in ('reserved','completed','failed')),
  units integer not null default 1 check (units > 0),
  yyyymm text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '5 minutes'),
  completed_at timestamptz,
  provider text,
  failure_code text,
  provider_usage jsonb not null default '{}'
);
create index if not exists generation_usage_user_status on public.generation_usage(user_id,status,yyyymm);
alter table public.generation_usage enable row level security;
revoke all on public.generation_usage from public, anon, authenticated;
grant select, insert, update, delete on public.generation_usage to service_role;

-- Preserve known prelaunch usage. Deleted rows cannot be reconstructed; do not
-- invent a history. Existing campaign IDs make this backfill idempotent.
insert into public.generation_usage(id,user_id,campaign_id,status,yyyymm,created_at,completed_at)
select id,user_id,id,'completed',to_char(created_at at time zone 'UTC','YYYYMM'),created_at,created_at
from public.campaigns on conflict on constraint generation_usage_pkey do nothing;

-- Retain a larger known legacy monthly total as a summary, not invented
-- campaign rows. This does not reconstruct already-refunded/deleted history.
insert into public.generation_usage(id,user_id,input_hash,status,units,yyyymm,created_at,completed_at)
select md5('legacy:'||u.user_id::text||':'||u.yyyymm)::uuid,u.user_id,'legacy-summary','completed',
 u.campaign_count-coalesce(g.n,0),u.yyyymm,to_date(u.yyyymm||'01','YYYYMMDD')::timestamptz,to_date(u.yyyymm||'01','YYYYMMDD')::timestamptz
from public.usage_monthly u left join (select user_id,yyyymm,sum(units)::integer as n from public.generation_usage where status='completed' group by user_id,yyyymm) g
 on g.user_id=u.user_id and g.yyyymm=u.yyyymm
where u.campaign_count>coalesce(g.n,0) and u.yyyymm ~ '^[0-9]{4}(0[1-9]|1[0-2])$'
on conflict on constraint generation_usage_pkey do nothing;

alter table public.campaigns add column if not exists brief jsonb not null default '{}';
alter table public.campaigns add column if not exists stage_status jsonb not null default '{}';
alter table public.campaigns add column if not exists revision integer not null default 1;
alter table public.campaigns add column if not exists updated_at timestamptz not null default now();

-- Retire the unsafe old API. An older deployment must fail closed instead of
-- decrementing consumed usage after this migration.
drop function if exists public.reserve_campaign_slot(uuid,text,int,int);
drop function if exists public.release_campaign_slot(uuid,text);
drop function if exists public.enforce_lifetime_cap(uuid,uuid,int);

create or replace function public.reserve_generation(
  p_uid uuid, p_id uuid, p_hash text, p_lifetime_limit integer,
  p_monthly_limit integer, p_daily_limit integer default 200,
  p_concurrency integer default 2
) returns jsonb language plpgsql security definer set search_path=public as $$
declare prior public.generation_usage; life integer; month_count integer;
  daily_count integer; inflight integer; m text:=to_char(now() at time zone 'UTC','YYYYMM');
begin
  if p_uid is null or p_id is null or length(p_hash) <> 64 or
     p_daily_limit not between 1 and 1000 or p_concurrency not between 1 and 10 or
     (p_lifetime_limit is not null and p_lifetime_limit < 1) or
     (p_monthly_limit is not null and p_monthly_limit < 1) then
    return jsonb_build_object('ok',false,'code','INVALID_RESERVATION');
  end if;
  perform pg_advisory_xact_lock(hashtext('bf_generation_'||p_uid::text));
  update public.generation_usage set status='failed',failure_code='RESERVATION_EXPIRED'
    where user_id=p_uid and status='reserved' and expires_at<=now();
  select * into prior from public.generation_usage where id=p_id;
  if found then
    if prior.user_id<>p_uid or prior.input_hash<>p_hash then
      return jsonb_build_object('ok',false,'code','IDEMPOTENCY_CONFLICT');
    end if;
    return jsonb_build_object('ok',false,'code',case when prior.status='completed' then 'ALREADY_COMPLETED' when prior.status='failed' then 'ALREADY_FAILED' else 'ALREADY_RESERVED' end,'campaign_id',prior.campaign_id);
  end if;
  select coalesce(sum(units),0),
    coalesce(sum(units) filter(where yyyymm=m),0),
    count(*) filter(where created_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'),
    count(*) filter(where status='reserved')
    into life,month_count,daily_count,inflight
    from public.generation_usage where user_id=p_uid and status in ('reserved','completed');
  if p_lifetime_limit is not null and life>=p_lifetime_limit then
    return jsonb_build_object('ok',false,'code','LIMIT_LIFETIME');
  elsif p_monthly_limit is not null and month_count>=p_monthly_limit then
    return jsonb_build_object('ok',false,'code','LIMIT_MONTHLY');
  elsif daily_count>=p_daily_limit then
    return jsonb_build_object('ok',false,'code','LIMIT_DAILY');
  elsif inflight>=p_concurrency then
    return jsonb_build_object('ok',false,'code','LIMIT_CONCURRENT');
  end if;
  insert into public.generation_usage(id,user_id,input_hash,status,yyyymm)
    values(p_id,p_uid,p_hash,'reserved',m);
  return jsonb_build_object('ok',true,'reservation_id',p_id);
end $$;

create or replace function public.fail_generation(p_uid uuid,p_id uuid,p_code text)
returns boolean language plpgsql security definer set search_path=public as $$
declare affected integer;
begin
  update public.generation_usage set status='failed',failure_code=left(p_code,80)
  where id=p_id and user_id=p_uid and status='reserved';
  get diagnostics affected=row_count;
  return affected=1;
end $$;

-- Save campaign + finalize its reservation in ONE transaction. A lost HTTP
-- response can be retried with the same reservation, without a second charge.
create or replace function public.complete_generation(p_uid uuid,p_id uuid,p_campaign jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare r public.generation_usage; cid uuid; nm text;
begin
  perform pg_advisory_xact_lock(hashtext('bf_generation_'||p_uid::text));
  select * into r from public.generation_usage where id=p_id and user_id=p_uid for update;
  if not found then raise exception 'Reservation not found'; end if;
  if r.status='completed' then
    return jsonb_build_object('id',r.campaign_id,'replayed',true);
  end if;
  if r.status<>'reserved' or r.expires_at<=now() then raise exception 'Reservation expired or failed'; end if;
  if jsonb_typeof(p_campaign->'files') <> 'array' or length(p_campaign->>'product')=0 then
    raise exception 'Invalid campaign';
  end if;
  nm:=left(coalesce(nullif(p_campaign->>'name',''),p_campaign->>'product'),80);
  insert into public.campaigns(user_id,name,product,industry,audience,benefits,lang,strategy,copy,seo,
    research_live,provider,files,brief,stage_status)
  values(p_uid,nm,left(p_campaign->>'product',80),left(coalesce(p_campaign->>'industry',''),80),
    left(coalesce(p_campaign->>'audience',''),120),left(coalesce(p_campaign->>'benefits',''),500),
    coalesce(p_campaign->>'lang','en'),p_campaign->>'strategy',p_campaign->>'copy',p_campaign->>'seo',
    false,coalesce(p_campaign->>'provider','offline'),p_campaign->'files',
    coalesce(p_campaign->'brief','{}'::jsonb),coalesce(p_campaign->'stage_status','{}'::jsonb)) returning id into cid;
  update public.generation_usage set status='completed',campaign_id=cid,completed_at=now(),provider=p_campaign->>'provider',provider_usage=coalesce(p_campaign->'provider_usage','{}'::jsonb)
    where id=p_id;
  return jsonb_build_object('id',cid,'name',nm,'replayed',false);
end $$;

create or replace function public.generation_totals(p_uid uuid)
returns jsonb language sql security definer set search_path=public as $$
 select jsonb_build_object(
  'campaigns_lifetime',coalesce(sum(units) filter(where status='completed'),0),
  'campaigns_this_month',coalesce(sum(units) filter(where status='completed' and yyyymm=to_char(now() at time zone 'UTC','YYYYMM')),0),
  'reserved',count(*) filter(where status='reserved' and expires_at>now()),
  'resets_at',date_trunc('month',now() at time zone 'UTC')+interval '1 month')
 from public.generation_usage where user_id=p_uid;
$$;

revoke execute on function public.reserve_generation(uuid,uuid,text,int,int,int,int) from public,anon,authenticated;
revoke execute on function public.fail_generation(uuid,uuid,text) from public,anon,authenticated;
revoke execute on function public.complete_generation(uuid,uuid,jsonb) from public,anon,authenticated;
revoke execute on function public.generation_totals(uuid) from public,anon,authenticated;
grant execute on function public.reserve_generation(uuid,uuid,text,int,int,int,int) to service_role;
grant execute on function public.fail_generation(uuid,uuid,text) to service_role;
grant execute on function public.complete_generation(uuid,uuid,jsonb) to service_role;
grant execute on function public.generation_totals(uuid) to service_role;

-- Do not rely on Supabase's historical default grants.
grant select,insert,update,delete on public.profiles,public.campaigns,public.usage_monthly,public.delivery_log,public.paddle_events to service_role;
revoke all on public.profiles,public.campaigns from anon,authenticated;
grant select on public.profiles,public.campaigns to authenticated;
drop policy if exists "own keys" on public.user_api_keys;


-- v1.4 commerce: one-time desktop orders are NOT Cloud plans.
-- Owner confirmed this is prelaunch, with no paid legacy commitments.
alter table public.profiles add column if not exists deletion_pending boolean not null default false;
alter table public.profiles add column if not exists past_due_since timestamptz;
update public.profiles set plan='free',plan_status='active' where plan in ('desktop_solo','desktop_agency');

create table if not exists public.billing_subscriptions (
 id text primary key, user_id uuid references auth.users on delete set null,
 customer_id text not null, plan text not null check(plan in ('pro','agency')),
 status text not null, price_id text, billing_interval text,
 occurred_at timestamptz not null, updated_at timestamptz not null default now()
);
create index if not exists billing_subscriptions_user on public.billing_subscriptions(user_id,status);

create table if not exists public.checkout_intents (
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,
 plan text not null,billing_interval text not null,transaction_id text,
 state text not null default 'creating',created_at timestamptz not null default now(),
 expires_at timestamptz not null default now()+interval '30 minutes'
);
create index if not exists checkout_intents_user on public.checkout_intents(user_id,created_at desc);

create table if not exists public.billing_operations (
 user_id uuid primary key references auth.users on delete cascade,
 operation_id uuid not null,expires_at timestamptz not null
);

create table if not exists public.desktop_orders (
 transaction_id text primary key,customer_id text not null,email text not null,
 tier text not null check(tier in ('owner','agency_source')),
 status text not null default 'paid' check(status in ('paid','refunded','disputed')),
 amount_total bigint not null default 0, currency text not null default 'USD',
 release_path text not null,created_at timestamptz not null default now(),
 occurred_at timestamptz not null,delivery_nonce uuid not null default gen_random_uuid(),
 delivered_at timestamptz,delivery_url text,delivery_expires_at timestamptz,
 delivery_error text
);
create index if not exists desktop_orders_customer on public.desktop_orders(customer_id);
create table if not exists public.payment_adjustments (
 id text primary key,transaction_id text not null,action text not null,status text not null,
 adjustment_type text,amount_total bigint not null default 0,occurred_at timestamptz not null
);

-- All billing records and operations are private to service-role handlers.
alter table public.billing_subscriptions enable row level security;
alter table public.checkout_intents enable row level security;
alter table public.billing_operations enable row level security;
alter table public.desktop_orders enable row level security;
alter table public.payment_adjustments enable row level security;
revoke all on public.billing_subscriptions,public.checkout_intents,public.billing_operations,public.desktop_orders,public.payment_adjustments from public,anon,authenticated;
grant select,insert,update,delete on public.billing_subscriptions,public.checkout_intents,public.billing_operations,public.desktop_orders,public.payment_adjustments to service_role;

create or replace function public.begin_checkout(p_uid uuid,p_plan text,p_interval text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare prior public.checkout_intents; cid uuid;
begin
 perform pg_advisory_xact_lock(hashtext('bf_billing_'||p_uid::text));
 if exists(select 1 from public.profiles where id=p_uid and deletion_pending) then
  return jsonb_build_object('ok',false,'code','DELETION_PENDING');
 end if;
 if exists(select 1 from public.billing_subscriptions where user_id=p_uid and status in ('active','trialing','past_due','paused')) or
    exists(select 1 from public.profiles where id=p_uid and paddle_subscription_id is not null) then
  return jsonb_build_object('ok',false,'code','SUBSCRIPTION_EXISTS');
 end if;
 select * into prior from public.checkout_intents where user_id=p_uid and state in ('creating','open','uncertain') order by created_at desc limit 1;
 if found then
  if prior.plan<>p_plan or prior.billing_interval<>p_interval then
   return jsonb_build_object('ok',false,'code','CHECKOUT_ALREADY_OPEN');
  end if;
  return jsonb_build_object('ok',false,'code','CHECKOUT_PENDING','id',prior.id,'transaction_id',prior.transaction_id);
 end if;
 if p_plan not in ('pro','agency') or p_interval not in ('month','year') then
  return jsonb_build_object('ok',false,'code','INVALID_PLAN');
 end if;
 insert into public.checkout_intents(user_id,plan,billing_interval) values(p_uid,p_plan,p_interval) returning id into cid;
 return jsonb_build_object('ok',true,'id',cid);
end $$;

create or replace function public.begin_billing_operation(p_uid uuid,p_id uuid)
returns boolean language plpgsql security definer set search_path=public as $$
begin
 perform pg_advisory_xact_lock(hashtext('bf_billing_'||p_uid::text));
 if exists(select 1 from public.billing_operations where user_id=p_uid and expires_at>now()) then return false; end if;
 insert into public.billing_operations(user_id,operation_id,expires_at) values(p_uid,p_id,now()+interval '5 minutes')
 on conflict on constraint billing_operations_pkey do update set operation_id=excluded.operation_id,expires_at=excluded.expires_at;
 return true;
end $$;

-- Atomic event ordering prevents delayed or parallel webhooks from rolling
-- an account back. Store ALL subscriptions, so duplicates are detectable.
create or replace function public.apply_subscription(p_uid uuid,p_id text,p_customer text,p_plan text,p_status text,p_price text,p_interval text,p_at timestamptz)
returns boolean language plpgsql security definer set search_path=public as $$
declare chosen public.billing_subscriptions; affected integer;
begin
 perform pg_advisory_xact_lock(hashtext('bf_subscription_'||p_id));
 perform pg_advisory_xact_lock(hashtext('bf_billing_'||p_uid::text));
 if exists(select 1 from public.billing_subscriptions where id=p_id and user_id is distinct from p_uid) then
  raise exception 'Subscription account mismatch';
 end if;
 insert into public.billing_subscriptions(id,user_id,customer_id,plan,status,price_id,billing_interval,occurred_at)
 values(p_id,p_uid,p_customer,p_plan,p_status,p_price,p_interval,p_at)
 on conflict on constraint billing_subscriptions_pkey do update set status=excluded.status,plan=excluded.plan,
 price_id=excluded.price_id,billing_interval=excluded.billing_interval,occurred_at=excluded.occurred_at,updated_at=now()
 where billing_subscriptions.occurred_at<=excluded.occurred_at;
 get diagnostics affected=row_count;
 if affected=0 then return false; end if;
 select * into chosen from public.billing_subscriptions where user_id=p_uid and status in ('active','trialing','past_due')
 order by case status when 'past_due' then 0 else 1 end desc,case plan when 'agency' then 2 else 1 end desc,occurred_at desc limit 1;
 if found then
  update public.profiles set plan=chosen.plan,plan_status=chosen.status,paddle_customer_id=p_customer,
    paddle_subscription_id=chosen.id,billing_updated_at=greatest(coalesce(billing_updated_at,p_at),p_at),
    past_due_since=case when chosen.status='past_due' then coalesce(past_due_since,chosen.occurred_at) else null end
    where id=p_uid;
 else
  update public.profiles set plan='free',plan_status='active',paddle_customer_id=p_customer,
    paddle_subscription_id=null,past_due_since=null,billing_updated_at=greatest(coalesce(billing_updated_at,p_at),p_at) where id=p_uid;
 end if;
 update public.checkout_intents set state='completed' where user_id=p_uid and state in ('open','creating','uncertain');
 return true;
end $$;

create or replace function public.desktop_order_state(p_tid text,p_amount bigint)
returns text language sql stable security definer set search_path=public as $$
 select case
  when exists(select 1 from public.payment_adjustments a where a.transaction_id=p_tid and a.action='refund' and a.status='approved' and a.adjustment_type='full')
    or (p_amount>0 and (select coalesce(sum(a.amount_total),0) from public.payment_adjustments a where a.transaction_id=p_tid and a.action='refund' and a.status='approved')>=p_amount) then 'refunded'
  when (select a.action from public.payment_adjustments a where a.transaction_id=p_tid and a.status='approved' and a.action in ('chargeback','chargeback_warning','chargeback_reverse') order by a.occurred_at desc,a.id desc limit 1) in ('chargeback','chargeback_warning') then 'disputed'
  else 'paid' end;
$$;
revoke execute on function public.desktop_order_state(text,bigint) from public,anon,authenticated;
grant execute on function public.desktop_order_state(text,bigint) to service_role;

create or replace function public.apply_payment_adjustment(p_data jsonb)
returns void language plpgsql security definer set search_path=public as $$
declare tid text:=p_data->>'transaction_id';
begin
 perform pg_advisory_xact_lock(hashtext('bf_order_'||tid));
 insert into public.payment_adjustments(id,transaction_id,action,status,adjustment_type,amount_total,occurred_at)
 values(p_data->>'id',tid,p_data->>'action',p_data->>'status',p_data->>'type',coalesce((p_data->>'amount_total')::bigint,0),(p_data->>'occurred_at')::timestamptz)
 on conflict on constraint payment_adjustments_pkey do update set status=excluded.status,amount_total=excluded.amount_total,occurred_at=excluded.occurred_at
 where payment_adjustments.occurred_at<=excluded.occurred_at;
 -- Approved cumulative/full refunds revoke downloads. Dispute reversal
 -- restores access only if there is no approved full/cumulative refund.
 update public.desktop_orders o set status=public.desktop_order_state(tid,o.amount_total) where o.transaction_id=tid;
end $$;

revoke execute on function public.begin_checkout(uuid,text,text),public.begin_billing_operation(uuid,uuid),public.apply_subscription(uuid,text,text,text,text,text,text,timestamptz),public.apply_payment_adjustment(jsonb) from public,anon,authenticated;
grant execute on function public.begin_checkout(uuid,text,text),public.begin_billing_operation(uuid,uuid),public.apply_subscription(uuid,text,text,text,text,text,text,timestamptz),public.apply_payment_adjustment(jsonb) to service_role;

-- A crashed webhook worker must not leave an event permanently "processed".
alter table public.paddle_events add column if not exists status text not null default 'completed';
alter table public.paddle_events add column if not exists lease_until timestamptz;
create or replace function public.claim_paddle_event(p_id text)
returns text language plpgsql security definer set search_path=public as $$
declare n integer; state text;
begin
 insert into public.paddle_events(event_id,status,lease_until) values(p_id,'processing',now()+interval '5 minutes')
 on conflict on constraint paddle_events_pkey do update set status='processing',lease_until=excluded.lease_until
 where paddle_events.status='failed' or (paddle_events.status='processing' and paddle_events.lease_until<now());
 get diagnostics n=row_count;
 if n=1 then return 'claimed'; end if;
 select status into state from public.paddle_events where event_id=p_id;
 return state;
end $$;

create or replace function public.record_desktop_order(p_data jsonb)
returns void language plpgsql security definer set search_path=public as $$
declare tid text:=p_data->>'transaction_id'; state text:='paid';
begin
 perform pg_advisory_xact_lock(hashtext('bf_order_'||tid));
 state:=public.desktop_order_state(tid,(p_data->>'amount_total')::bigint);
 insert into public.desktop_orders(transaction_id,customer_id,email,tier,status,amount_total,currency,release_path,occurred_at)
 values(tid,p_data->>'customer_id',lower(p_data->>'email'),p_data->>'tier',state,(p_data->>'amount_total')::bigint,p_data->>'currency',p_data->>'release_path',(p_data->>'occurred_at')::timestamptz)
 on conflict on constraint desktop_orders_pkey do nothing;
end $$;
alter table public.desktop_orders add column if not exists delivery_claimed_until timestamptz;
create or replace function public.claim_desktop_delivery(p_id text)
returns boolean language plpgsql security definer set search_path=public as $$
declare n integer;
begin
 update public.desktop_orders set delivery_claimed_until=now()+interval '5 minutes' where transaction_id=p_id and status='paid' and delivered_at is null and (delivery_claimed_until is null or delivery_claimed_until<now());
 get diagnostics n=row_count;return n=1;
end $$;
revoke execute on function public.claim_paddle_event(text),public.record_desktop_order(jsonb),public.claim_desktop_delivery(text) from public,anon,authenticated;
grant execute on function public.claim_paddle_event(text),public.record_desktop_order(jsonb),public.claim_desktop_delivery(text) to service_role;

create or replace function public.request_desktop_redelivery(p_id text)
returns boolean language plpgsql security definer set search_path=public as $$
declare n integer;
begin
 update public.desktop_orders set delivered_at=null,delivery_nonce=gen_random_uuid() where transaction_id=p_id and status='paid' and delivered_at<now()-interval '24 hours' and (delivery_claimed_until is null or delivery_claimed_until<now());
 get diagnostics n=row_count;return n=1;
end $$;
revoke execute on function public.request_desktop_redelivery(text) from public,anon,authenticated;
grant execute on function public.request_desktop_redelivery(text) to service_role;
alter table public.paddle_events add column if not exists event_type text;
alter table public.paddle_events add column if not exists entity_id text;
alter table public.paddle_events add column if not exists last_error text;

-- Email reuse is not a billing ownership grant. Keep the customer binding
-- even after account deletion (user_id becomes NULL and cannot be reclaimed).
create table if not exists public.billing_customers (
 customer_id text primary key,user_id uuid references auth.users on delete set null,created_at timestamptz not null default now()
);
alter table public.billing_customers enable row level security;
revoke all on public.billing_customers from public,anon,authenticated;
grant select,insert,update,delete on public.billing_customers to service_role;
insert into public.billing_customers(customer_id,user_id)
 select p.paddle_customer_id,p.id from public.profiles p where p.paddle_customer_id is not null and not exists(select 1 from public.profiles other where other.paddle_customer_id=p.paddle_customer_id and other.id<>p.id)
 on conflict on constraint billing_customers_pkey do nothing;
create or replace function public.claim_billing_customer(p_uid uuid,p_customer text)
returns boolean language plpgsql security definer set search_path=public as $$
declare owner uuid;
begin
 perform pg_advisory_xact_lock(hashtext('bf_customer_'||p_customer));
 select user_id into owner from public.billing_customers where customer_id=p_customer;
 if found then return owner is not distinct from p_uid; end if;
 if exists(select 1 from public.profiles where paddle_customer_id=p_customer and id<>p_uid)
   or exists(select 1 from public.billing_subscriptions where customer_id=p_customer and user_id is distinct from p_uid) then return false; end if;
 insert into public.billing_customers(customer_id,user_id) values(p_customer,p_uid);
 return true;
end $$;
revoke execute on function public.claim_billing_customer(uuid,text) from public,anon,authenticated;
grant execute on function public.claim_billing_customer(uuid,text) to service_role;


-- Reusable client brand context. Browser writes cannot bypass validation.
create table if not exists public.brand_profiles (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users on delete cascade,
 name text not null, data jsonb not null default '{}',created_at timestamptz not null default now(),updated_at timestamptz not null default now()
);
create index if not exists brand_profiles_owner on public.brand_profiles(user_id,updated_at desc);
alter table public.brand_profiles enable row level security;
revoke all on public.brand_profiles from public,anon,authenticated;
grant select,insert,update,delete on public.brand_profiles to service_role;

-- Opt-in feedback, not a claim of real customer traction. Does not contain
-- prompts, contacts, images or keys. Account deletion cascades these records.
create table if not exists public.product_feedback (
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,
 campaign_id uuid references public.campaigns on delete set null,
 usable boolean,minutes_saved integer check(minutes_saved between 0 and 600),
 note text check(length(note)<=1000),created_at timestamptz not null default now()
);
alter table public.product_feedback enable row level security;
revoke all on public.product_feedback from public,anon,authenticated;
grant select,insert,update,delete on public.product_feedback to service_role;

create table if not exists public.campaign_revisions (
 campaign_id uuid not null references public.campaigns on delete cascade,
 user_id uuid not null references auth.users on delete cascade,
 revision integer not null, snapshot jsonb not null,created_at timestamptz not null default now(),
 primary key(campaign_id,revision)
);
alter table public.campaign_revisions enable row level security;
revoke all on public.campaign_revisions from public,anon,authenticated;
grant select,insert,update,delete on public.campaign_revisions to service_role;

create or replace function public.edit_campaign(p_uid uuid,p_id uuid,p_revision integer,p_changes jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; statuses jsonb; key text;
begin
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 if c.revision<>p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 insert into public.campaign_revisions(campaign_id,user_id,revision,snapshot) values(p_id,p_uid,c.revision,to_jsonb(c)-'files'-'brief');
 statuses:=c.stage_status;
 foreach key in array array['strategy','copy','seo'] loop
  if p_changes ? key then statuses:=jsonb_set(statuses,array[key],'{"state":"edited","provider":"human"}'::jsonb); end if;
 end loop;
 update public.campaigns set name=coalesce(p_changes->>'name',c.name),strategy=coalesce(p_changes->>'strategy',c.strategy),copy=coalesce(p_changes->>'copy',c.copy),seo=coalesce(p_changes->>'seo',c.seo),stage_status=statuses,revision=c.revision+1,updated_at=now() where id=p_id;
 -- Retention is explicit in the UI: the last ten saved versions.
 delete from public.campaign_revisions where campaign_id=p_id and revision<c.revision-9;
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision+1);
end $$;

create or replace function public.save_brand(p_uid uuid,p_id uuid,p_name text,p_data jsonb)
returns uuid language plpgsql security definer set search_path=public as $$
declare result uuid;
begin
 perform pg_advisory_xact_lock(hashtext('bf_brands_'||p_uid::text));
 if length(p_name) not between 1 and 80 or octet_length(p_data::text)>100000 then raise exception 'Invalid brand'; end if;
 if p_id is not null then
  update public.brand_profiles set name=p_name,data=p_data,updated_at=now() where id=p_id and user_id=p_uid returning id into result;
  if result is null then raise exception 'Brand not found'; end if;
 else
  if (select count(*) from public.brand_profiles where user_id=p_uid)>=100 then raise exception '100 saved brand limit reached'; end if;
  insert into public.brand_profiles(user_id,name,data) values(p_uid,p_name,p_data) returning id into result;
 end if;
 return result;
end $$;
revoke execute on function public.edit_campaign(uuid,uuid,int,jsonb),public.save_brand(uuid,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.edit_campaign(uuid,uuid,int,jsonb),public.save_brand(uuid,uuid,text,jsonb) to service_role;


-- Conservative operator-credit reservations; deleting a user or content never
-- refunds an already-started provider budget. IDs are opaque, not user IDs.
create table if not exists public.operator_cost_reservations (
 id uuid primary key,day date not null default (now() at time zone 'UTC')::date,
 upper_usd numeric(14,6) not null check(upper_usd>=0),created_at timestamptz not null default now()
);
alter table public.operator_cost_reservations enable row level security;
revoke all on public.operator_cost_reservations from public,anon,authenticated;
grant select,insert,update,delete on public.operator_cost_reservations to service_role;
alter table public.generation_usage add column if not exists provider_usage jsonb not null default '{}';

create or replace function public.reserve_operator_cost(p_id uuid,p_upper numeric,p_daily numeric)
returns boolean language plpgsql security definer set search_path=public as $$
declare today date:=(now() at time zone 'UTC')::date; spent numeric;
begin
 if p_upper is null or p_daily is null or p_upper<0 or p_daily<=0 or p_daily>100000 then raise exception 'Invalid cost budget'; end if;
 perform pg_advisory_xact_lock(hashtext('bf_operator_cost_'||today::text));
 if exists(select 1 from public.operator_cost_reservations where id=p_id) then return false; end if;
 select coalesce(sum(upper_usd),0) into spent from public.operator_cost_reservations where day=today;
 if spent+p_upper>p_daily then return false; end if;
 insert into public.operator_cost_reservations(id,upper_usd) values(p_id,p_upper);
 return true;
end $$;
create or replace function public.generation_health()
returns jsonb language sql security definer set search_path=public as $$
 select jsonb_build_object(
 'completed_today',count(*) filter(where status='completed'),
 'failed_today',count(*) filter(where status='failed'),
 'active_reservations',count(*) filter(where status='reserved' and expires_at>now()),
 'average_duration_ms',coalesce(avg((provider_usage->>'duration_ms')::numeric) filter(where status='completed'),0),
 'reported_input_tokens',coalesce(sum((provider_usage->>'input_tokens')::bigint),0),
 'reported_output_tokens',coalesce(sum((provider_usage->>'output_tokens')::bigint),0),
 'reserved_operator_budget_usd',(select coalesce(sum(upper_usd),0) from public.operator_cost_reservations where day=(now() at time zone 'UTC')::date))
 from public.generation_usage where created_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC';
$$;
revoke execute on function public.reserve_operator_cost(uuid,numeric,numeric),public.generation_health() from public,anon,authenticated;
grant execute on function public.reserve_operator_cost(uuid,numeric,numeric),public.generation_health() to service_role;

create or replace function public.expire_generation_reservations()
returns integer language plpgsql security definer set search_path=public as $$
declare n integer;
begin
 update public.generation_usage set status='failed',failure_code='RESERVATION_EXPIRED' where status='reserved' and expires_at<now();
 get diagnostics n=row_count;
 delete from public.operator_cost_reservations where day<(now() at time zone 'UTC')::date-90;
 return n;
end $$;
revoke execute on function public.expire_generation_reservations() from public,anon,authenticated;
grant execute on function public.expire_generation_reservations() to service_role;


-- Freeze the exact paid release metadata, and make retries fair and bounded.
-- No existing record is silently assigned a checksum for a different artifact.
alter table public.desktop_orders add column if not exists release_sha256 text;
alter table public.desktop_orders add column if not exists release_bucket text;
alter table public.desktop_orders add column if not exists delivery_attempts integer not null default 0;
alter table public.desktop_orders add column if not exists delivery_next_attempt_at timestamptz not null default now();
create index if not exists desktop_delivery_queue on public.desktop_orders(delivery_next_attempt_at,delivery_attempts,created_at) where status='paid' and delivered_at is null;

create or replace function public.record_desktop_order(p_data jsonb)
returns void language plpgsql security definer set search_path=public as $$
declare tid text:=p_data->>'transaction_id'; state text;
begin
 perform pg_advisory_xact_lock(hashtext('bf_order_'||tid));
 state:=public.desktop_order_state(tid,(p_data->>'amount_total')::bigint);
 if p_data->>'release_sha256' is not null and (p_data->>'release_sha256') !~ '^[0-9a-fA-F]{64}$' then raise exception 'Invalid release checksum'; end if;
 insert into public.desktop_orders(transaction_id,customer_id,email,tier,status,amount_total,currency,release_path,release_sha256,release_bucket,occurred_at)
 values(tid,p_data->>'customer_id',lower(p_data->>'email'),p_data->>'tier',state,(p_data->>'amount_total')::bigint,p_data->>'currency',p_data->>'release_path',p_data->>'release_sha256',p_data->>'release_bucket',(p_data->>'occurred_at')::timestamptz)
 on conflict on constraint desktop_orders_pkey do nothing;
end $$;

create or replace function public.claim_desktop_delivery(p_id text)
returns boolean language plpgsql security definer set search_path=public as $$
declare n integer;
begin
 update public.desktop_orders set delivery_claimed_until=now()+interval '5 minutes',
  delivery_next_attempt_at=now()+make_interval(secs=>least(86400,60*power(2,least(delivery_attempts,10)))::double precision),
  delivery_attempts=delivery_attempts+1
 where transaction_id=p_id and status='paid' and delivered_at is null and delivery_next_attempt_at<=now()
   and (delivery_claimed_until is null or delivery_claimed_until<now());
 get diagnostics n=row_count;return n=1;
end $$;

create or replace function public.request_desktop_redelivery(p_id text)
returns boolean language plpgsql security definer set search_path=public as $$
declare n integer;
begin
 update public.desktop_orders set delivered_at=null,delivery_nonce=gen_random_uuid(),delivery_attempts=0,delivery_next_attempt_at=now()
 where transaction_id=p_id and status='paid' and delivered_at<now()-interval '24 hours'
   and (delivery_claimed_until is null or delivery_claimed_until<now());
 get diagnostics n=row_count;return n=1;
end $$;
revoke execute on function public.record_desktop_order(jsonb),public.claim_desktop_delivery(text),public.request_desktop_redelivery(text) from public,anon,authenticated;
grant execute on function public.record_desktop_order(jsonb),public.claim_desktop_delivery(text),public.request_desktop_redelivery(text) to service_role;
