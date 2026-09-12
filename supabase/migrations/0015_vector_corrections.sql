-- Versioned corrections are deliberately limited to new inline vector packs.
alter table public.campaigns add column if not exists visual_recipe jsonb;
alter table public.campaigns add column if not exists visual_fields jsonb;
alter table public.campaigns add column if not exists visual_field_report jsonb;
create table if not exists public.campaign_visual_versions (
 id uuid primary key default gen_random_uuid(),
 campaign_id uuid not null references public.campaigns(id) on delete cascade,
 user_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(octet_length(payload::text)<=3000000),
 request_id uuid,source_revision integer,result_revision integer,
 created_at timestamptz not null default now(),unique(user_id,request_id)
);
create index if not exists visual_versions_campaign on public.campaign_visual_versions(campaign_id);
alter table public.campaign_visual_versions enable row level security;
revoke all on public.campaign_visual_versions from public,anon,authenticated;
grant select,insert,update,delete on public.campaign_visual_versions to service_role;
alter table public.campaigns add column if not exists visual_version_id uuid references public.campaign_visual_versions(id);
create or replace function public.prune_campaign_visual_versions(p_campaign uuid)
returns void language sql security definer set search_path=public as $$
 delete from public.campaign_visual_versions v where v.campaign_id=p_campaign
 and not exists(select 1 from public.campaigns c where c.visual_version_id=v.id)
 and not exists(select 1 from public.campaign_revisions r where r.campaign_id=p_campaign and r.snapshot->>'visual_version_id'=v.id::text);
$$;
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
    research_live,provider,files,brief,stage_status,visual_status,asset_bundle_id,visual_recipe,visual_fields)
  values(p_uid,nm,left(p_campaign->>'product',80),left(coalesce(p_campaign->>'industry',''),80),
    left(coalesce(p_campaign->>'audience',''),120),left(coalesce(p_campaign->>'benefits',''),500),
    coalesce(p_campaign->>'lang','en'),p_campaign->>'strategy',p_campaign->>'copy',p_campaign->>'seo',
    false,coalesce(p_campaign->>'provider','offline'),p_campaign->'files',
    coalesce(p_campaign->'brief','{}'::jsonb),coalesce(p_campaign->'stage_status','{}'::jsonb),
    coalesce(p_campaign->'visual_status','{"mode":"unknown","state":"unknown"}'::jsonb),
    (p_campaign->>'asset_bundle_id')::uuid,p_campaign->'visual_recipe',p_campaign->'visual_fields') returning id into cid;
  if b.id is not null then
    update public.campaign_asset_bundles set state='attached',campaign_id=cid where id=b.id;
  end if;
  update public.generation_usage set status='completed',campaign_id=cid,completed_at=now(),provider=p_campaign->>'provider',provider_usage=coalesce(p_campaign->'provider_usage','{}'::jsonb)
    where id=p_id;
  return jsonb_build_object('id',cid,'name',nm,'replayed',false);
end $$;

create or replace function public.edit_campaign(p_uid uuid,p_id uuid,p_revision integer,p_changes jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; statuses jsonb; key text;
begin
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 if c.revision is distinct from p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 insert into public.campaign_revisions(campaign_id,user_id,revision,snapshot) values(p_id,p_uid,c.revision,to_jsonb(c)-'files'-'brief');
 statuses:=c.stage_status;
 foreach key in array array['strategy','copy','seo'] loop
  if p_changes ? key then statuses:=jsonb_set(statuses,array[key],'{"state":"edited","provider":"human"}'::jsonb); end if;
 end loop;
 update public.campaigns set name=coalesce(p_changes->>'name',c.name),strategy=coalesce(p_changes->>'strategy',c.strategy),copy=coalesce(p_changes->>'copy',c.copy),seo=coalesce(p_changes->>'seo',c.seo),stage_status=statuses,visual_review_state=case when p_changes ? 'copy' and p_changes->>'copy' is distinct from c.copy then 'review_required' else c.visual_review_state end,visual_review_ack_revision=null,visual_review_ack_at=null,revision=c.revision+1,updated_at=now() where id=p_id;
 -- Retention is explicit in the UI: the last ten saved versions.
 delete from public.campaign_revisions where campaign_id=p_id and revision<c.revision-9;
 perform public.prune_campaign_visual_versions(p_id);
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision+1);
end $$;


create or replace function public.save_vector_correction(p_uid uuid,p_id uuid,p_revision integer,p_request uuid,p_payload jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; prior public.campaign_visual_versions; old_id uuid; new_id uuid;
begin
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 select * into prior from public.campaign_visual_versions where user_id=p_uid and request_id=p_request;
 if found then
  if prior.campaign_id<>p_id or prior.source_revision is distinct from p_revision or prior.payload->'fields' is distinct from p_payload->'fields' then return jsonb_build_object('ok',false,'code','IDEMPOTENCY_CONFLICT'); end if;
  return jsonb_build_object('ok',true,'id',p_id,'revision',prior.result_revision,'replayed',true);
 end if;
 if c.revision is distinct from p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 if c.asset_bundle_id is not null or c.visual_recipe->>'schema' is distinct from '1' or c.visual_status->>'mode'='ai' then return jsonb_build_object('ok',false,'code','VISUAL_CORRECTION_UNSUPPORTED'); end if;
 if p_request is null or p_payload->'recipe' is distinct from c.visual_recipe or jsonb_typeof(p_payload->'files') is distinct from 'array' or jsonb_typeof(p_payload->'fields') is distinct from 'object' then raise exception 'Invalid correction payload'; end if;
 old_id:=c.visual_version_id;
 if old_id is null then
  insert into public.campaign_visual_versions(campaign_id,user_id,payload) values(p_id,p_uid,jsonb_build_object('files',c.files,'recipe',c.visual_recipe,'fields',c.visual_fields,'report',c.visual_field_report)) returning id into old_id;
  -- All pre-correction text snapshots used this same original file set.
  update public.campaign_revisions set snapshot=jsonb_set(snapshot,'{visual_version_id}',to_jsonb(old_id)) where campaign_id=p_id and snapshot->>'visual_version_id' is null;
  c.visual_version_id:=old_id;
 end if;
 insert into public.campaign_revisions(campaign_id,user_id,revision,snapshot) values(p_id,p_uid,c.revision,to_jsonb(c)-'files'-'brief');
 insert into public.campaign_visual_versions(campaign_id,user_id,payload,request_id,source_revision,result_revision) values(p_id,p_uid,p_payload,p_request,p_revision,c.revision+1) returning id into new_id;
 update public.campaigns set files=p_payload->'files',visual_fields=p_payload->'fields',visual_field_report=p_payload->'report',visual_version_id=new_id,revision=c.revision+1,updated_at=now(),visual_review_state='review_required',visual_review_ack_revision=null,visual_review_ack_at=null where id=p_id;
 delete from public.campaign_revisions where campaign_id=p_id and revision<c.revision-9;
 perform public.prune_campaign_visual_versions(p_id);
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision+1,'replayed',false);
end $$;

create or replace function public.restore_vector_revision(p_uid uuid,p_id uuid,p_revision integer,p_restore integer)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; snap jsonb; v public.campaign_visual_versions;
begin
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 if c.revision is distinct from p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 select snapshot into snap from public.campaign_revisions where campaign_id=p_id and user_id=p_uid and revision=p_restore;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 select * into v from public.campaign_visual_versions where id=(snap->>'visual_version_id')::uuid and campaign_id=p_id and user_id=p_uid;
 if not found or c.asset_bundle_id is not null or c.visual_status->>'mode'='ai' then return jsonb_build_object('ok',false,'code','VISUAL_CORRECTION_UNSUPPORTED'); end if;
 insert into public.campaign_revisions(campaign_id,user_id,revision,snapshot) values(p_id,p_uid,c.revision,to_jsonb(c)-'files'-'brief');
 update public.campaigns set name=snap->>'name',strategy=snap->>'strategy',copy=snap->>'copy',seo=snap->>'seo',stage_status=snap->'stage_status',files=v.payload->'files',visual_fields=v.payload->'fields',visual_recipe=v.payload->'recipe',visual_field_report=v.payload->'report',visual_version_id=v.id,revision=c.revision+1,updated_at=now(),visual_review_state='review_required',visual_review_ack_revision=null,visual_review_ack_at=null where id=p_id;
 delete from public.campaign_revisions where campaign_id=p_id and revision<c.revision-9;
 perform public.prune_campaign_visual_versions(p_id);
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision+1);
end $$;

revoke execute on function public.complete_generation(uuid,uuid,jsonb),public.edit_campaign(uuid,uuid,int,jsonb),public.prune_campaign_visual_versions(uuid),public.save_vector_correction(uuid,uuid,int,uuid,jsonb),public.restore_vector_revision(uuid,uuid,int,int) from public,anon,authenticated;
grant execute on function public.complete_generation(uuid,uuid,jsonb),public.edit_campaign(uuid,uuid,int,jsonb),public.prune_campaign_visual_versions(uuid),public.save_vector_correction(uuid,uuid,int,uuid,jsonb),public.restore_vector_revision(uuid,uuid,int,int) to service_role;

create or replace function public.attach_migrated_asset_bundle(p_uid uuid,p_campaign uuid,p_revision integer,p_bundle uuid)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; b public.campaign_asset_bundles;
begin
 select * into c from public.campaigns where id=p_campaign and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 if c.visual_version_id is not null then return jsonb_build_object('ok',false,'code','VISUAL_HISTORY_MIGRATION_UNSUPPORTED'); end if;
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
