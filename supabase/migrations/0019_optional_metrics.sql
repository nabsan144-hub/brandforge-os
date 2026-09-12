-- Optional consented, client-reported event counts. No customer content or account IDs.
create table public.usage_events (
 id uuid primary key,actor_hash text not null check(actor_hash ~ '^[a-f0-9]{64}$'),
 event text not null check(event in ('visit','return_visit','signup_started','email_confirmed','campaign_saved','pack_exported','export_failed','billing_active_seen')),
 surface text not null check(surface in ('sales','cloud')),created_at timestamptz not null default now(),unique(actor_hash,event,surface)
);
alter table public.usage_events enable row level security;
revoke all on public.usage_events from public,anon,authenticated;
grant select,insert,delete on public.usage_events to service_role;
create function public.record_usage_event(p_id uuid,p_actor text,p_event text,p_surface text)
returns boolean language plpgsql security definer set search_path=public as $$
begin
 insert into public.usage_events(id,actor_hash,event,surface) values(p_id,p_actor,p_event,p_surface) on conflict do nothing;
 return true;
end; $$;
create function public.usage_event_summary()
returns jsonb language sql security definer set search_path=public as $$
 select jsonb_build_object('window_days',30,'client_reported',true,'event_counts',coalesce((select jsonb_agg(x) from (select surface,event,count(*) as count from public.usage_events where created_at>now()-interval '30 days' group by surface,event order by surface,event) x),'[]'::jsonb),
 'notice','Consenting sample; one event type per anonymous browser per UTC day and surface. Daily rotating pseudonyms, no cross-domain or account linkage. Not unique people, actual completed payments, causal conversions or a usable-pack benchmark.');
$$;
create function public.gc_usage_events() returns bigint language plpgsql security definer set search_path=public as $$
declare n bigint;begin delete from public.usage_events where created_at<now()-interval '30 days';get diagnostics n=row_count;return n;end; $$;
revoke all on function public.record_usage_event(uuid,text,text,text),public.usage_event_summary(),public.gc_usage_events() from public,anon,authenticated;
grant execute on function public.record_usage_event(uuid,text,text,text),public.usage_event_summary(),public.gc_usage_events() to service_role;
