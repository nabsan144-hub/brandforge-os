-- Independent editable projects: never import credentials, approvals or billing.
create table public.canvas_projects(id uuid primary key,user_id uuid not null references auth.users(id) on delete cascade,name text not null,revision integer not null default 1,document jsonb not null check(octet_length(document::text)<=1100000),updated_at timestamptz not null default now());
create index canvas_owner on public.canvas_projects(user_id,updated_at);
create table public.canvas_versions(project_id uuid references public.canvas_projects(id) on delete cascade,revision integer not null,document jsonb not null,primary key(project_id,revision));
create table public.canvas_requests(user_id uuid references auth.users(id) on delete cascade,request_id uuid,project_id uuid references public.canvas_projects(id) on delete cascade,request_hash text not null,result_revision integer not null,primary key(user_id,request_id));
alter table public.canvas_projects enable row level security;
alter table public.canvas_versions enable row level security;
alter table public.canvas_requests enable row level security;
revoke all on public.canvas_projects,public.canvas_versions,public.canvas_requests from public,anon,authenticated;
grant select,insert,update,delete on public.canvas_projects,public.canvas_versions,public.canvas_requests to service_role;
create function public.save_canvas(p_uid uuid,p_id uuid,p_revision integer,p_request uuid,p_hash text,p_document jsonb,p_restore integer default null)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.canvas_projects; q public.canvas_requests; d jsonb; cid uuid; plan_name text;
begin
 perform pg_advisory_xact_lock(hashtext('canvas_'||p_uid::text));
 select plan into plan_name from public.profiles where id=p_uid and not deletion_pending for share;
 if not found then return jsonb_build_object('ok',false,'code','ACCOUNT_UNAVAILABLE'); end if;
 select * into q from public.canvas_requests where user_id=p_uid and request_id=p_request;
 if found then
  if q.request_hash<>p_hash then return jsonb_build_object('ok',false,'code','IDEMPOTENCY_CONFLICT'); end if;
  return jsonb_build_object('ok',true,'id',q.project_id,'revision',q.result_revision,'replayed',true);
 end if;
 cid:=coalesce(p_id,p_request);
 select * into c from public.canvas_projects where id=cid and user_id=p_uid for update;
 if p_id is not null and not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 if c.id is not null and c.revision<>p_revision then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 if c.id is null and (p_revision<>0 or p_restore is not null or exists(select 1 from public.canvas_projects where id=cid)) then return jsonb_build_object('ok',false,'code','REVISION_CONFLICT'); end if;
 if c.id is null and (select count(*) from public.canvas_projects where user_id=p_uid)>=10 then return jsonb_build_object('ok',false,'code','TEN_PROJECT_LIMIT'); end if;
 d:=p_document;
 if p_restore is not null then
  select document into d from public.canvas_versions where project_id=cid and revision=p_restore;
  if not found then return jsonb_build_object('ok',false,'code','VERSION_UNAVAILABLE'); end if;
 end if;
 if d->>'format' is distinct from 'brandforge-canvas' or d->>'version' is distinct from '1' or octet_length(d::text)>1100000 then raise exception 'Invalid canvas'; end if;
 if plan_name='free' then d:=jsonb_set(d,'{watermark}','true'); end if;
 if c.id is null then
  insert into public.canvas_projects(id,user_id,name,document)values(cid,p_uid,left(d->>'name',80),d);
  insert into public.canvas_versions values(cid,1,d);
 else
  update public.canvas_projects set name=left(d->>'name',80),document=d,revision=c.revision+1,updated_at=now() where id=cid;
  insert into public.canvas_versions values(cid,c.revision+1,d);
 end if;
 insert into public.canvas_requests values(p_uid,p_request,cid,p_hash,coalesce(c.revision,0)+1);
 delete from public.canvas_versions where project_id=cid and revision<coalesce(c.revision,0)-8;
 delete from public.canvas_requests where project_id=cid and result_revision<coalesce(c.revision,0)-18;
 return jsonb_build_object('ok',true,'id',cid,'revision',coalesce(c.revision,0)+1);
end $$;
revoke execute on function public.save_canvas(uuid,uuid,integer,uuid,text,jsonb,integer) from public,anon,authenticated;
grant execute on function public.save_canvas(uuid,uuid,integer,uuid,text,jsonb,integer) to service_role;

create function public.export_canvas_page(p_uid uuid,p_page integer default 0)
returns jsonb language sql security definer set search_path=public as $$
 with owned as (select v.project_id,v.revision,v.document,c.name,c.updated_at from public.canvas_versions v join public.canvas_projects c on c.id=v.project_id where c.user_id=p_uid),
 n as (select count(*) as total from owned),
 page as (select * from owned order by project_id,revision offset greatest(0,p_page) limit 1)
 select jsonb_build_object('data',jsonb_build_object('canvas_versions',coalesce((select jsonb_agg(to_jsonb(page)) from page),'[]'::jsonb)), 'total',n.total,'has_more',greatest(0,p_page)+1<n.total,'next_page',case when greatest(0,p_page)+1<n.total then greatest(0,p_page)+1 else null end) from n;
$$;
revoke execute on function public.export_canvas_page(uuid,integer) from public,anon,authenticated;
grant execute on function public.export_canvas_page(uuid,integer) to service_role;
