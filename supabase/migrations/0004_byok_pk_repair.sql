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
