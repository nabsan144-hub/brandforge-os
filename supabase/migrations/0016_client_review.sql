-- Scoped, revocable bearer review; no public table access or workspace login.
create table public.campaign_review_links (
 id uuid primary key default gen_random_uuid(),
 campaign_id uuid not null unique references public.campaigns(id) on delete cascade,
 user_id uuid not null references auth.users(id) on delete cascade,
 token_hash text not null unique check(token_hash ~ '^[a-f0-9]{64}$'),
 revision integer not null check(revision>0),
 expires_at timestamptz not null,
 revoked_at timestamptz,
 status text not null default 'pending' check(status in ('pending','approved','changes_requested')),
 comments jsonb not null default '[]' check(jsonb_typeof(comments)='array' and jsonb_array_length(comments)<=100 and octet_length(comments::text)<250000),
 created_at timestamptz not null default now()
);
alter table public.campaign_review_links enable row level security;
revoke all on public.campaign_review_links from public,anon,authenticated;
grant select,insert,update,delete on public.campaign_review_links to service_role;

create function public.manage_campaign_review(p_uid uuid,p_id uuid,p_revision integer,p_hash text,p_days integer)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c public.campaigns; r public.campaign_review_links;
begin
 -- Same owner deletion lock used by generation; prevent a new link during erasure.
 perform 1 from public.profiles where id=p_uid and not deletion_pending for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 select * into c from public.campaigns where id=p_id and user_id=p_uid for update;
 if not found then return jsonb_build_object('ok',false,'code','NOT_FOUND'); end if;
 if p_hash is null then
  update public.campaign_review_links set revoked_at=now() where campaign_id=p_id and user_id=p_uid;
  return jsonb_build_object('ok',true,'revoked',true);
 end if;
 if c.revision<>p_revision or not coalesce((c.visual_review_state='unchanged' or (c.visual_review_ack_revision=c.revision and c.visual_review_ack_at is not null)),false) then
  return jsonb_build_object('ok',false,'code','REVIEW_REQUIRED');
 end if;
 if p_days not in (1,7,30) or p_hash !~ '^[a-f0-9]{64}$' then raise exception 'Invalid review configuration'; end if;
 insert into public.campaign_review_links(campaign_id,user_id,token_hash,revision,expires_at)
 values(p_id,p_uid,p_hash,c.revision,now()+make_interval(days=>p_days))
 on conflict(campaign_id) do update set token_hash=excluded.token_hash,revision=excluded.revision,expires_at=excluded.expires_at,revoked_at=null,status='pending',comments='[]',created_at=now()
 returning * into r;
 return jsonb_build_object('ok',true,'revision',r.revision,'expires_at',r.expires_at);
end; $$;

create function public.access_campaign_review(p_hash text,p_comment jsonb default null)
returns jsonb language plpgsql security definer set search_path=public as $$
declare r public.campaign_review_links; c public.campaigns; uid uuid; cid uuid;
begin
 select user_id,campaign_id into uid,cid from public.campaign_review_links where token_hash=p_hash;
 if not found then return jsonb_build_object('ok',false); end if;
 perform 1 from public.profiles where id=uid and not deletion_pending for share;
 if not found then return jsonb_build_object('ok',false); end if;
 -- Match manage/edit lock order; editing the campaign invalidates old review links.
 select * into c from public.campaigns where id=cid and user_id=uid for share;
 if not found then return jsonb_build_object('ok',false); end if;
 select * into r from public.campaign_review_links where token_hash=p_hash and revoked_at is null and expires_at>now() for update;
 if not found or r.revision<>c.revision then return jsonb_build_object('ok',false); end if;
 if p_comment is not null then
  if not (p_comment ?& array['request_id','name','message','decision']) or length(p_comment->>'name') not between 1 and 80
    or length(p_comment->>'message')>1500 or p_comment->>'decision' not in ('comment','approved','changes_requested')
    or (p_comment->>'request_id') !~ '^[0-9a-f-]{36}$' then raise exception 'Invalid review response'; end if;
  if exists(select 1 from jsonb_array_elements(r.comments) x where x->>'request_id'=p_comment->>'request_id') then
   if not exists(select 1 from jsonb_array_elements(r.comments) x where x-'at'=p_comment and x->>'request_id'=p_comment->>'request_id') then raise exception 'Review request ID conflict'; end if;
  else
   if jsonb_array_length(r.comments)>=100 then raise exception 'Review comment limit reached'; end if;
   update public.campaign_review_links set comments=comments || jsonb_build_array(p_comment || jsonb_build_object('at',now())),
     status=case when p_comment->>'decision'='comment' then status else p_comment->>'decision' end
     where id=r.id returning * into r;
  end if;
 end if;
 return jsonb_build_object('ok',true,'review',jsonb_build_object('revision',r.revision,'expires_at',r.expires_at,'status',r.status,'comments',r.comments),
 'campaign',jsonb_build_object('id',c.id,'name',c.name,'revision',c.revision,'strategy',c.strategy,'copy',c.copy,'seo',c.seo,
 'files',c.files,'asset_bundle_id',c.asset_bundle_id,'visual_review_state',c.visual_review_state,'visual_review_ack_revision',c.visual_review_ack_revision,'visual_review_ack_at',c.visual_review_ack_at,'visual_version_id',c.visual_version_id));
end; $$;
revoke all on function public.manage_campaign_review(uuid,uuid,integer,text,integer) from public,anon,authenticated;
revoke all on function public.access_campaign_review(text,jsonb) from public,anon,authenticated;
grant execute on function public.manage_campaign_review(uuid,uuid,integer,text,integer) to service_role;
grant execute on function public.access_campaign_review(text,jsonb) to service_role;
