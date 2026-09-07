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
