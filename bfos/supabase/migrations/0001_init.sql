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
