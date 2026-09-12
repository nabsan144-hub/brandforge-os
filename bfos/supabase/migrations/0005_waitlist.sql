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
