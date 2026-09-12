import base64
import hashlib
import json
import uuid
import subprocess
from pathlib import Path
import pytest
from modules.portable_pack import validate, ArchiveStore


def pack():
    raw = b'<script>not executed by the archive viewer</script>'
    return {'format': 'brandforge-portable', 'version': 1, 'origin': 'desktop', 'name': 'Archive', 'sections': {'strategy': 'Strategy', 'copy': 'Copy', 'seo': 'No live audit'}, 'files': [{'name': 'landing.html', 'encoding': 'base64', 'content': base64.b64encode(raw).decode(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}]}


def test_archive_is_opaque_and_no_files_are_extracted(tmp_path):
    store = ArchiveStore(str(tmp_path))
    p = pack(); key = str(uuid.uuid4())
    result = store.save(p, key)
    assert store.read(result['id']) == p
    assert not list(tmp_path.rglob('landing.html'))
    assert store.save(p, key)['replayed'] is True
    with pytest.raises(ValueError):
        store.save({**p, 'name': 'Changed'}, key)
    store.delete(key)
    assert store.list() == []


@pytest.mark.parametrize('bad', ['../leak.html', 'same/path.html', '.env', 'run.exe', '\\server.txt'])
def test_traversal_and_unsupported_files_rejected(bad):
    p = pack(); p['files'][0]['name'] = bad
    with pytest.raises(ValueError):
        validate(p)


def test_corruption_unknown_fields_versions_and_capacity(tmp_path):
    p = pack(); p['files'][0]['content'] = 'YQ=='
    with pytest.raises(ValueError): validate(p)
    with pytest.raises(ValueError): validate({**pack(), 'version': 2})
    with pytest.raises(ValueError): validate({**pack(), 'provider_key': 'not permitted'})
    store = ArchiveStore(str(tmp_path))
    for _ in range(10): store.save(pack(), str(uuid.uuid4()))
    with pytest.raises(ValueError): store.save(pack(), str(uuid.uuid4()))


def test_desktop_to_cloud_validator_to_desktop_byte_roundtrip(tmp_path):
    # Actual JS validator, no provider/auth/network mocks needed for this format.
    root = Path(__file__).resolve().parents[2]
    source = tmp_path/'portable.json'; source.write_text(json.dumps(pack()))
    script = "import {readFileSync} from 'node:fs';import {validatePortable} from './cloud/public/portable-pack.js';console.log(JSON.stringify(await validatePortable(JSON.parse(readFileSync(process.argv[1],'utf8')))));"
    r = subprocess.run(['node', '--input-type=module', '-e', script, str(source)], cwd=root, check=True, capture_output=True, text=True)
    assert validate(json.loads(r.stdout)) == pack()


def test_desktop_http_archive_workflow(client):
    key = str(uuid.uuid4()); p = pack()
    r = client.post('/api/transfers', json={'pack': p, 'request_id': key, 'consent': True})
    assert r.status_code == 200, r.text
    assert client.get('/api/transfers', params={'id': key}).json()['pack'] == p
    assert client.get('/transfer').status_code == 200
    assert client.delete('/api/transfers', params={'id': key}).status_code == 200
    assert client.get('/api/transfers', params={'id': key}).status_code == 404


def test_core_export_reports_every_omitted_file_and_shared_scripts_match(tmp_path):
    from modules.portable_pack import export_campaign
    (tmp_path/'hero_banner.svg').write_text('<svg/>')
    (tmp_path/'large.pdf').write_bytes(b'x'*2_300_000)
    class Manager:
        def get_campaign(self, name):
            return {'campaign_name': name, 'files': [{'name': n} for n in ('hero_banner.svg', 'large.pdf', 'campaign.json')]}
        def get_campaign_file(self, name, file):
            return tmp_path/file
    with pytest.raises(ValueError): export_campaign(Manager(), 'Core')
    result = export_campaign(Manager(), 'Core', core=True)
    assert [f['name'] for f in result['files']] == ['hero_banner.svg']
    assert [f['name'] for f in result['omitted_files']] == ['large.pdf']
    root = Path(__file__).resolve().parents[2]
    for name in ('portable-pack.js', 'transfer.js'):
        assert (root/'cloud/public'/name).read_bytes() == (root/'app/brandforge_assets/transfer'/name).read_bytes()
    source = tmp_path/'core.json'; source.write_text(json.dumps(result))
    script = "import {readFileSync} from 'node:fs';import {validatePortable} from './cloud/public/portable-pack.js';console.log(JSON.stringify(await validatePortable(JSON.parse(readFileSync(process.argv[1],'utf8')))));"
    run = subprocess.run(['node', '--input-type=module', '-e', script, str(source)], cwd=root, check=True, capture_output=True, text=True)
    assert validate(json.loads(run.stdout)) == result
    for invalid in ({'name': 'x'}, {'name': 'x', 'reason': 'r', 'extra': True}, {'name': 'x', 'reason': 'r'*201}):
        with pytest.raises(ValueError): validate({**result, 'omitted_files': [invalid]})
