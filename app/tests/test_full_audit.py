"""Regressions found in the independent full-project audit."""
import asyncio
from types import SimpleNamespace
from pathlib import Path
import pytest


def test_remote_peer_cannot_read_desktop_session_even_with_localhost_host(client):
    from fastapi.testclient import TestClient
    import server
    with TestClient(server.app, base_url='http://localhost', client=('198.51.100.9', 1234)) as remote:
        assert remote.get('/api/session').status_code == 403
        assert remote.get('/api/campaigns').status_code == 403
    assert client.get('/api/session').status_code == 200


def test_telegram_requires_loopback_and_explicit_chat_allowlist(monkeypatch):
    from gateway.telegram_bot import BrandForgeTelegramBot
    monkeypatch.delenv('TELEGRAM_ALLOWED_CHAT_IDS', raising=False)
    with pytest.raises(ValueError):
        BrandForgeTelegramBot('test-only-token-with-enough-characters', 'https://attacker.example')
    bot=BrandForgeTelegramBot('test-only-token-with-enough-characters')
    assert not bot._allowed(SimpleNamespace(message=SimpleNamespace(chat_id=123)))
    with pytest.raises(RuntimeError):
        asyncio.run(bot.start())


def test_telegram_async_lifecycle_has_ordered_start_and_cleanup(monkeypatch):
    from gateway.telegram_bot import BrandForgeTelegramBot
    monkeypatch.setenv('TELEGRAM_ALLOWED_CHAT_IDS', '123')
    calls=[]
    class Updater:
        running=False
        async def start_polling(self): self.running=True;calls.append('poll')
        async def stop(self): self.running=False;calls.append('stop-poll')
    class App:
        updater=Updater()
        async def __aenter__(self):calls.append('initialize');return self
        async def __aexit__(self,*args):calls.append('shutdown')
        async def start(self):calls.append('start')
        async def stop(self):calls.append('stop')
    bot=BrandForgeTelegramBot('test-only-token-with-enough-characters')
    monkeypatch.setattr(bot,'build_application',lambda:App())
    async def run():
        event=asyncio.Event();event.set();await bot.start(event)
    asyncio.run(run())
    assert calls==['initialize','start','poll','stop-poll','stop','shutdown']


def test_only_the_operated_cloud_is_shipped():
    root=Path(__file__).resolve().parents[2]
    assert not (root/'hosted').exists()
    assert not (root/'Dockerfile').exists()
    assert (root/'cloud/api/_lib/routes/campaigns.js').exists() and (root/'cloud/api/index.js').exists()


def test_sales_clean_pages_preserve_queries_and_unknown_routes_remain_404(client):
    assert client.get('/sales/demo').status_code == 200
    assert client.get('/sales/tour?paused=1').status_code == 200
    old = client.get('/sales/demo.html?from=email', follow_redirects=False)
    assert old.status_code == 308
    assert old.headers['location'].endswith('/sales/demo?from=email')
    assert client.get('/sales/does-not-exist').status_code == 404
    assert client.get('/sales/assets/sample/campaign.pdf').status_code == 200


def test_distinct_non_latin_brands_get_distinct_safe_ids(client):
    ids=[]
    for name in ['ایپکس کافی', 'نارتھ لائن کافی', 'एपेक्स कॉफ़ी']:
        response=client.post('/api/clients',json={'client_name':name})
        assert response.status_code==200,response.text
        ids.append(response.json()['client_id'])
    assert len(set(ids))==3


def test_update_consent_works_without_env_and_explicit_off_wins(monkeypatch):
    from modules import update_check
    monkeypatch.delenv('BRANDFORGE_UPDATE_CHECK',raising=False)
    assert update_check.allowed(True) and not update_check.allowed(False)
    monkeypatch.setenv('BRANDFORGE_UPDATE_CHECK','0')
    assert not update_check.allowed(True)


def test_repeated_brand_creation_does_not_clear_omitted_context(client):
    first=client.post('/api/clients',json={'client_name':'Persistent review brand','proof_points':'Approved source details'})
    assert first.status_code==200
    repeated=client.post('/api/clients',json={'client_name':'Persistent review brand'})
    assert repeated.status_code==200
    import server
    assert server.get_core()[2].get_client(first.json()['client_id'])['proof_points']=='Approved source details'


def test_request_snapshot_does_not_follow_concurrent_settings_changes(client):
    import server
    source=server.get_core()[0]
    with server._settings_lock:
        source.provider='offline'
        source._file_env['GROQ_API_KEY']='original-test-key'
    snap=server.request_engine()
    with server._settings_lock:
        source._file_env['GROQ_API_KEY']='changed-test-key'
    assert snap._file_env['GROQ_API_KEY']=='original-test-key'
    assert snap.config is not source.config


def test_provider_error_text_does_not_store_credentials():
    from engines.ai_engine import AIEngine
    from types import SimpleNamespace
    error=SimpleNamespace(response=SimpleNamespace(status_code=401,json=lambda:{'error':{'message':'Invalid key SECRET_VALUE'}}))
    text=AIEngine._http_error_detail(error)
    assert 'HTTP 401' in text and 'SECRET_VALUE' not in text


def test_campaign_pack_preserves_complete_reviewed_text():
    from modules.campaign_pack import build_campaign_pack
    text='Approved copy. '*1300+' END-OF-COPY'
    pack=build_campaign_pack({'product_name':'Test','strategy_text':'Strategy'}, {'copy_text':text},{},'client')
    assert 'END-OF-COPY' in pack['02_copy_pack.md']
    assert 'END-OF-COPY' in pack['01_strategy_and_approval.html']


def test_image_off_cannot_fall_back_to_public_generator(tmp_path,monkeypatch):
    import json
    from modules.mcp_registry import MCPRegistry
    import modules.image_generator as ig
    (tmp_path/'config.json').write_text(json.dumps({'image_provider':'off'}))
    monkeypatch.setattr(ig,'generate_image_bytes',lambda *a,**k:pytest.fail('Off sent a public image request'))
    result=MCPRegistry(str(tmp_path)).execute_tool('generate_image',{'prompt':'Coffee'})
    assert result['image'] is None and 'turned off' in result['note']


def test_valid_saved_model_is_not_silently_upgraded(tmp_path):
    import json
    from engines.ai_engine import AIEngine
    (tmp_path/'config.json').write_text(json.dumps({'provider':'gemini','model':'gemini-2.5-flash'}))
    assert AIEngine(provider=None,data_dir=str(tmp_path)).model=='gemini-2.5-flash'


def test_sales_mount_root_is_the_real_homepage(client):
    response=client.get('/sales/')
    assert response.status_code==200 and '<title>' in response.text and 'lang="en"' in response.text


def test_managers_of_the_same_folder_share_mutation_lock(tmp_path):
    from modules.client_manager import ClientManager
    from modules.memory_manager import MemoryManager
    from modules.project_manager import ProjectManager
    a=ClientManager(str(tmp_path));b=ClientManager(str(tmp_path));m=MemoryManager(str(tmp_path));p=ProjectManager(str(tmp_path))
    assert a._lock is b._lock is m._lock is p._lock
    m.close()


def test_groq_default_model_can_be_saved_explicitly(client):
    r=client.post('/api/settings',json={'provider':'groq','model':'openai/gpt-oss-120b','api_key':'test-only-groq-key'})
    assert r.status_code==200,r.text
    assert r.json()['model']=='openai/gpt-oss-120b'
    client.post('/api/settings',json={'provider':'offline'})
