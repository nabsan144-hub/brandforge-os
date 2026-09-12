-- Immutable private bundles + durable cleanup independent of account lifetime.
-- Create the private bucket separately; this migration never creates a public bucket.
create table if not exists public.campaign_asset_bundles (
 id uuid primary key,
 user_id uuid references auth.users(id) on delete set null,
 generation_id uuid,
 campaign_id uuid references public.campaigns(id) on delete set null,
 source_campaign_id uuid references public.campaigns(id) on delete set null,
 source_revision integer,
 bucket text not null, object_path text not null,
 bytes integer not null check(bytes between 1 and 20000000),
 sha256 text not null check(sha256 ~ '^[a-f0-9]{64}$'),
 file_manifest jsonb not null check(jsonb_typeof(file_manifest)='array'),
 state text not null default 'pending' check(state in ('pending','attached','deleting')),
 created_at timestamptz not null default now(), uploaded_at timestamptz,
 cleanup_until timestamptz, cleanup_token uuid,
 unique(bucket,object_path)
);
create index if not exists campaign_asset_cleanup on public.campaign_asset_bundles(state,created_at);
create index if not exists campaign_asset_owner on public.campaign_asset_bundles(user_id,campaign_id);
alter table public.campaign_asset_bundles enable row level security;
revoke all on public.campaign_asset_bundles from public,anon,authenticated;
grant select,insert,update,delete on public.campaign_asset_bundles to service_role;
alter table public.campaigns add column if not exists asset_bundle_id uuid references public.campaign_asset_bundles(id);

create or replace function public.complete_generation(p_uid uuid,p_id uuid,p_campaign jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare r public.generation_usage; cid uuid; nm text; b public.campaign_asset_bundles;
begin
  perform pg_advisory_xact_lock(hashtext('bf_generation_'||p_uid::text));
  select * into r from public.generation_usage where id=p_id and user_id=p_uid for update;
  if not found then raise exception 'Reservation not found'; end if;
  if r.status='completed' then
    return jsonb_build_object('id',r.campaign_id,'replayed',true);
  end if;
  if r.status<>'reserved' or r.expires_at<=now() then raise exception 'Reservation expired or failed'; end if;
  if jsonb_typeof(p_campaign->'files') <> 'array' or length(p_campaign->>'product')=0 then
    raise exception 'Invalid campaign';
  end if;
  if p_campaign->>'asset_bundle_id' is not null then
    select * into b from public.campaign_asset_bundles where id=(p_campaign->>'asset_bundle_id')::uuid for update;
    if not found or b.user_id is distinct from p_uid or b.generation_id is distinct from p_id
      or b.state<>'pending' or b.uploaded_at is null or b.source_campaign_id is not null
      or b.file_manifest is distinct from p_campaign->'files' then raise exception 'Invalid private file bundle'; end if;
  elsif exists(select 1 from jsonb_array_elements(p_campaign->'files') x where x->>'storage'='bundle') then
    raise exception 'Missing private file bundle';
  end if;
  nm:=left(coalesce(nullif(p_campaign->>'name',''),p_campaign->>'product'),80);
  insert into public.campaigns(user_id,name,product,industry,audience,benefits,lang,strategy,copy,seo,
    research_live,provider,files,brief,stage_status,visual_status,asset_bundle_id)
  values(p_uid,nm,left(p_campaign->>'product',80),left(coalesce(p_campaign->>'industry',''),80),
    left(coalesce(p_campaign->>'audience',''),120),left(coalesce(p_campaign->>'benefits',''),500),
    coalesce(p_campaign->>'lang','en'),p_campaign->>'strategy',p_campaign->>'copy',p_campaign->>'seo',
    false,coalesce(p_campaign->>'provider','offline'),p_campaign->'files',
    coalesce(p_campaign->'brief','{}'::jsonb),coalesce(p_campaign->'stage_status','{}'::jsonb),
    coalesce(p_campaign->'visual_status','{"mode":"unknown","state":"unknown"}'::jsonb),
    (p_campaign->>'asset_bundle_id')::uuid) returning id into cid;
  if b.id is not null then
    update public.campaign_asset_bundles set state='attached',campaign_id=cid where id=b.id;
  end if;
  update public.generation_usage set status='completed',campaign_id=cid,completed_at=now(),provider=p_campaign->>'provider',provider_usage=coalesce(p_campaign->'provider_usage','{}'::jsonb)
    where id=p_id;
  return jsonb_build_object('id',cid,'name',nm,'replayed',false);
end $$;

-- Historical conversion is storage-only; it does not consume quota or rewrite copy.
create or replace function public.attach_migrated_asset_bundle(p_uid uuid,p_campaign uuid,p_revision integer,p_bundle uuid)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; b public.campaign_asset_bundles;
begin
 select * into c from public.campaigns where id=p_campaign and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 if c.asset_bundle_id=p_bundle then return jsonb_build_object('ok',true,'replayed',true); end if;
 if c.revision<>p_revision or c.asset_bundle_id is not null then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 select * into b from public.campaign_asset_bundles where id=p_bundle for update;
 if not found or b.user_id is distinct from p_uid or b.source_campaign_id is distinct from p_campaign
  or b.source_revision is distinct from p_revision or b.state<>'pending' or b.uploaded_at is null
  or b.generation_id is not null then raise exception 'Invalid migration bundle'; end if;
 update public.campaigns set files=b.file_manifest,asset_bundle_id=b.id where id=p_campaign;
 update public.campaign_asset_bundles set state='attached',campaign_id=p_campaign where id=b.id;
 return jsonb_build_object('ok',true);
end $$;

-- A lease prevents two maintenance workers from deleting the same queue record.
-- 24h pending grace covers uncertain uploads/saves. Attached rows remain protected
-- until their campaign OR identity is deleted. State is locked against attachment.
create or replace function public.claim_campaign_asset_cleanup(p_limit integer default 25)
returns jsonb language plpgsql security definer set search_path=public as $$
declare row public.campaign_asset_bundles; token uuid; result jsonb:='[]';
begin
 for row in select * from public.campaign_asset_bundles
  where (state='pending' and created_at<now()-interval '24 hours')
    or (state='attached' and (campaign_id is null or user_id is null))
    or (state='deleting' and cleanup_until<now())
  order by created_at limit greatest(1,least(coalesce(p_limit,25),100)) for update skip locked
 loop
  token:=gen_random_uuid();
  update public.campaign_asset_bundles set state='deleting',cleanup_until=now()+interval '15 minutes',cleanup_token=token where id=row.id;
  result:=result||jsonb_build_array(jsonb_build_object('id',row.id,'bucket',row.bucket,'object_path',row.object_path,'cleanup_token',token));
 end loop;
 return result;
end $$;
revoke execute on function public.complete_generation(uuid,uuid,jsonb),public.attach_migrated_asset_bundle(uuid,uuid,integer,uuid),public.claim_campaign_asset_cleanup(integer) from public,anon,authenticated;
grant execute on function public.complete_generation(uuid,uuid,jsonb),public.attach_migrated_asset_bundle(uuid,uuid,integer,uuid),public.claim_campaign_asset_cleanup(integer) to service_role;
