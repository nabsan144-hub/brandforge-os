-- Optional, bounded progress metadata; does not change charging or request replay.
alter table public.generation_usage add column if not exists progress jsonb not null default '{}';
create or replace function public.set_generation_progress(p_uid uuid,p_id uuid,p_stage text,p_state text)
returns boolean language plpgsql security definer set search_path=public as $$
begin
 if p_stage not in ('strategy','copy','seo','artwork','packaging') or p_state not in ('running','generated','template','fallback','not_requested','complete') then raise exception 'Invalid progress state';end if;
 update generation_usage set progress=jsonb_set(progress,array[p_stage],to_jsonb(p_state),true)
 where id=p_id and user_id=p_uid and status='reserved';
 return found;
end $$;
revoke all on function public.set_generation_progress(uuid,uuid,text,text) from public,anon,authenticated;
grant execute on function public.set_generation_progress(uuid,uuid,text,text) to service_role;
