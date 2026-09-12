-- Private vector correction/restore: immutable files; last-ten-version retention.
create or replace function public.prune_campaign_visual_versions(p_campaign uuid)
returns void language plpgsql security definer set search_path=public as $$
begin
 delete from public.campaign_visual_versions v where v.campaign_id=p_campaign
 and not exists(select 1 from public.campaigns c where c.visual_version_id=v.id)
 and not exists(select 1 from public.campaign_revisions r where r.campaign_id=p_campaign and r.snapshot->>'visual_version_id'=v.id::text);
 update public.campaign_asset_bundles b set state='deleting',cleanup_until=now()
 where b.campaign_id=p_campaign and b.state='attached'
 and not exists(select 1 from public.campaigns c where c.asset_bundle_id=b.id)
 and not exists(select 1 from public.campaign_visual_versions v where v.campaign_id=p_campaign and v.payload->>'bundle_id'=b.id::text);
end; $$;

create or replace function public.save_vector_correction(p_uid uuid,p_id uuid,p_revision integer,p_request uuid,p_payload jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; prior public.campaign_visual_versions; old_id uuid; new_id uuid; b public.campaign_asset_bundles;
begin
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 select * into prior from public.campaign_visual_versions where user_id=p_uid and request_id=p_request;
 if found then
  if prior.campaign_id<>p_id or prior.source_revision is distinct from p_revision or prior.payload->'fields' is distinct from p_payload->'fields' then return jsonb_build_object('ok',false,'code','IDEMPOTENCY_CONFLICT'); end if;
  return jsonb_build_object('ok',true,'id',p_id,'revision',prior.result_revision,'replayed',true);
 end if;
 if c.revision is distinct from p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 if c.visual_recipe->>'schema' is distinct from '1' or c.visual_status->>'mode'='ai' then return jsonb_build_object('ok',false,'code','VISUAL_CORRECTION_UNSUPPORTED'); end if;
 if p_request is null or p_payload->'recipe' is distinct from c.visual_recipe or jsonb_typeof(p_payload->'files') is distinct from 'array' or jsonb_typeof(p_payload->'fields') is distinct from 'object' then raise exception 'Invalid correction payload'; end if;
 if p_payload->>'bundle_id' is not null then
  select * into b from public.campaign_asset_bundles where id=(p_payload->>'bundle_id')::uuid for update;
  if not found or b.user_id is distinct from p_uid or b.source_campaign_id is distinct from p_id or b.source_revision is distinct from p_revision or b.state<>'pending' or b.uploaded_at is null or b.file_manifest is distinct from p_payload->'files' then raise exception 'Invalid correction bundle'; end if;
 elsif c.asset_bundle_id is not null then raise exception 'Private corrections require private output';
 end if;
 old_id:=c.visual_version_id;
 if old_id is null then
  insert into public.campaign_visual_versions(campaign_id,user_id,payload) values(p_id,p_uid,jsonb_build_object('files',c.files,'recipe',c.visual_recipe,'fields',c.visual_fields,'report',c.visual_field_report,'bundle_id',c.asset_bundle_id,'status',c.visual_status)) returning id into old_id;
  -- All pre-correction text snapshots used this same original file set.
  update public.campaign_revisions set snapshot=jsonb_set(snapshot,'{visual_version_id}',to_jsonb(old_id)) where campaign_id=p_id and snapshot->>'visual_version_id' is null;
  c.visual_version_id:=old_id;
 end if;
 insert into public.campaign_revisions(campaign_id,user_id,revision,snapshot) values(p_id,p_uid,c.revision,to_jsonb(c)-'files'-'brief');
 insert into public.campaign_visual_versions(campaign_id,user_id,payload,request_id,source_revision,result_revision) values(p_id,p_uid,p_payload,p_request,p_revision,c.revision+1) returning id into new_id;
 update public.campaigns set asset_bundle_id=b.id,files=p_payload->'files',visual_fields=p_payload->'fields',visual_field_report=p_payload->'report',visual_version_id=new_id,revision=c.revision+1,updated_at=now(),visual_review_state='review_required',visual_review_ack_revision=null,visual_review_ack_at=null where id=p_id;
 if b.id is not null then update public.campaign_asset_bundles set state='attached',campaign_id=p_id where id=b.id; end if;
 delete from public.campaign_revisions where campaign_id=p_id and revision<c.revision-9;
 perform public.prune_campaign_visual_versions(p_id);
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision+1,'replayed',false);
end $$;


create or replace function public.restore_vector_revision(p_uid uuid,p_id uuid,p_revision integer,p_restore integer)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; snap jsonb; v public.campaign_visual_versions; b public.campaign_asset_bundles;
begin
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 if c.revision is distinct from p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 select snapshot into snap from public.campaign_revisions where campaign_id=p_id and user_id=p_uid and revision=p_restore;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 select * into v from public.campaign_visual_versions where id=(snap->>'visual_version_id')::uuid and campaign_id=p_id and user_id=p_uid;
 if not found or (c.visual_status->>'mode'='ai' and c.visual_version_id is null) then return jsonb_build_object('ok',false,'code','VISUAL_CORRECTION_UNSUPPORTED'); end if;
 if v.payload->>'bundle_id' is not null then
  select * into b from public.campaign_asset_bundles where id=(v.payload->>'bundle_id')::uuid and user_id=p_uid and campaign_id=p_id and state='attached' for update;
  if not found then return jsonb_build_object('ok',false,'code','PRIVATE_VERSION_UNAVAILABLE'); end if;
 end if;
 insert into public.campaign_revisions(campaign_id,user_id,revision,snapshot) values(p_id,p_uid,c.revision,to_jsonb(c)-'files'-'brief');
 update public.campaigns set asset_bundle_id=b.id,name=snap->>'name',strategy=snap->>'strategy',copy=snap->>'copy',seo=snap->>'seo',stage_status=snap->'stage_status',visual_status=coalesce(v.payload->'status',snap->'visual_status',c.visual_status),files=v.payload->'files',visual_fields=v.payload->'fields',visual_recipe=v.payload->'recipe',visual_field_report=v.payload->'report',visual_version_id=v.id,revision=c.revision+1,updated_at=now(),visual_review_state='review_required',visual_review_ack_revision=null,visual_review_ack_at=null where id=p_id;
 delete from public.campaign_revisions where campaign_id=p_id and revision<c.revision-9;
 perform public.prune_campaign_visual_versions(p_id);
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision+1);
end $$;
