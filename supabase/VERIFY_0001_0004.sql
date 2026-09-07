-- ============================================================================
-- BrandForge OS Cloud — VERIFY.sql (run after migrations 0001-0004)
-- ----------------------------------------------------------------------------
-- Confirms the schema is complete and correctly secured. Each query should
-- return the expected result; if any comes back empty/wrong, re-run the
-- migration it references.
-- ============================================================================

-- 1) All 6 tables present
select string_agg(table_name, ', ' order by table_name) as tables_present
  from information_schema.tables
 where table_schema = 'public'
   and table_name in (
     'profiles','campaigns','usage_monthly','user_api_keys',
     'paddle_events','delivery_log'
   );
-- EXPECT: campaigns, delivery_log, paddle_events, profiles, usage_monthly, user_api_keys

-- 2) RLS is ON for all 6 (should show all rls_enabled = t)
select relname as table_name, relrowsecurity as rls_enabled
  from pg_class
 where relname in (
     'profiles','campaigns','usage_monthly','user_api_keys',
     'paddle_events','delivery_log'
   )
   and relnamespace = 'public'::regnamespace
 order by relname;
-- EXPECT: every row is t

-- 3) All 5 functions exist
select string_agg(routine_name, ', ' order by routine_name) as functions_present
  from information_schema.routines
 where routine_schema = 'public'
   and routine_name in (
     'reserve_campaign_slot','release_campaign_slot',
     'enforce_lifetime_cap','reserve_delivery_slot','handle_new_user'
   );
-- EXPECT: enforce_lifetime_cap, handle_new_user, release_campaign_slot,
--         reserve_campaign_slot, reserve_delivery_slot

-- 4) Signup trigger is attached to auth.users
select count(*) as signup_trigger_count
  from pg_trigger
 where tgrelid = 'auth.users'::regclass
   and tgname = 'on_auth_user_created'
   and not tgisinternal;
-- EXPECT: 1

-- 5) user_api_keys PK is the composite (user_id, provider)
select pg_get_constraintdef(oid) as user_api_keys_pk
  from pg_constraint
 where conname = 'user_api_keys_pkey'
   and conrelid = 'public.user_api_keys'::regclass;
-- EXPECT: PRIMARY KEY (user_id, provider)

-- 6) Campaigns has the columns the app writes
select string_agg(column_name, ', ' order by column_name) as campaigns_cols
  from information_schema.columns
 where table_schema = 'public'
   and table_name = 'campaigns'
   and column_name in ('product','industry','audience','lang','benefits','files','user_id');
-- EXPECT: audience, benefits, files, industry, lang, product, user_id
