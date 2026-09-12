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
