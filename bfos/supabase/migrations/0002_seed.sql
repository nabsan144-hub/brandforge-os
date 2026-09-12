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
