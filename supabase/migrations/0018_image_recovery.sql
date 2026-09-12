-- Image-only recovery: no generation allowance mutation. Operator budget still mandatory.
create table public.campaign_image_jobs (
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
 campaign_id uuid not null references public.campaigns(id) on delete cascade,request_id uuid not null,request_hash text not null,
 source_revision integer not null,result_revision integer,status text not null default 'running' check(status in ('running','completed','failed')),
 failure_code text,expires_at timestamptz not null default now()+interval '2 minutes',created_at timestamptz not null default now(),unique(user_id,request_id)
);
alter table public.campaign_image_jobs enable row level security;
revoke all on public.campaign_image_jobs from public,anon,authenticated;
grant select,insert,update,delete on public.campaign_image_jobs to service_role;
create function public.claim_image_recovery(p_uid uuid,p_id uuid,p_revision integer,p_request uuid,p_hash text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; j public.campaign_image_jobs;
begin
 perform 1 from public.profiles where id=p_uid and not deletion_pending and plan in ('pro','agency') and plan_status is distinct from 'past_due' for update;
 if not found then return jsonb_build_object('ok',false,'code','PLAN_UNAVAILABLE'); end if;
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 select * into j from public.campaign_image_jobs where user_id=p_uid and request_id=p_request;
 if found then
  if j.request_hash<>p_hash or j.campaign_id<>p_id then return jsonb_build_object('ok',false,'code','REQUEST_CONFLICT'); end if;
  return jsonb_build_object('ok',false,'code',case when j.status='running' and j.expires_at<=now() then 'EXPIRED' else upper(j.status) end,'revision',j.result_revision,'job_id',j.id);
 end if;
 if c.revision<>p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 if c.asset_bundle_id is not null or c.visual_recipe->>'schema' is distinct from '1' or c.visual_status->>'state' is distinct from 'fallback' or c.visual_status->>'mode' is distinct from 'svg' then return jsonb_build_object('ok',false,'code','RECOVERY_UNSUPPORTED'); end if;
 if exists(select 1 from public.campaign_image_jobs where campaign_id=p_id and status='running' and expires_at>now()) then return jsonb_build_object('ok',false,'code','RUNNING'); end if;
 if (select count(*) from public.campaign_image_jobs where user_id=p_uid and created_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC')>=3 then return jsonb_build_object('ok',false,'code','DAILY_RECOVERY_LIMIT'); end if;
 insert into public.campaign_image_jobs(user_id,campaign_id,request_id,request_hash,source_revision) values(p_uid,p_id,p_request,p_hash,p_revision) returning * into j;
 return jsonb_build_object('ok',true,'job_id',j.id);
end; $$;
create function public.finish_image_recovery(p_uid uuid,p_job uuid,p_payload jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; j public.campaign_image_jobs; old_id uuid; new_id uuid; cid uuid;
begin
 perform 1 from public.profiles where id=p_uid and not deletion_pending for share;
 if not found then return jsonb_build_object('ok',false,'code','ACCOUNT_UNAVAILABLE'); end if;
 select campaign_id into cid from public.campaign_image_jobs where id=p_job and user_id=p_uid;
 select * into c from public.campaigns where id=cid and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 select * into j from public.campaign_image_jobs where id=p_job and user_id=p_uid for update;
 if j.status='completed' then return jsonb_build_object('ok',true,'revision',j.result_revision,'replayed',true); end if;
 if j.status<>'running' or j.expires_at<=now() or c.revision<>j.source_revision then return jsonb_build_object('ok',false,'code','REVISION_OR_LEASE_CONFLICT'); end if;
 if p_payload->'recipe' is distinct from c.visual_recipe or p_payload->'fields' is distinct from c.visual_fields or p_payload->'status'->>'mode'<>'ai' then raise exception 'Invalid image recovery'; end if;
 old_id:=c.visual_version_id;
 if old_id is null then
  insert into public.campaign_visual_versions(campaign_id,user_id,payload) values(c.id,p_uid,jsonb_build_object('files',c.files,'recipe',c.visual_recipe,'fields',c.visual_fields,'report',c.visual_field_report,'status',c.visual_status)) returning id into old_id;
  update public.campaign_revisions set snapshot=jsonb_set(snapshot,'{visual_version_id}',to_jsonb(old_id)) where campaign_id=c.id and snapshot->>'visual_version_id' is null;
  c.visual_version_id:=old_id;
 end if;
 insert into public.campaign_revisions(campaign_id,user_id,revision,snapshot) values(c.id,p_uid,c.revision,to_jsonb(c)-'files'-'brief');
 insert into public.campaign_visual_versions(campaign_id,user_id,payload) values(c.id,p_uid,p_payload) returning id into new_id;
 update public.campaigns set files=p_payload->'files',visual_status=p_payload->'status',visual_version_id=new_id,revision=c.revision+1,updated_at=now(),visual_review_state='review_required',visual_review_ack_revision=null,visual_review_ack_at=null where id=c.id;
 update public.campaign_image_jobs set status='completed',result_revision=c.revision+1 where id=p_job;
 delete from public.campaign_revisions where campaign_id=c.id and revision<c.revision-9;
 perform public.prune_campaign_visual_versions(c.id);
 return jsonb_build_object('ok',true,'id',c.id,'revision',c.revision+1);
end; $$;
revoke all on function public.claim_image_recovery(uuid,uuid,integer,uuid,text),public.finish_image_recovery(uuid,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.claim_image_recovery(uuid,uuid,integer,uuid,text),public.finish_image_recovery(uuid,uuid,jsonb) to service_role;

-- Extend exact restore only to our own versioned recovery payloads, not legacy AI packs.
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
 if not found or c.asset_bundle_id is not null or (c.visual_status->>'mode'='ai' and c.visual_version_id is null) then return jsonb_build_object('ok',false,'code','VISUAL_CORRECTION_UNSUPPORTED'); end if;
 insert into public.campaign_revisions(campaign_id,user_id,revision,snapshot) values(p_id,p_uid,c.revision,to_jsonb(c)-'files'-'brief');
 update public.campaigns set name=snap->>'name',strategy=snap->>'strategy',copy=snap->>'copy',seo=snap->>'seo',stage_status=snap->'stage_status',visual_status=coalesce(v.payload->'status',snap->'visual_status',c.visual_status),files=v.payload->'files',visual_fields=v.payload->'fields',visual_recipe=v.payload->'recipe',visual_field_report=v.payload->'report',visual_version_id=v.id,revision=c.revision+1,updated_at=now(),visual_review_state='review_required',visual_review_ack_revision=null,visual_review_ack_at=null where id=p_id;
 delete from public.campaign_revisions where campaign_id=p_id and revision<c.revision-9;
 perform public.prune_campaign_visual_versions(p_id);
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision+1);
end $$;
