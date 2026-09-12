-- Additive upgrade: historical campaigns have unknown image provenance.
-- Do not infer a provider from an existing SVG or overwrite old data.
alter table public.campaigns add column if not exists visual_status jsonb not null
 default '{"mode":"unknown","state":"unknown"}'::jsonb
 check (jsonb_typeof(visual_status)='object');

create or replace function public.complete_generation(p_uid uuid,p_id uuid,p_campaign jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare r public.generation_usage; cid uuid; nm text;
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
  nm:=left(coalesce(nullif(p_campaign->>'name',''),p_campaign->>'product'),80);
  insert into public.campaigns(user_id,name,product,industry,audience,benefits,lang,strategy,copy,seo,
    research_live,provider,files,brief,stage_status,visual_status)
  values(p_uid,nm,left(p_campaign->>'product',80),left(coalesce(p_campaign->>'industry',''),80),
    left(coalesce(p_campaign->>'audience',''),120),left(coalesce(p_campaign->>'benefits',''),500),
    coalesce(p_campaign->>'lang','en'),p_campaign->>'strategy',p_campaign->>'copy',p_campaign->>'seo',
    false,coalesce(p_campaign->>'provider','offline'),p_campaign->'files',
    coalesce(p_campaign->'brief','{}'::jsonb),coalesce(p_campaign->'stage_status','{}'::jsonb),
    coalesce(p_campaign->'visual_status','{"mode":"unknown","state":"unknown"}'::jsonb)) returning id into cid;
  update public.generation_usage set status='completed',campaign_id=cid,completed_at=now(),provider=p_campaign->>'provider',provider_usage=coalesce(p_campaign->'provider_usage','{}'::jsonb)
    where id=p_id;
  return jsonb_build_object('id',cid,'name',nm,'replayed',false);
end $$;

revoke execute on function public.complete_generation(uuid,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.complete_generation(uuid,uuid,jsonb) to service_role;
