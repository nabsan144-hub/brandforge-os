create table public.campaign_transfers (
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
 request_id uuid not null,sha256 text not null,name text not null,pack jsonb not null check(octet_length(pack::text)<=3100000),
 created_at timestamptz not null default now(),unique(user_id,request_id)
);
alter table public.campaign_transfers enable row level security;
revoke all on public.campaign_transfers from public,anon,authenticated;
grant select,insert,update,delete on public.campaign_transfers to service_role;
create function public.save_campaign_transfer(p_uid uuid,p_request uuid,p_hash text,p_pack jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare existing public.campaign_transfers; tid uuid;
begin
 perform 1 from public.profiles where id=p_uid and not deletion_pending for update;
 if not found then return jsonb_build_object('ok',false,'code','ACCOUNT_UNAVAILABLE'); end if;
 select * into existing from public.campaign_transfers where user_id=p_uid and request_id=p_request;
 if found then
  if existing.sha256<>p_hash then return jsonb_build_object('ok',false,'code','REQUEST_CONFLICT'); end if;
  return jsonb_build_object('ok',true,'id',existing.id,'replayed',true);
 end if;
 if (select count(*) from public.campaign_transfers where user_id=p_uid)>=10 then return jsonb_build_object('ok',false,'code','ARCHIVE_LIMIT'); end if;
 insert into public.campaign_transfers(user_id,request_id,sha256,name,pack) values(p_uid,p_request,p_hash,p_pack->>'name',p_pack) returning id into tid;
 return jsonb_build_object('ok',true,'id',tid);
end; $$;
revoke all on function public.save_campaign_transfer(uuid,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.save_campaign_transfer(uuid,uuid,text,jsonb) to service_role;
