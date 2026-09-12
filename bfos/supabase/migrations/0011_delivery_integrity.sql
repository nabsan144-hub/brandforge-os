-- Freeze the exact paid release metadata, and make retries fair and bounded.
-- No existing record is silently assigned a checksum for a different artifact.
alter table public.desktop_orders add column if not exists release_sha256 text;
alter table public.desktop_orders add column if not exists release_bucket text;
alter table public.desktop_orders add column if not exists delivery_attempts integer not null default 0;
alter table public.desktop_orders add column if not exists delivery_next_attempt_at timestamptz not null default now();
create index if not exists desktop_delivery_queue on public.desktop_orders(delivery_next_attempt_at,delivery_attempts,created_at) where status='paid' and delivered_at is null;

create or replace function public.record_desktop_order(p_data jsonb)
returns void language plpgsql security definer set search_path=public as $$
declare tid text:=p_data->>'transaction_id'; state text;
begin
 perform pg_advisory_xact_lock(hashtext('bf_order_'||tid));
 state:=public.desktop_order_state(tid,(p_data->>'amount_total')::bigint);
 if p_data->>'release_sha256' is not null and (p_data->>'release_sha256') !~ '^[0-9a-fA-F]{64}$' then raise exception 'Invalid release checksum'; end if;
 insert into public.desktop_orders(transaction_id,customer_id,email,tier,status,amount_total,currency,release_path,release_sha256,release_bucket,occurred_at)
 values(tid,p_data->>'customer_id',lower(p_data->>'email'),p_data->>'tier',state,(p_data->>'amount_total')::bigint,p_data->>'currency',p_data->>'release_path',p_data->>'release_sha256',p_data->>'release_bucket',(p_data->>'occurred_at')::timestamptz)
 on conflict on constraint desktop_orders_pkey do nothing;
end $$;

create or replace function public.claim_desktop_delivery(p_id text)
returns boolean language plpgsql security definer set search_path=public as $$
declare n integer;
begin
 update public.desktop_orders set delivery_claimed_until=now()+interval '5 minutes',
  delivery_next_attempt_at=now()+make_interval(secs=>least(86400,60*power(2,least(delivery_attempts,10)))::double precision),
  delivery_attempts=delivery_attempts+1
 where transaction_id=p_id and status='paid' and delivered_at is null and delivery_next_attempt_at<=now()
   and (delivery_claimed_until is null or delivery_claimed_until<now());
 get diagnostics n=row_count;return n=1;
end $$;

create or replace function public.request_desktop_redelivery(p_id text)
returns boolean language plpgsql security definer set search_path=public as $$
declare n integer;
begin
 update public.desktop_orders set delivered_at=null,delivery_nonce=gen_random_uuid(),delivery_attempts=0,delivery_next_attempt_at=now()
 where transaction_id=p_id and status='paid' and delivered_at<now()-interval '24 hours'
   and (delivery_claimed_until is null or delivery_claimed_until<now());
 get diagnostics n=row_count;return n=1;
end $$;
revoke execute on function public.record_desktop_order(jsonb),public.claim_desktop_delivery(text),public.request_desktop_redelivery(text) from public,anon,authenticated;
grant execute on function public.record_desktop_order(jsonb),public.claim_desktop_delivery(text),public.request_desktop_redelivery(text) to service_role;
