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
