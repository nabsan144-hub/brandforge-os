-- Unknown historical alignment is not a claim of correctness. New rows are
-- unchanged since generation; a later copy edit requires an explicit review.
alter table public.campaigns add column if not exists visual_review_state text not null default 'unknown'
 check(visual_review_state in ('unknown','unchanged','review_required'));
alter table public.campaigns alter column visual_review_state set default 'unchanged';
alter table public.campaigns add column if not exists visual_review_ack_revision integer;
alter table public.campaigns add column if not exists visual_review_ack_at timestamptz;
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
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision+1);
end $$;

-- An owner acknowledges only the current version. This neither changes files
-- nor certifies their accuracy, consumes quota, or creates a text revision.
create or replace function public.acknowledge_visual_review(p_uid uuid,p_id uuid,p_revision integer)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns;
begin
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 if c.revision is distinct from p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 if c.visual_review_ack_revision=c.revision and c.visual_review_ack_at is not null then
  return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision,'replayed',true);
 end if;
 update public.campaigns set visual_review_ack_revision=c.revision,visual_review_ack_at=now() where id=p_id;
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision,'replayed',false);
end $$;
revoke execute on function public.edit_campaign(uuid,uuid,int,jsonb),public.acknowledge_visual_review(uuid,uuid,int) from public,anon,authenticated;
grant execute on function public.edit_campaign(uuid,uuid,int,jsonb),public.acknowledge_visual_review(uuid,uuid,int) to service_role;
