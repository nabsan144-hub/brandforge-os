-- Reusable client brand context. Browser writes cannot bypass validation.
create table if not exists public.brand_profiles (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users on delete cascade,
 name text not null, data jsonb not null default '{}',created_at timestamptz not null default now(),updated_at timestamptz not null default now()
);
create index if not exists brand_profiles_owner on public.brand_profiles(user_id,updated_at desc);
alter table public.brand_profiles enable row level security;
revoke all on public.brand_profiles from public,anon,authenticated;
grant select,insert,update,delete on public.brand_profiles to service_role;

-- Opt-in feedback, not a claim of real customer traction. Does not contain
-- prompts, contacts, images or keys. Account deletion cascades these records.
create table if not exists public.product_feedback (
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,
 campaign_id uuid references public.campaigns on delete set null,
 usable boolean,minutes_saved integer check(minutes_saved between 0 and 600),
 note text check(length(note)<=1000),created_at timestamptz not null default now()
);
alter table public.product_feedback enable row level security;
revoke all on public.product_feedback from public,anon,authenticated;
grant select,insert,update,delete on public.product_feedback to service_role;

create table if not exists public.campaign_revisions (
 campaign_id uuid not null references public.campaigns on delete cascade,
 user_id uuid not null references auth.users on delete cascade,
 revision integer not null, snapshot jsonb not null,created_at timestamptz not null default now(),
 primary key(campaign_id,revision)
);
alter table public.campaign_revisions enable row level security;
revoke all on public.campaign_revisions from public,anon,authenticated;
grant select,insert,update,delete on public.campaign_revisions to service_role;

create or replace function public.edit_campaign(p_uid uuid,p_id uuid,p_revision integer,p_changes jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; statuses jsonb; key text;
begin
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 if c.revision<>p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 insert into public.campaign_revisions(campaign_id,user_id,revision,snapshot) values(p_id,p_uid,c.revision,to_jsonb(c)-'files'-'brief');
 statuses:=c.stage_status;
 foreach key in array array['strategy','copy','seo'] loop
  if p_changes ? key then statuses:=jsonb_set(statuses,array[key],'{"state":"edited","provider":"human"}'::jsonb); end if;
 end loop;
 update public.campaigns set name=coalesce(p_changes->>'name',c.name),strategy=coalesce(p_changes->>'strategy',c.strategy),copy=coalesce(p_changes->>'copy',c.copy),seo=coalesce(p_changes->>'seo',c.seo),stage_status=statuses,revision=c.revision+1,updated_at=now() where id=p_id;
 -- Retention is explicit in the UI: the last ten saved versions.
 delete from public.campaign_revisions where campaign_id=p_id and revision<c.revision-9;
 return jsonb_build_object('ok',true,'id',p_id,'revision',c.revision+1);
end $$;

create or replace function public.save_brand(p_uid uuid,p_id uuid,p_name text,p_data jsonb)
returns uuid language plpgsql security definer set search_path=public as $$
declare result uuid;
begin
 perform pg_advisory_xact_lock(hashtext('bf_brands_'||p_uid::text));
 if length(p_name) not between 1 and 80 or octet_length(p_data::text)>100000 then raise exception 'Invalid brand'; end if;
 if p_id is not null then
  update public.brand_profiles set name=p_name,data=p_data,updated_at=now() where id=p_id and user_id=p_uid returning id into result;
  if result is null then raise exception 'Brand not found'; end if;
 else
  if (select count(*) from public.brand_profiles where user_id=p_uid)>=100 then raise exception '100 saved brand limit reached'; end if;
  insert into public.brand_profiles(user_id,name,data) values(p_uid,p_name,p_data) returning id into result;
 end if;
 return result;
end $$;
revoke execute on function public.edit_campaign(uuid,uuid,int,jsonb),public.save_brand(uuid,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.edit_campaign(uuid,uuid,int,jsonb),public.save_brand(uuid,uuid,text,jsonb) to service_role;
