-- Schema 2 retains a hash-bound immutable JPEG scene; no new provider call.
-- Bounded deterministic layout/canonical-field changes, preserving attribution.
create or replace function public.save_vector_correction(p_uid uuid,p_id uuid,p_revision integer,p_request uuid,p_payload jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; prior public.campaign_visual_versions; old_id uuid; new_id uuid; b public.campaign_asset_bundles;
begin
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 select * into prior from public.campaign_visual_versions where user_id=p_uid and request_id=p_request;
 if found then
  if prior.campaign_id<>p_id or prior.source_revision is distinct from p_revision or prior.payload->'fields' is distinct from p_payload->'fields' or prior.payload->'change_hash' is distinct from p_payload->'change_hash' then return jsonb_build_object('ok',false,'code','IDEMPOTENCY_CONFLICT'); end if;
  return jsonb_build_object('ok',true,'id',p_id,'revision',prior.result_revision,'replayed',true);
 end if;
 if c.revision is distinct from p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 if coalesce(c.visual_recipe->>'schema','') not in ('1','2') or (c.visual_status->>'mode'='ai' and c.visual_recipe->>'schema' is distinct from '2') then return jsonb_build_object('ok',false,'code','VISUAL_CORRECTION_UNSUPPORTED'); end if;
 if p_request is null or p_payload->'recipe'->>'schema' is distinct from c.visual_recipe->>'schema' or p_payload->'recipe'->>'scene_sha256' is distinct from c.visual_recipe->>'scene_sha256' or p_payload->'recipe'->'formats' is distinct from c.visual_recipe->'formats' or p_payload->'recipe'->'common'->'watermark' is distinct from c.visual_recipe->'common'->'watermark' or p_payload->'recipe'->'common'->'style' is distinct from c.visual_recipe->'common'->'style' or jsonb_typeof(p_payload->'files') is distinct from 'array' or jsonb_typeof(p_payload->'fields') is distinct from 'object' then raise exception 'Invalid correction payload'; end if;
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
 update public.campaigns set visual_recipe=p_payload->'recipe',asset_bundle_id=b.id,files=p_payload->'files',visual_fields=p_payload->'fields',visual_field_report=p_payload->'report',visual_version_id=new_id,revision=c.revision+1,updated_at=now(),visual_review_state='review_required',visual_review_ack_revision=null,visual_review_ack_at=null where id=p_id;
 if b.id is not null then update public.campaign_asset_bundles set state='attached',campaign_id=p_id where id=b.id; end if;
 delete from public.campaign_revisions where campaign_id=p_id and revision<c.revision-9;
 perform public.prune_campaign_visual_versions(p_id);
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision+1,'replayed',false);
end $$;

create or replace function public.finish_image_recovery(p_uid uuid,p_job uuid,p_payload jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; j public.campaign_image_jobs; old_id uuid; new_id uuid; cid uuid; b public.campaign_asset_bundles;
begin
 perform 1 from public.profiles where id=p_uid and not deletion_pending for share;
 if not found then return jsonb_build_object('ok',false,'code','ACCOUNT_UNAVAILABLE'); end if;
 select campaign_id into cid from public.campaign_image_jobs where id=p_job and user_id=p_uid;
 select * into c from public.campaigns where id=cid and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 select * into j from public.campaign_image_jobs where id=p_job and user_id=p_uid for update;
 if j.status='completed' then return jsonb_build_object('ok',true,'revision',j.result_revision,'replayed',true); end if;
 if j.status<>'running' or j.expires_at<=now() or c.revision<>j.source_revision then return jsonb_build_object('ok',false,'code','REVISION_OR_LEASE_CONFLICT'); end if;
 if ((p_payload->'recipe')-'schema'-'scene_sha256') is distinct from (c.visual_recipe-'schema') or p_payload->'recipe'->>'schema' is distinct from '2' or coalesce(p_payload->'recipe'->>'scene_sha256','') !~ '^[a-f0-9]{64}$' or p_payload->'fields' is distinct from c.visual_fields or p_payload->'status'->>'mode'<>'ai' then raise exception 'Invalid image recovery'; end if;
 if p_payload->>'bundle_id' is not null then
  select * into b from public.campaign_asset_bundles where id=(p_payload->>'bundle_id')::uuid for update;
  if not found or b.user_id is distinct from p_uid or b.source_campaign_id is distinct from c.id or b.source_revision is distinct from j.source_revision or b.state<>'pending' or b.uploaded_at is null or b.file_manifest is distinct from p_payload->'files' then raise exception 'Invalid recovered file bundle'; end if;
 elsif c.asset_bundle_id is not null then raise exception 'Private recovery requires private output';
 end if;
 old_id:=c.visual_version_id;
 if old_id is null then
  insert into public.campaign_visual_versions(campaign_id,user_id,payload) values(c.id,p_uid,jsonb_build_object('files',c.files,'recipe',c.visual_recipe,'fields',c.visual_fields,'report',c.visual_field_report,'status',c.visual_status,'bundle_id',c.asset_bundle_id)) returning id into old_id;
  update public.campaign_revisions set snapshot=jsonb_set(snapshot,'{visual_version_id}',to_jsonb(old_id)) where campaign_id=c.id and snapshot->>'visual_version_id' is null;
  c.visual_version_id:=old_id;
 end if;
 insert into public.campaign_revisions(campaign_id,user_id,revision,snapshot) values(c.id,p_uid,c.revision,to_jsonb(c)-'files'-'brief');
 insert into public.campaign_visual_versions(campaign_id,user_id,payload) values(c.id,p_uid,p_payload) returning id into new_id;
 update public.campaigns set visual_recipe=p_payload->'recipe',asset_bundle_id=b.id,files=p_payload->'files',visual_status=p_payload->'status',visual_version_id=new_id,revision=c.revision+1,updated_at=now(),visual_review_state='review_required',visual_review_ack_revision=null,visual_review_ack_at=null where id=c.id;
 if b.id is not null then update public.campaign_asset_bundles set state='attached',campaign_id=c.id where id=b.id; end if;
 update public.campaign_image_jobs set status='completed',result_revision=c.revision+1 where id=p_job;
 delete from public.campaign_revisions where campaign_id=c.id and revision<c.revision-9;
 perform public.prune_campaign_visual_versions(c.id);
 return jsonb_build_object('ok',true,'id',c.id,'revision',c.revision+1);
end; $$;
