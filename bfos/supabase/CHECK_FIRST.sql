-- ============================================================================
-- BrandForge OS Cloud — CHECK_FIRST.sql (read-only, no CHANGE)
-- ----------------------------------------------------------------------------
-- Safe to run any time. Verifies whether the schema is already applied and
-- reports current row counts, so you know what state the project is in before
-- you run any migration. It makes NO writes.
-- ============================================================================

-- 1) Which application tables exist already? (empty = fresh project)
select table_name
  from information_schema.tables
 where table_schema = 'public'
   and table_name in (
     'profiles','campaigns','usage_monthly','user_api_keys',
     'paddle_events','delivery_log'
   )
 order by table_name;

-- 2) Are the quota functions present?
select routine_name
  from information_schema.routines
 where routine_schema = 'public'
   and routine_name in (
     'reserve_campaign_slot','release_campaign_slot',
     'enforce_lifetime_cap','reserve_delivery_slot','handle_new_user'
   )
 order by routine_name;

-- 3) Row counts (0 rows = clean, ready for 0001)
select 'profiles' as t, count(*) from public.profiles
union all select 'campaigns', count(*) from public.campaigns
union all select 'usage_monthly', count(*) from public.usage_monthly
union all select 'user_api_keys', count(*) from public.user_api_keys
union all select 'paddle_events', count(*) from public.paddle_events
union all select 'delivery_log', count(*) from public.delivery_log;

-- 4) Is the signup trigger wired to auth.users?
select tgname, pg_get_triggerdef(oid)
  from pg_trigger
 where tgrelid = 'auth.users'::regclass
   and not tgisinternal;

-- 5) RLS enabled on each table?
select relname as table_name, relrowsecurity as rls_enabled
  from pg_class
 where relname in (
     'profiles','campaigns','usage_monthly','user_api_keys',
     'paddle_events','delivery_log'
   )
   and relnamespace = 'public'::regnamespace
 order by relname;
