-- v1.4 commerce: one-time desktop orders are NOT Cloud plans.
-- Owner confirmed this is prelaunch, with no paid legacy commitments.
alter table public.profiles add column if not exists deletion_pending boolean not null default false;
alter table public.profiles add column if not exists past_due_since timestamptz;
update public.profiles set plan='free',plan_status='active' where plan in ('desktop_solo','desktop_agency');

create table if not exists public.billing_subscriptions (
 id text primary key, user_id uuid references auth.users on delete set null,
 customer_id text not null, plan text not null check(plan in ('pro','agency')),
 status text not null, price_id text, billing_interval text,
 occurred_at timestamptz not null, updated_at timestamptz not null default now()
);
create index if not exists billing_subscriptions_user on public.billing_subscriptions(user_id,status);

create table if not exists public.checkout_intents (
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,
 plan text not null,billing_interval text not null,transaction_id text,
 state text not null default 'creating',created_at timestamptz not null default now(),
 expires_at timestamptz not null default now()+interval '30 minutes'
);
create index if not exists checkout_intents_user on public.checkout_intents(user_id,created_at desc);

create table if not exists public.billing_operations (
 user_id uuid primary key references auth.users on delete cascade,
 operation_id uuid not null,expires_at timestamptz not null
);

create table if not exists public.desktop_orders (
 transaction_id text primary key,customer_id text not null,email text not null,
 tier text not null check(tier in ('owner','agency_source')),
 status text not null default 'paid' check(status in ('paid','refunded','disputed')),
 amount_total bigint not null default 0, currency text not null default 'USD',
 release_path text not null,created_at timestamptz not null default now(),
 occurred_at timestamptz not null,delivery_nonce uuid not null default gen_random_uuid(),
 delivered_at timestamptz,delivery_url text,delivery_expires_at timestamptz,
 delivery_error text
);
create index if not exists desktop_orders_customer on public.desktop_orders(customer_id);
create table if not exists public.payment_adjustments (
 id text primary key,transaction_id text not null,action text not null,status text not null,
 adjustment_type text,amount_total bigint not null default 0,occurred_at timestamptz not null
);

-- All billing records and operations are private to service-role handlers.
alter table public.billing_subscriptions enable row level security;
alter table public.checkout_intents enable row level security;
alter table public.billing_operations enable row level security;
alter table public.desktop_orders enable row level security;
alter table public.payment_adjustments enable row level security;
revoke all on public.billing_subscriptions,public.checkout_intents,public.billing_operations,public.desktop_orders,public.payment_adjustments from public,anon,authenticated;
grant select,insert,update,delete on public.billing_subscriptions,public.checkout_intents,public.billing_operations,public.desktop_orders,public.payment_adjustments to service_role;

create or replace function public.begin_checkout(p_uid uuid,p_plan text,p_interval text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare prior public.checkout_intents; cid uuid;
begin
 perform pg_advisory_xact_lock(hashtext('bf_billing_'||p_uid::text));
 if exists(select 1 from public.profiles where id=p_uid and deletion_pending) then
  return jsonb_build_object('ok',false,'code','DELETION_PENDING');
 end if;
 if exists(select 1 from public.billing_subscriptions where user_id=p_uid and status in ('active','trialing','past_due','paused')) or
    exists(select 1 from public.profiles where id=p_uid and paddle_subscription_id is not null) then
  return jsonb_build_object('ok',false,'code','SUBSCRIPTION_EXISTS');
 end if;
 select * into prior from public.checkout_intents where user_id=p_uid and state in ('creating','open','uncertain') order by created_at desc limit 1;
 if found then
  if prior.plan<>p_plan or prior.billing_interval<>p_interval then
   return jsonb_build_object('ok',false,'code','CHECKOUT_ALREADY_OPEN');
  end if;
  return jsonb_build_object('ok',false,'code','CHECKOUT_PENDING','id',prior.id,'transaction_id',prior.transaction_id);
 end if;
 if p_plan not in ('pro','agency') or p_interval not in ('month','year') then
  return jsonb_build_object('ok',false,'code','INVALID_PLAN');
 end if;
 insert into public.checkout_intents(user_id,plan,billing_interval) values(p_uid,p_plan,p_interval) returning id into cid;
 return jsonb_build_object('ok',true,'id',cid);
end $$;

create or replace function public.begin_billing_operation(p_uid uuid,p_id uuid)
returns boolean language plpgsql security definer set search_path=public as $$
begin
 perform pg_advisory_xact_lock(hashtext('bf_billing_'||p_uid::text));
 if exists(select 1 from public.billing_operations where user_id=p_uid and expires_at>now()) then return false; end if;
 insert into public.billing_operations(user_id,operation_id,expires_at) values(p_uid,p_id,now()+interval '5 minutes')
 on conflict on constraint billing_operations_pkey do update set operation_id=excluded.operation_id,expires_at=excluded.expires_at;
 return true;
end $$;

-- Atomic event ordering prevents delayed or parallel webhooks from rolling
-- an account back. Store ALL subscriptions, so duplicates are detectable.
create or replace function public.apply_subscription(p_uid uuid,p_id text,p_customer text,p_plan text,p_status text,p_price text,p_interval text,p_at timestamptz)
returns boolean language plpgsql security definer set search_path=public as $$
declare chosen public.billing_subscriptions; affected integer;
begin
 perform pg_advisory_xact_lock(hashtext('bf_subscription_'||p_id));
 perform pg_advisory_xact_lock(hashtext('bf_billing_'||p_uid::text));
 if exists(select 1 from public.billing_subscriptions where id=p_id and user_id is distinct from p_uid) then
  raise exception 'Subscription account mismatch';
 end if;
 insert into public.billing_subscriptions(id,user_id,customer_id,plan,status,price_id,billing_interval,occurred_at)
 values(p_id,p_uid,p_customer,p_plan,p_status,p_price,p_interval,p_at)
 on conflict on constraint billing_subscriptions_pkey do update set status=excluded.status,plan=excluded.plan,
 price_id=excluded.price_id,billing_interval=excluded.billing_interval,occurred_at=excluded.occurred_at,updated_at=now()
 where billing_subscriptions.occurred_at<=excluded.occurred_at;
 get diagnostics affected=row_count;
 if affected=0 then return false; end if;
 select * into chosen from public.billing_subscriptions where user_id=p_uid and status in ('active','trialing','past_due')
 order by case status when 'past_due' then 0 else 1 end desc,case plan when 'agency' then 2 else 1 end desc,occurred_at desc limit 1;
 if found then
  update public.profiles set plan=chosen.plan,plan_status=chosen.status,paddle_customer_id=p_customer,
    paddle_subscription_id=chosen.id,billing_updated_at=greatest(coalesce(billing_updated_at,p_at),p_at),
    past_due_since=case when chosen.status='past_due' then coalesce(past_due_since,chosen.occurred_at) else null end
    where id=p_uid;
 else
  update public.profiles set plan='free',plan_status='active',paddle_customer_id=p_customer,
    paddle_subscription_id=null,past_due_since=null,billing_updated_at=greatest(coalesce(billing_updated_at,p_at),p_at) where id=p_uid;
 end if;
 update public.checkout_intents set state='completed' where user_id=p_uid and state in ('open','creating','uncertain');
 return true;
end $$;

create or replace function public.desktop_order_state(p_tid text,p_amount bigint)
returns text language sql stable security definer set search_path=public as $$
 select case
  when exists(select 1 from public.payment_adjustments a where a.transaction_id=p_tid and a.action='refund' and a.status='approved' and a.adjustment_type='full')
    or (p_amount>0 and (select coalesce(sum(a.amount_total),0) from public.payment_adjustments a where a.transaction_id=p_tid and a.action='refund' and a.status='approved')>=p_amount) then 'refunded'
  when (select a.action from public.payment_adjustments a where a.transaction_id=p_tid and a.status='approved' and a.action in ('chargeback','chargeback_warning','chargeback_reverse') order by a.occurred_at desc,a.id desc limit 1) in ('chargeback','chargeback_warning') then 'disputed'
  else 'paid' end;
$$;
revoke execute on function public.desktop_order_state(text,bigint) from public,anon,authenticated;
grant execute on function public.desktop_order_state(text,bigint) to service_role;

create or replace function public.apply_payment_adjustment(p_data jsonb)
returns void language plpgsql security definer set search_path=public as $$
declare tid text:=p_data->>'transaction_id';
begin
 perform pg_advisory_xact_lock(hashtext('bf_order_'||tid));
 insert into public.payment_adjustments(id,transaction_id,action,status,adjustment_type,amount_total,occurred_at)
 values(p_data->>'id',tid,p_data->>'action',p_data->>'status',p_data->>'type',coalesce((p_data->>'amount_total')::bigint,0),(p_data->>'occurred_at')::timestamptz)
 on conflict on constraint payment_adjustments_pkey do update set status=excluded.status,amount_total=excluded.amount_total,occurred_at=excluded.occurred_at
 where payment_adjustments.occurred_at<=excluded.occurred_at;
 -- Approved cumulative/full refunds revoke downloads. Dispute reversal
 -- restores access only if there is no approved full/cumulative refund.
 update public.desktop_orders o set status=public.desktop_order_state(tid,o.amount_total) where o.transaction_id=tid;
end $$;

revoke execute on function public.begin_checkout(uuid,text,text),public.begin_billing_operation(uuid,uuid),public.apply_subscription(uuid,text,text,text,text,text,text,timestamptz),public.apply_payment_adjustment(jsonb) from public,anon,authenticated;
grant execute on function public.begin_checkout(uuid,text,text),public.begin_billing_operation(uuid,uuid),public.apply_subscription(uuid,text,text,text,text,text,text,timestamptz),public.apply_payment_adjustment(jsonb) to service_role;

-- A crashed webhook worker must not leave an event permanently "processed".
alter table public.paddle_events add column if not exists status text not null default 'completed';
alter table public.paddle_events add column if not exists lease_until timestamptz;
create or replace function public.claim_paddle_event(p_id text)
returns text language plpgsql security definer set search_path=public as $$
declare n integer; state text;
begin
 insert into public.paddle_events(event_id,status,lease_until) values(p_id,'processing',now()+interval '5 minutes')
 on conflict on constraint paddle_events_pkey do update set status='processing',lease_until=excluded.lease_until
 where paddle_events.status='failed' or (paddle_events.status='processing' and paddle_events.lease_until<now());
 get diagnostics n=row_count;
 if n=1 then return 'claimed'; end if;
 select status into state from public.paddle_events where event_id=p_id;
 return state;
end $$;

create or replace function public.record_desktop_order(p_data jsonb)
returns void language plpgsql security definer set search_path=public as $$
declare tid text:=p_data->>'transaction_id'; state text:='paid';
begin
 perform pg_advisory_xact_lock(hashtext('bf_order_'||tid));
 state:=public.desktop_order_state(tid,(p_data->>'amount_total')::bigint);
 insert into public.desktop_orders(transaction_id,customer_id,email,tier,status,amount_total,currency,release_path,occurred_at)
 values(tid,p_data->>'customer_id',lower(p_data->>'email'),p_data->>'tier',state,(p_data->>'amount_total')::bigint,p_data->>'currency',p_data->>'release_path',(p_data->>'occurred_at')::timestamptz)
 on conflict on constraint desktop_orders_pkey do nothing;
end $$;
alter table public.desktop_orders add column if not exists delivery_claimed_until timestamptz;
create or replace function public.claim_desktop_delivery(p_id text)
returns boolean language plpgsql security definer set search_path=public as $$
declare n integer;
begin
 update public.desktop_orders set delivery_claimed_until=now()+interval '5 minutes' where transaction_id=p_id and status='paid' and delivered_at is null and (delivery_claimed_until is null or delivery_claimed_until<now());
 get diagnostics n=row_count;return n=1;
end $$;
revoke execute on function public.claim_paddle_event(text),public.record_desktop_order(jsonb),public.claim_desktop_delivery(text) from public,anon,authenticated;
grant execute on function public.claim_paddle_event(text),public.record_desktop_order(jsonb),public.claim_desktop_delivery(text) to service_role;

create or replace function public.request_desktop_redelivery(p_id text)
returns boolean language plpgsql security definer set search_path=public as $$
declare n integer;
begin
 update public.desktop_orders set delivered_at=null,delivery_nonce=gen_random_uuid() where transaction_id=p_id and status='paid' and delivered_at<now()-interval '24 hours' and (delivery_claimed_until is null or delivery_claimed_until<now());
 get diagnostics n=row_count;return n=1;
end $$;
revoke execute on function public.request_desktop_redelivery(text) from public,anon,authenticated;
grant execute on function public.request_desktop_redelivery(text) to service_role;
alter table public.paddle_events add column if not exists event_type text;
alter table public.paddle_events add column if not exists entity_id text;
alter table public.paddle_events add column if not exists last_error text;

-- Email reuse is not a billing ownership grant. Keep the customer binding
-- even after account deletion (user_id becomes NULL and cannot be reclaimed).
create table if not exists public.billing_customers (
 customer_id text primary key,user_id uuid references auth.users on delete set null,created_at timestamptz not null default now()
);
alter table public.billing_customers enable row level security;
revoke all on public.billing_customers from public,anon,authenticated;
grant select,insert,update,delete on public.billing_customers to service_role;
insert into public.billing_customers(customer_id,user_id)
 select p.paddle_customer_id,p.id from public.profiles p where p.paddle_customer_id is not null and not exists(select 1 from public.profiles other where other.paddle_customer_id=p.paddle_customer_id and other.id<>p.id)
 on conflict on constraint billing_customers_pkey do nothing;
create or replace function public.claim_billing_customer(p_uid uuid,p_customer text)
returns boolean language plpgsql security definer set search_path=public as $$
declare owner uuid;
begin
 perform pg_advisory_xact_lock(hashtext('bf_customer_'||p_customer));
 select user_id into owner from public.billing_customers where customer_id=p_customer;
 if found then return owner is not distinct from p_uid; end if;
 if exists(select 1 from public.profiles where paddle_customer_id=p_customer and id<>p_uid)
   or exists(select 1 from public.billing_subscriptions where customer_id=p_customer and user_id is distinct from p_uid) then return false; end if;
 insert into public.billing_customers(customer_id,user_id) values(p_customer,p_uid);
 return true;
end $$;
revoke execute on function public.claim_billing_customer(uuid,text) from public,anon,authenticated;
grant execute on function public.claim_billing_customer(uuid,text) to service_role;
