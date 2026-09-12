"""Meaningful regression coverage for setup, CLI, maintenance and recovery.

Real temporary files/SQLite are used for persistence. Provider transports,
terminal prompts and scheduling clocks are controlled; no paid calls are made.
"""
import json
from io import StringIO
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import pytest
from rich.console import Console


@pytest.fixture
def cli(tmp_path, monkeypatch):
    import brandforge
    from engines.ai_engine import AIEngine
    from modules.project_manager import ProjectManager
    monkeypatch.setenv('BRANDFORGE_DATA_DIR',str(tmp_path/'state'))
    monkeypatch.setenv('BRANDFORGE_UPDATE_CHECK','0')
    output=StringIO();monkeypatch.setattr(brandforge,'console',Console(file=output,width=160,color_system=None))
    engine=AIEngine(provider='offline',data_dir=str(tmp_path/'state'))
    manager=ProjectManager(base_dir=engine.base_dir)
    yield brandforge,engine,manager,output
    engine.memory.close()


def answers(monkeypatch, module, values):
    queue=iter(values);calls=[]
    def ask(prompt,*args,**kwargs):
        calls.append((prompt,kwargs));return next(queue)
    monkeypatch.setattr(module.Prompt,'ask',ask)
    return calls


@pytest.mark.parametrize('raw,expected',[('200',200),('$1,200/mo',1200),(' 12.50/month ',12.5),('.25',.25),('',0),('0',0)])
def test_spend_parser_valid(raw,expected):
    import brandforge
    assert brandforge._parse_spend(raw)==expected


@pytest.mark.parametrize('raw',['-20','1e6','NaN','inf','1.2.3','1,23','$','1000001','2 apples'])
def test_spend_parser_never_changes_invalid_numbers_into_savings(raw):
    import brandforge
    with pytest.raises(ValueError):brandforge._parse_spend(raw)


def test_cli_banner_does_not_advertise_disabled_vector_memory(cli,monkeypatch):
    import importlib.util
    module,engine,_,output=cli
    monkeypatch.setattr(importlib.util,'find_spec',lambda name:object())
    text=module._capability_line();assert 'Vector' not in text and 'Telegram' in text
    engine.clients.save_named_client({'client_name':'[not-a-tag] Brand'})
    module.display_banner(engine.clients)
    assert 'BRANDFORGE OS' in output.getvalue()


def test_cli_cancel_does_not_claim_previous_online_provider_is_offline(cli,monkeypatch):
    module,engine,_,output=cli
    assert engine.save_api_key('test-key-for-groq',provider='groq')
    calls=answers(monkeypatch,module,['2',''])
    assert module._configure_engine(engine) is False
    assert engine.provider=='groq' and 'Current provider: groq' in output.getvalue()
    assert calls[1][1]['password'] is True


def test_cli_failed_key_save_is_not_reported_as_saved(cli,monkeypatch):
    module,engine,_,output=cli
    answers(monkeypatch,module,['1','short'])
    assert module._configure_engine(engine) is False
    assert engine.provider=='offline' and 'not saved' in output.getvalue()


def test_cli_saves_connected_then_offline_preferences(cli,monkeypatch):
    module,engine,_,_=cli
    answers(monkeypatch,module,['1','test-valid-key'])
    assert module._configure_engine(engine)
    assert json.loads(Path(engine.config_file).read_text())['provider']=='groq'
    answers(monkeypatch,module,['5'])
    assert module._configure_engine(engine)
    assert engine.provider=='offline'
    with pytest.raises(ValueError):module._persist_provider(engine,'unknown')


@pytest.mark.parametrize('reachable',[False,True])
def test_ollama_choice_is_honest(cli,monkeypatch,reachable):
    module,engine,_,output=cli
    answers(monkeypatch,module,['4'])
    monkeypatch.setattr(engine,'check_ollama_alive',lambda:reachable)
    assert module._configure_engine(engine) is reachable
    assert engine.provider==('ollama' if reachable else 'offline')
    assert 'fully offline' not in output.getvalue()


def test_cli_chat_and_campaign_use_the_active_brand(cli,monkeypatch):
    module,engine,manager,_=cli
    cid,_=engine.clients.save_named_client({'client_name':'نیا برانڈ','industry':'Coffee'})
    engine.clients.set_active_client(cid)
    module.run_free_command_mode(engine,'Product: Coffee, Benefits: Fresh beans')
    assert engine.memory.get_recent_chat_history(client_id=cid)
    folder=module.run_swarm_campaign(engine,manager,'Coffee','Coffee','Drinkers','Fresh beans','Scoped campaign','ur')
    data=manager.get_campaign(Path(folder).name)
    assert data['client_id']==cid and data['lang']=='ur'
    assert 'Scoped campaign' not in Path(folder).name  # filesystem-safe generated name


@pytest.mark.parametrize('choice,prompts',[
 ('4',[]),('5',[]),('6',['Coffee','Coffee','Drinkers']),('7',['Coffee','Fresh beans','Drinkers']),
 ('8',['Coffee','Fresh beans']),('9',[]),('12',['yes','دوسرا برانڈ','Coffee','Calm','#112233','#ffffff']),
 ('13',['Coffee','','200'])])
def test_cli_menu_real_local_actions(cli,monkeypatch,choice,prompts):
    module,engine,manager,output=cli
    answers(monkeypatch,module,prompts)
    module._menu_action(choice,engine,manager,'en')
    assert output.getvalue()
    if choice=='8':assert (Path(engine.base_dir)/'output/visual_preview.svg').is_file()
    if choice=='13':assert (Path(engine.base_dir)/'output/audit_scorecard.html').is_file()
    if choice=='12':assert any(c['client_name']=='دوسرا برانڈ' for c in engine.clients.list_clients())


def test_cli_chat_loop_menu_errors_and_unknown_messages(cli,monkeypatch):
    module,engine,manager,output=cli
    answers(monkeypatch,module,['hello','exit']);module.run_free_command_mode(engine)
    answers(monkeypatch,module,['hello again','13','Coffee','','-1','0'])
    module.interactive_menu(engine,manager)
    assert 'not completed' in output.getvalue()


@pytest.mark.parametrize('result',[{'error':'blocked'},{'audit':{'score':None}},{'audit':{'score':80,'method':'fixture'},'recommendations':['Review title']}])
def test_cli_site_check_never_reports_failed_inspection_clean(cli,monkeypatch,result):
    from modules.web_searcher import WebSearcher
    module,engine,manager,output=cli
    answers(monkeypatch,module,['https://example.test'])
    monkeypatch.setattr(WebSearcher,'deep_competitor_analysis',lambda self,url:result)
    module._menu_action('3',engine,manager,'en')
    assert ('did not complete' in output.getvalue()) == (result.get('audit',{}).get('score') is None)


def test_onboarding_stops_its_own_server(cli,monkeypatch):
    module,engine,manager,output=cli
    answers(monkeypatch,module,['5','no'])
    stopped=[];opened=[]
    handle=SimpleNamespace(url='http://127.0.0.1:9876/',stop=lambda:stopped.append(True) or True)
    monkeypatch.setattr(module,'_start_server_thread',lambda *a:handle)
    monkeypatch.setattr(module.console,'input',lambda *a:'')
    import webbrowser
    monkeypatch.setattr(webbrowser,'open',lambda url:opened.append(url))
    module.run_onboard(engine,manager)
    assert stopped==[True] and opened==[handle.url]


def test_onboarding_never_opens_an_unconfirmed_server(cli,monkeypatch):
    module,engine,manager,output=cli
    answers(monkeypatch,module,['5','no'])
    monkeypatch.setattr(module,'_start_server_thread',lambda *a:None)
    import webbrowser
    monkeypatch.setattr(webbrowser,'open',lambda *a:pytest.fail('opened an unconfirmed server'))
    module.run_onboard(engine,manager)
    assert 'did not start' in output.getvalue()


@pytest.mark.parametrize('host,port',[('0.0.0.0',8000),('192.168.1.1',8000),('example.com',8000),('127.0.0.1',-1),('::',8000)])
def test_all_cli_server_bind_paths_refuse_public_targets(host,port):
    from modules.desktop_launcher import validate_bind
    with pytest.raises(ValueError):validate_bind(host,port)


def test_managed_server_does_not_mistake_another_listener_for_readiness():
    from modules.desktop_launcher import start_background
    with socket.socket() as busy:
        busy.bind(('127.0.0.1',0));busy.listen()
        assert start_background(port=busy.getsockname()[1],timeout=1) is None


def test_setup_invalid_state_never_crashes(tmp_path,monkeypatch):
    import setup_env
    monkeypatch.setattr(setup_env,'ROOT',tmp_path);monkeypatch.setattr(setup_env,'STATE',tmp_path/'setup-state.json')
    monkeypatch.setattr(setup_env,'REQUIREMENTS',tmp_path/'requirements.txt')
    (tmp_path/'requirements.txt').write_text('example==1\n')
    monkeypatch.setattr(setup_env,'installed_versions',lambda:{'example':'1'})
    for bad in ['null','[]','"string"','{not json}','{}']:
        setup_env.STATE.write_text(bad);assert setup_env.configured() is False
    setup_env.record();assert setup_env.configured()
    monkeypatch.setattr(setup_env,'installed_versions',lambda:{'example':'2'})
    assert not setup_env.configured()


def test_setup_missing_distribution_and_partial_write_leave_no_false_marker(tmp_path,monkeypatch):
    import setup_env
    monkeypatch.setattr(setup_env,'ROOT',tmp_path);monkeypatch.setattr(setup_env,'STATE',tmp_path/'setup-state.json')
    monkeypatch.setattr(setup_env,'REQUIREMENTS',tmp_path/'requirements.txt')
    setup_env.REQUIREMENTS.write_text('# Core\nexample>=1\n')
    monkeypatch.setattr(setup_env.metadata,'version',lambda _: (_ for _ in ()).throw(setup_env.metadata.PackageNotFoundError()))
    with pytest.raises(setup_env.metadata.PackageNotFoundError):setup_env.record()
    assert not setup_env.STATE.exists()
    monkeypatch.setattr(setup_env.metadata,'version',lambda _:'1')
    monkeypatch.setattr(setup_env.os,'replace',lambda *a: (_ for _ in ()).throw(OSError('disk')))
    with pytest.raises(OSError):setup_env.record()
    assert not list(tmp_path.glob('.setup-state-*'))


def test_setup_checks_never_run_pip_and_install_orders_checks_before_record(tmp_path,monkeypatch):
    import setup_env
    monkeypatch.setattr(setup_env,'ROOT',tmp_path);monkeypatch.setattr(setup_env,'STATE',tmp_path/'setup-state.json')
    calls=[]
    monkeypatch.setattr(setup_env.subprocess,'run',lambda command,**kw:calls.append(command))
    monkeypatch.setattr(sys,'argv',['setup_env.py','--check'])
    assert setup_env.main()==1 and not calls
    setup_env.install()
    assert [c[2] for c in calls[:3]]==['venv','pip','pip']
    assert calls[2][-1]=='check' and calls[3][-1]=='--record'


def test_settings_pair_rolls_back_if_second_write_fails(tmp_path,monkeypatch):
    from modules import settings_store as store
    old_config=b'{"provider":"offline"}\n';old_env=b'EXISTING="secret"\n'
    (tmp_path/'config.json').write_bytes(old_config);(tmp_path/'.env').write_bytes(old_env)
    original=store.atomic_write_bytes;failed=[]
    def write(path,data,**kw):
        if Path(path).name=='config.json' and not failed:
            failed.append(True);raise OSError('disk failure')
        original(path,data,**kw)
    monkeypatch.setattr(store,'atomic_write_bytes',write)
    with pytest.raises(store.SettingsStorageError):store.commit(tmp_path,{'provider':'groq'},'NEW="key"\n')
    assert (tmp_path/'config.json').read_bytes()==old_config and (tmp_path/'.env').read_bytes()==old_env
    assert not (tmp_path/store.JOURNAL).exists()


def test_settings_restart_recovers_interrupted_file_pair(tmp_path,monkeypatch):
    from modules import settings_store as store
    old=b'{"provider":"offline"}\n';(tmp_path/'config.json').write_bytes(old)
    original=store.atomic_write_bytes
    def interrupted(path,data,**kw):
        if Path(path).name=='config.json':raise SystemExit('simulated interruption')
        original(path,data,**kw)
    monkeypatch.setattr(store,'atomic_write_bytes',interrupted)
    with pytest.raises(SystemExit):store.commit(tmp_path,{'provider':'groq'},'GROQ_API_KEY="new"\n')
    assert (tmp_path/store.JOURNAL).exists()
    monkeypatch.setattr(store,'atomic_write_bytes',original)
    assert store.recover(tmp_path)
    assert (tmp_path/'config.json').read_bytes()==old and not (tmp_path/'.env').exists()


def test_invalid_settings_journal_and_corrupt_config_are_preserved(tmp_path):
    from modules.settings_store import recover,JOURNAL,SettingsStorageError
    from engines.ai_engine import AIEngine
    path=tmp_path/JOURNAL;path.write_text('{bad')
    with pytest.raises(SettingsStorageError):recover(tmp_path)
    assert path.read_text()=='{bad'
    path.unlink();config=tmp_path/'config.json';config.write_text('[]')
    with pytest.raises(SettingsStorageError):AIEngine(data_dir=str(tmp_path))
    assert config.read_text()=='[]'


def test_failed_settings_write_is_not_reported_success(client,monkeypatch):
    import server
    engine=server.get_core()[0]
    monkeypatch.setattr(engine,'update_configuration',lambda *a,**k:False)
    engine.settings_error='Not saved'
    assert client.post('/api/settings',json={'provider':'offline'}).status_code==503
    assert client.post('/api/update-consent',json={'enabled':True}).status_code==503


def test_combined_invalid_settings_does_not_partially_save_text_key(client):
    import server
    engine=server.get_core()[0]
    old=Path(engine.env_file).read_bytes() if Path(engine.env_file).exists() else None
    r=client.post('/api/settings',json={'provider':'groq','api_key':'valid-test-key','image_provider':'not-a-provider'})
    assert r.status_code==400
    assert (Path(engine.env_file).read_bytes() if Path(engine.env_file).exists() else None)==old
    assert engine.provider=='offline'


@pytest.mark.parametrize('name,value',[('approvals.json','[]'),('approvals.json','{bad'),('performance.json','null'),('performance.json','{"a":[{"spend":"bad"}]}')])
def test_unreadable_local_state_is_not_replaced(tmp_path,name,value):
    from modules.approval_manager import ApprovalManager
    from modules.performance_tracker import PerformanceTracker
    from modules.state_io import LocalStateError
    path=tmp_path/name;path.write_text(value)
    with pytest.raises(LocalStateError):
        if name=='approvals.json':ApprovalManager(str(tmp_path)).create('draft')
        else:PerformanceTracker(str(tmp_path)).add_entry('draft',5)
    assert path.read_text()==value


def test_memory_failure_is_honest_and_full_response_is_kept(tmp_path,monkeypatch):
    from modules.memory_manager import MemoryManager
    from modules.mcp_registry import MCPRegistry
    import modules.memory_manager as module
    with MemoryManager(str(tmp_path)) as memory:
        long='x'*9000+' END'
        assert memory.add_chat('assistant',long,'brand')
        assert memory.get_recent_chat_history(client_id='brand')[0]['message']==long
        monkeypatch.setattr(module,'atomic_write_text',lambda *a,**kw: (_ for _ in ()).throw(OSError('full')))
        assert memory.save_long_term('title','note','brand') is False
        registry=MCPRegistry(str(tmp_path));monkeypatch.setattr(registry,'_get_memory',lambda:memory)
        assert 'error' in registry.execute_tool('save_memory',{'key':'title','value':'note'})


def test_daemon_lifecycle_and_scheduling(tmp_path,monkeypatch):
    import daemon
    monkeypatch.setenv('BRANDFORGE_DATA_DIR',str(tmp_path))
    jobs=[]
    class Scheduler:
        running=False
        def add_job(self,fn,kind,**kw):jobs.append((fn,kind,kw))
        def start(self):self.running=True
        def shutdown(self):self.running=False
    monkeypatch.setattr(daemon,'BackgroundScheduler',Scheduler);monkeypatch.setattr(daemon,'HAS_SCHEDULER',True)
    worker=daemon.BrandForgeDaemon();assert worker.start() and worker.start()
    assert len(jobs)==3 and {j[2]['id'] for j in jobs}=={'heartbeat','daily_summary','memory_cleanup'}
    assert worker.stop() and not worker.is_running
    monkeypatch.setattr(daemon,'HAS_SCHEDULER',False)
    assert daemon.BrandForgeDaemon().start() is False


def test_daemon_real_rotation_summary_and_explicit_retention(tmp_path,monkeypatch):
    import daemon
    from modules.memory_manager import MemoryManager
    from modules.client_manager import ClientManager
    monkeypatch.setenv('BRANDFORGE_DATA_DIR',str(tmp_path))
    worker=daemon.BrandForgeDaemon();assert worker.heartbeat()
    logfile=tmp_path/'output/daemon.log';logfile.write_bytes(b'x'*1_000_001)
    assert worker.heartbeat() and logfile.stat().st_size<1000 and Path(str(logfile)+'.1').stat().st_size==1_000_001
    assert worker.daily_summary()
    cid=ClientManager(str(tmp_path)).get_active_client()['client_id']
    with MemoryManager(str(tmp_path)) as memory:
        assert 'Daily Summary' in memory.get_long_term_memory(cid)
        for i in range(5):memory.add_chat('user',str(i))
        monkeypatch.delenv('BRANDFORGE_MEMORY_MAX_ROWS',raising=False);assert worker.memory_cleanup()==0
        assert memory.count_history()==5
        monkeypatch.setenv('BRANDFORGE_MEMORY_MAX_ROWS','bad');assert worker.memory_cleanup() is False
        monkeypatch.setenv('BRANDFORGE_MEMORY_MAX_ROWS','2');assert worker.memory_cleanup()==3
        assert memory.count_history()==2


def test_daemon_failed_rotation_does_not_grow_log(tmp_path,monkeypatch):
    import daemon
    monkeypatch.setenv('BRANDFORGE_DATA_DIR',str(tmp_path))
    path=tmp_path/'output/daemon.log';path.parent.mkdir();path.write_bytes(b'x'*1_000_001)
    worker=daemon.BrandForgeDaemon()
    monkeypatch.setattr(daemon.os,'replace',lambda *a: (_ for _ in ()).throw(OSError('permission')))
    assert worker.heartbeat() is False and path.stat().st_size==1_000_001


def test_cli_main_honors_server_override_without_changing_saved_preference(cli,monkeypatch):
    module,engine,_,_=cli
    assert engine.save_api_key('old-provider-test-key',provider='groq')
    observed=[]
    monkeypatch.setattr(module,'run_server_mode',lambda host,port,selected,opened:observed.append((host,port,selected.provider,opened)))
    monkeypatch.setattr(sys,'argv',['brandforge','--server','--provider','offline','--port','8769','--open-browser'])
    assert module.main()==0
    assert observed==[('127.0.0.1',8769,'offline',True)]
    assert json.loads(Path(engine.config_file).read_text())['provider']=='groq'


@pytest.mark.parametrize('arguments',[['--product','Coffee'],['--port','0'],['--host','0.0.0.0','--server'],['--open-browser'],['--server','--onboard']])
def test_cli_invalid_modes_fail_before_launch(cli,monkeypatch,arguments):
    module,_,_,_=cli
    monkeypatch.setattr(module,'get_engine',lambda **kw:pytest.fail('invalid arguments initialized the engine'))
    monkeypatch.setattr(sys,'argv',['brandforge']+arguments)
    with pytest.raises(SystemExit) as error:module.main()
    assert error.value.code==2


def test_cli_main_creates_real_offline_campaign(cli,monkeypatch):
    module,engine,_,_=cli
    monkeypatch.setattr(sys,'argv',['brandforge','--provider','offline','--product','Coffee','--campaign-name','CLI proof','--lang','es'])
    assert module.main()==0
    from modules.project_manager import ProjectManager
    manager=ProjectManager(engine.base_dir)
    row=next(c for c in manager.list_campaigns() if 'cli_proof' in c['name'])
    assert manager.get_campaign(row['name'])['lang']=='es'


def test_cli_main_catches_unreadable_config_without_traceback(cli,monkeypatch):
    module,engine,_,output=cli
    Path(engine.config_file).write_text('{broken')
    monkeypatch.setattr(sys,'argv',['brandforge','--product','Coffee','--campaign-name','bad config'])
    assert module.main()==1
    assert 'not completed' in output.getvalue()


def test_managed_server_serves_then_stops_its_actual_bound_socket():
    from modules.desktop_launcher import start_background
    import urllib.request
    handle=start_background(port=0,timeout=5)
    assert handle is not None
    try:
        assert handle.port>0
        with urllib.request.urlopen(handle.url+'health',timeout=3) as response:
            assert json.load(response)['name']=='BrandForge OS'
    finally:
        assert handle.stop()
    with socket.socket() as client:
        assert client.connect_ex(('127.0.0.1',handle.port))!=0


@pytest.mark.parametrize('url',['https://example.test:0/','ftp://example.test/','https://user:secret@example.test','https://example.test/path with spaces'])
def test_public_fetch_refuses_invalid_url_before_exchange(monkeypatch,url):
    from modules import public_http
    monkeypatch.setattr(public_http,'_exchange',lambda *a,**kw:pytest.fail('invalid URL reached exchange'))
    with pytest.raises(public_http.PublicFetchError):public_http.fetch_public(url)


@pytest.mark.parametrize('options',[{'max_bytes':-1},{'max_bytes':True},{'max_bytes':0},{'timeout':float('nan')},{'timeout':float('inf')},{'timeout':0}])
def test_public_fetch_limits_are_validated_before_dns(monkeypatch,options):
    from modules import public_http
    monkeypatch.setattr(public_http,'resolve_public',lambda *a,**kw:pytest.fail('invalid options reached DNS'))
    with pytest.raises(public_http.PublicFetchError):public_http.fetch_public('https://example.test',**options)


def test_memory_false_write_result_is_exposed_by_chat(client,monkeypatch):
    import server
    engine=server.get_core()[0]
    monkeypatch.setattr(engine.memory,'add_chat',lambda *a,**k:False)
    response=client.post('/api/chat',json={'message':'Hello'})
    assert response.status_code==200 and response.json()['memory_saved'] is False


def test_corrupt_local_approval_file_returns_service_error_without_replacing_data(client):
    import server
    path=Path(server.get_approvals().path);path.write_text('{preserve-this')
    response=client.get('/api/approvals')
    assert response.status_code==503 and 'preserved' in response.json()['detail']
    assert path.read_text()=='{preserve-this'


def test_foreground_browser_opens_only_after_this_server_started(monkeypatch):
    import modules.desktop_launcher as launcher
    import webbrowser
    import threading
    opened=threading.Event();seen=[]
    class Server:
        started=False
        def run(self):
            assert not seen
            self.started=True
            assert opened.wait(2)
    server=Server();monkeypatch.setattr(launcher,'make_server',lambda *a:server)
    def open_browser(url):seen.append(url);opened.set()
    monkeypatch.setattr(webbrowser,'open',open_browser)
    launcher.run_foreground(host='::1',port=8005,open_browser=True)
    assert seen==['http://[::1]:8005/']


def test_foreground_failure_does_not_open_browser(monkeypatch):
    import modules.desktop_launcher as launcher
    import webbrowser
    class Server:
        started=False
        def run(self):raise OSError('bind failure')
    monkeypatch.setattr(launcher,'make_server',lambda *a:Server())
    monkeypatch.setattr(webbrowser,'open',lambda *a:pytest.fail('opened failed server'))
    with pytest.raises(OSError):launcher.run_foreground(open_browser=True)


def test_server_receives_exact_cli_engine_snapshot(cli):
    import server
    from modules.desktop_launcher import make_server
    _,engine,_,_=cli
    original=(server._engine,server._pm,server._cm,server._tools,server._approvals)
    try:
        configured=make_server(engine=engine,port=0)
        assert server._engine is engine and server._cm is engine.clients
        assert configured.config.proxy_headers is False
    finally:
        server._engine,server._pm,server._cm,server._tools,server._approvals=original


def test_daemon_start_and_stop_failures_are_not_success(monkeypatch,tmp_path):
    import daemon
    monkeypatch.setenv('BRANDFORGE_DATA_DIR',str(tmp_path))
    worker=daemon.BrandForgeDaemon()
    class Broken:
        running=True
        def add_job(self,*a,**k):raise RuntimeError('cannot schedule')
        def shutdown(self):raise RuntimeError('cannot stop')
    worker.scheduler=Broken()
    assert worker.start() is False and not worker.is_running
    worker.is_running=True
    assert worker.stop() is False and worker.is_running


def test_daemon_summary_failure_is_reported(monkeypatch,tmp_path):
    import daemon
    from modules.memory_manager import MemoryManager
    monkeypatch.setenv('BRANDFORGE_DATA_DIR',str(tmp_path))
    monkeypatch.setattr(MemoryManager,'save_long_term',lambda *a,**k:False)
    assert daemon.BrandForgeDaemon().daily_summary() is False


def test_setup_main_success_record_and_install_paths(tmp_path,monkeypatch):
    import setup_env
    calls=[]
    monkeypatch.setattr(setup_env,'configured',lambda:True)
    monkeypatch.setattr(sys,'argv',['setup','--check']);assert setup_env.main()==0
    monkeypatch.setattr(setup_env,'record',lambda:calls.append('record'))
    monkeypatch.setattr(sys,'argv',['setup','--record']);assert setup_env.main()==0
    monkeypatch.setattr(setup_env,'install',lambda:calls.append('install'))
    monkeypatch.setattr(sys,'argv',['setup','--install']);assert setup_env.main()==0
    assert calls==['record','install']


def test_empty_and_unsupported_setup_requirements_rejected(tmp_path,monkeypatch):
    import setup_env
    monkeypatch.setattr(setup_env,'REQUIREMENTS',tmp_path/'requirements.txt')
    for text in ['', '# comment\n', '-r unknown.txt\n']:
        setup_env.REQUIREMENTS.write_text(text)
        with pytest.raises(RuntimeError):setup_env.installed_versions()


def test_memory_tail_is_bounded_but_includes_latest_note(tmp_path):
    from modules.memory_manager import MemoryManager
    with MemoryManager(str(tmp_path)) as memory:
        Path(memory.long_term_file).write_text('x'*100000+'LATEST ENTRY')
        text=memory.get_long_term_memory()
        assert text.endswith('LATEST ENTRY') and len(text)<=5000
        assert not memory.add_chat('assistant','x'*30001)
        assert memory.count_history()==0
