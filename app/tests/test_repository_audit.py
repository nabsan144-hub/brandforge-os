"""Regression checks for the repository-wide audit, not production approval."""
import importlib.util
import json
from pathlib import Path
from modules.security import safe_text

ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_comparison_text_is_not_silently_deleted():
    assert safe_text('Dose < 10 mg and revenue > 20') == 'Dose < 10 mg and revenue > 20'
    assert safe_text('<script>alert(1)</script>') == 'alert(1)'


def test_pricing_structured_data_matches_visible_answers():
    script = load_script('sync_pricing_faq_jsonld')
    page = (ROOT / 'sales/pricing.html').read_text()
    assert script.sync(page, check=True) == page
    assert script.sync(script.sync(page)) == script.sync(page)


def test_cloud_private_pages_are_noindex_with_clean_urls():
    config = json.loads((ROOT / 'cloud/vercel.json').read_text())
    assert config['cleanUrls'] is True
    assert {'key': 'X-Robots-Tag', 'value': 'noindex, nofollow'} in config['headers'][0]['headers']


def test_customer_copy_does_not_overpromise_equivalence_or_languages():
    home = (ROOT / 'sales/index.html').read_text()
    pricing = (ROOT / 'sales/pricing.html').read_text()
    comparison = (ROOT / 'sales/vs-canva-ad-creator.html').read_text()
    assert 'exact in every language' not in home
    assert 'nothing is misspelled' not in home
    assert 'same engine' not in pricing
    assert 'not a custom-domain or rebranded Cloud application' in pricing
    assert 'No built-in claim checking' not in comparison


def test_release_manifest_has_no_stale_self_reference(tmp_path):
    import hashlib
    import zipfile
    import pytest
    from make_release_zip import TOP_DIR, write_release_manifest, REQUIRED_COMMON
    assert 'app/web/dist/index.html' not in REQUIRED_COMMON
    target = tmp_path / 'test.zip'
    with zipfile.ZipFile(target, 'w') as archive:
        archive.writestr(TOP_DIR + '/example.txt', 'complete file')
    write_release_manifest(target, 'source', 'a' * 40)
    with zipfile.ZipFile(target) as archive:
        manifest = json.loads(archive.read(TOP_DIR + '/RELEASE-MANIFEST.json'))
        assert len(archive.namelist()) == len(set(archive.namelist()))
        assert len(manifest['files']) == 1
        for item in manifest['files']:
            assert hashlib.sha256(archive.read(item['name'])).hexdigest() == item['sha256']
    with pytest.raises(ValueError):
        write_release_manifest(target, 'source', 'a' * 40)


def test_sales_clean_urls_redirect_and_private_notes_stay_private():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from modules.static_site import SalesStaticFiles
    app = FastAPI()
    app.mount('/', SalesStaticFiles(directory=ROOT / 'sales', html=True))
    with TestClient(app) as client:
        for path in ('pricing', 'docs', 'tools', 'demo', 'vs-canva-ad-creator'):
            response = client.get('/' + path + '.html', follow_redirects=False)
            assert response.status_code == 308
            assert response.headers['location'].endswith('/' + path)
            assert client.get('/' + path).status_code == 200
        for path in ('tests/funnel.test.js', 'package.json', 'assets/product-demo/ASSET-NOTICE.md', 'does-not-exist'):
            assert client.get('/' + path).status_code == 404


def test_sitemap_covers_every_indexable_root_page():
    script = load_script('regenerate_sitemap')
    files = {p[0] for p in script.PAGES}
    assert 'best-ad-copy-generator.html' in files
    assert 'vs-canva-ad-creator.html' in files
    assert '404.html' not in files


def test_inventory_scans_source_inside_an_ignored_parent_git_folder(tmp_path, monkeypatch):
    import importlib.util
    import subprocess
    from pathlib import Path
    script = Path(__file__).resolve().parents[2] / 'scripts/repository_inventory.py'
    spec = importlib.util.spec_from_file_location('inventory_nested_probe', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    subprocess.run(['git', 'init', str(tmp_path)], check=True, capture_output=True)
    (tmp_path / '.gitignore').write_text('.cache/\n')
    child = tmp_path / '.cache/project'
    child.mkdir(parents=True)
    (child / 'probe.py').write_text('value = 1\n')
    monkeypatch.setattr(module, 'ROOT', child)
    rows = module.inventory()
    assert [row['path'] for row in rows] == ['probe.py']
    assert rows[0]['syntax'] == 'Python AST passed'


def test_release_excludes_environment_symlink_names():
    from make_release_zip import FORBIDDEN_RES, TOP_DIR
    for name in ('cloud/node_modules', 'sales/node_modules', '.venv', 'app/venv'):
        assert any(rx.search(TOP_DIR + '/' + name) for rx in FORBIDDEN_RES)
