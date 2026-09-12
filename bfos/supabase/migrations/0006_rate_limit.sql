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
