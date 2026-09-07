"""Real multi-connection PostgreSQL regression test. NEVER point at production.

Requires psycopg[binary] and an EMPTY database with a name ending in _test.
Set BRANDFORGE_TEST_DATABASE_URL. Roles may already exist in CI.
"""
import json
from decimal import Decimal
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import psycopg
from psycopg.conninfo import conninfo_to_dict

DSN = os.environ['BRANDFORGE_TEST_DATABASE_URL']
info = conninfo_to_dict(DSN)
assert info.get('dbname','').endswith('_test'), 'Refusing any database not suffixed _test'
ROOT = Path(__file__).resolve().parents[1]
started=time.monotonic()
with psycopg.connect(DSN,autocommit=True) as connection:
    assert not connection.execute("select 1 from pg_class where relname='campaigns' and relnamespace='public'::regnamespace").fetchone(), 'Database must be empty'
    connection.execute('create schema auth;create table auth.users(id uuid primary key,email text)')
    connection.execute("create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$")
    for role in ('anon','authenticated','service_role'):
        if not connection.execute('select 1 from pg_roles where rolname=%s',(role,)).fetchone():
            connection.execute('create role '+role+(' bypassrls' if role=='service_role' else ''))
    connection.execute('grant usage on schema public,auth to anon,authenticated,service_role')
    for migration in sorted((ROOT/'supabase/migrations').glob('*.sql')):
        connection.execute(migration.read_text())
    uid=str(uuid.uuid4());connection.execute('insert into auth.users values(%s,%s)',(uid,'concurrency@example.test'))


def call(fn,args):
    with psycopg.connect(DSN,autocommit=True) as connection:
        connection.execute('set role service_role')
        return connection.execute('select public.'+fn+'('+','.join(['%s']*len(args))+')',args).fetchone()[0]


def generate(_):
    request_id=str(uuid.uuid4())
    reserved=call('reserve_generation',(uid,request_id,'a'*64,None,50,1000,10))
    if not reserved['ok']: return reserved['code']
    payload=json.dumps({'name':'Concurrent','product':'Coffee','industry':'Food','audience':'People','benefits':'Fresh','strategy':'Strategy','copy':'Copy','seo':'Not measured','files':[]})
    call('complete_generation',(uid,request_id,payload));return 'completed'

with ThreadPoolExecutor(max_workers=8) as workers:
    outcomes=list(workers.map(generate,range(120)))
assert outcomes.count('completed')==50,outcomes
assert outcomes.count('LIMIT_MONTHLY')==70,outcomes
with psycopg.connect(DSN,autocommit=True) as connection:
    connection.execute('delete from campaigns where user_id=%s',(uid,))
assert call('generation_totals',(uid,))['campaigns_this_month']==50
assert call('reserve_generation',(uid,str(uuid.uuid4()),'a'*64,None,50,1000,10))['code']=='LIMIT_MONTHLY'
with ThreadPoolExecutor(max_workers=16) as workers:
    money=list(workers.map(lambda _:call('reserve_operator_cost',(str(uuid.uuid4()),Decimal('1.3'),10)),range(50)))
assert sum(money)==7,money
# A competing checkout must not appear while the first is still creating.
with psycopg.connect(DSN,autocommit=True) as connection:
    uid2=str(uuid.uuid4());connection.execute('insert into auth.users values(%s,%s)',(uid2,'checkout@example.test'))
with ThreadPoolExecutor(max_workers=12) as workers:
    checkouts=list(workers.map(lambda _:call('begin_checkout',(uid2,'pro','month')),range(30)))
assert sum(bool(x['ok']) for x in checkouts)==1,checkouts
# Real browser roles cannot read another user's work, or the private waitlist.
with psycopg.connect(DSN,autocommit=True) as connection:
    connection.execute('set role authenticated')
    connection.execute("select set_config('request.jwt.claim.sub',%s,false)",(uid2,))
    assert connection.execute('select count(*) from public.campaigns').fetchone()[0]==0
    try: connection.execute('select * from public.waitlist')
    except psycopg.errors.InsufficientPrivilege: pass
    else: raise AssertionError('Waitlist was readable by authenticated')
print(json.dumps({'postgres':info.get('host'),'checks':'PASS','parallel_campaign_attempts':120,'completed_exactly':50,'delete_refunds':0,'parallel_cost_attempts':50,'accepted_cost_reservations':7,'parallel_checkout_attempts':30,'accepted_checkouts':1,'seconds':round(time.monotonic()-started,2)},indent=2))
