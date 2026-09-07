"""1.4 regressions: real local endpoints, output integrity and release boundaries."""
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from PIL import Image


def test_unknown_host_and_missing_capability_are_denied(client):
    assert client.get('/health',headers={'Host':'attacker.example','Origin':'http://attacker.example'}).status_code==400
    saved=client.headers.pop('X-BrandForge-Token')
    try:
        assert client.post('/api/swarm/run',json={'campaign_name':'Blocked','product_name':'Coffee'}).status_code==403
        assert client.get('/api/session').status_code==200
    finally:client.headers['X-BrandForge-Token']=saved


def test_real_swarm_api_honors_dimensions_logo_and_new_text_revision(client):
    made=client.post('/api/clients',json={'client_name':'Logo Regression Brand','industry':'Coffee'})
    assert made.status_code==200
    cid=made.json()['client_id']
    buffer=io.BytesIO();Image.new('RGB',(32,32),(255,0,170)).save(buffer,'PNG')
    assert client.post(f'/api/clients/{cid}/logo',files={'logo':('approved.png',buffer.getvalue(),'image/png')}).status_code==200
    run=client.post('/api/swarm/run',json={'campaign_name':'Logo size regression','product_name':'Apex Coffee','industry':'Coffee','target_audience':'Coffee drinkers','key_benefits':'Fresh-roasted beans','client_id':cid,'custom_sizes':[{'width':300,'height':250}]})
    assert run.status_code==200,run.text
    name=run.json()['campaign_name'];detail=client.get('/api/campaigns/'+name).json()
    files={f['name'] for f in detail['files']}
    banner=next(f for f in files if f.startswith('banner_') and f.endswith('.svg'))
    svg=client.get(f'/api/campaigns/{name}/files/{banner}').text
    assert 'width="300" height="250"' in svg and 'data:image/png;base64,' in svg
    png_name=banner.replace('.svg','.png')
    png=client.get(f'/api/campaigns/{name}/files/{png_name}')
    image=Image.open(io.BytesIO(png.content)).convert('RGB')
    assert image.size==(300,250)
    assert sum(1 for r,g,b in image.getdata() if r>240 and g<20 and 150<b<190)>10
    landing=client.get(f'/api/campaigns/{name}/files/landing_page.html').text
    assert 'data:image/png;base64,' in landing
    document=client.get(f'/api/campaigns/{name}/export.docx')
    with zipfile.ZipFile(io.BytesIO(document.content)) as archive:assert any(n.startswith('word/media/') for n in archive.namelist())
    original=detail['copy']['copy_text']
    revised=client.post(f'/api/campaigns/{name}/text-revision',json={'copy':'Reviewed copy. See details.'})
    assert revised.status_code==200,revised.text
    assert revised.json()['name']!=name
    assert client.get('/api/campaigns/'+name).json()['copy']['copy_text']==original
    assert client.get('/api/campaigns/'+revised.json()['name']).json()['copy']['copy_text']=='Reviewed copy. See details.'
    assert client.post('/api/swarm/run',json={'campaign_name':'Bad size','product_name':'Coffee','custom_sizes':[{'width':49,'height':250}]}).status_code==422


@pytest.mark.parametrize('benefits',['','one benefit','one; two','تازہ کافی','one, two, three'])
def test_generate_copy_accepts_zero_one_and_many_benefits(client,benefits):
    response=client.post('/api/tools/execute',json={'tool_name':'generate_copy','args':{'product':'Apex Coffee','benefits':benefits,'audience':'Coffee drinkers'}})
    assert response.status_code==200,response.text
    assert 'error' not in response.json()['result']


def test_tool_argument_failure_is_not_reported_as_success(client):
    response=client.post('/api/tools/execute',json={'tool_name':'generate_copy','args':{'unknown_argument':True}})
    assert response.status_code==422 and response.json()['success'] is False


def test_long_quality_pass_preserves_all_sections_and_facts():
    from engines.ai_engine import AIEngine
    from modules.draft_integrity import preserves_draft
    draft='AIDA\n'+('Fresh coffee. '*180)+'\nPAS\nA clear choice.\nWelcome Email\nSubject: Hello\nHero Headline\nApex\nCTA: https://example.test/offer at $20'
    engine=AIEngine(provider='offline')
    refined=engine._offline_smart_generate('DRAFT:\n'+draft,{'agent':'sentinel'})
    assert draft in refined
    assert preserves_draft(draft,refined)
    assert not preserves_draft(draft,draft[:2000])


def test_storage_does_not_cut_text_or_binary(tmp_path):
    from modules.project_manager import ProjectManager
    text='x'*250001
    file=tmp_path/'full.svg';ProjectManager._write_artifact(str(file),text)
    assert file.read_text()==text
    with pytest.raises(ValueError):ProjectManager._write_artifact(str(tmp_path/'bad.png'),b'x'*5000001)
    assert not (tmp_path/'bad.png').exists()


@pytest.mark.parametrize('brand',['Apex Coffee','A very long international brand name that must fit without clipping','ایپکس کافی','अपेक्स कॉफ़ी','Café Português'])
def test_measured_text_bounds_for_every_preset_and_edge_size(brand):
    from modules.visual_designer import AD_SIZES
    from modules.visual_layout import banner_svg,logo_svg
    for w,h in [tuple(v[:2]) for v in AD_SIZES.values()]+[(50,50),(5000,50),(50,5000),(999,333)]:
        svg=ET.fromstring(banner_svg(brand,'Approved benefit',w,h))
        for node in svg.iter():
            if 'data-box' in node.attrib:
                x,y,width,height=map(float,node.attrib['data-box'].split(','))
                assert x>=-.01 and y>=-.01 and x+width<=w+.01 and y+height<=h+.01,(brand,w,h,node.attrib)
    bodies=[]
    for style in ['wordmark','lettermark','combination','abstract','pictorial','emblem']:
        svg=ET.fromstring(logo_svg(brand,style=style))
        for node in svg.iter():
            if 'data-box' in node.attrib:
                x,y,w,h=map(float,node.attrib['data-box'].split(','));assert x>=0 and y>=0 and x+w<=1024.01 and y+h<=1024.01
        bodies.append([n.attrib for n in svg.iter() if n.tag.endswith(('path','circle'))])
    assert len({json.dumps(b,sort_keys=True) for b in bodies})==6


def test_unicode_exports_and_legacy_chroma_auto_enable_are_disabled():
    from modules.document_exporter import campaign_pdf
    from modules.memory_manager import MemoryManager
    for lang,text in [('ur','ایپکس کافی کے بارے میں جانیں'),('hi','अपेक्स कॉफ़ी के बारे में जानें')]:
        result=campaign_pdf({'lang':lang,'campaign_name':'Unicode','strategy':{'product_name':text,'strategy_text':text},'copy':{'copy_text':text},'analysis':{'seo_analysis':text}})
        assert result.startswith(b'%PDF') and len(result)>10000
    assert MemoryManager().vector_db is None


def test_owner_manifest_excludes_development_and_cloud_code():
    from make_release_zip import included_in_tier,TOP_DIR
    for name in ['cloud/api/me.js','supabase/migrations/0001_init.sql','hosted/api/main.py','app/web-modern/src/App.svelte','.github/workflows/ci.yml','scripts/test_postgres_concurrency.py','app/tests/test_api.py']:
        assert not included_in_tier(TOP_DIR+'/'+name,'owner'),name
        assert included_in_tier(TOP_DIR+'/'+name,'source')
    for name in ['app/server.py','app/requirements.txt','app/web/dist/index.html','app/brandforge_assets/fonts/NotoSans-Regular.ttf','SETUP-WINDOWS.bat','START-HERE.bat']:
        assert included_in_tier(TOP_DIR+'/'+name,'owner'),name


def test_normal_windows_launch_has_no_dependency_network_work():
    root=Path(__file__).resolve().parents[2]
    launcher=(root/'START-HERE.bat').read_text().lower()
    assert 'pip install' not in launcher and 'pip --' not in launcher
    assert 'setup_env.py --check' in launcher
    assert '--install' not in launcher
    setup=(root/'app/setup_env.py').read_text()
    assert 'requirements_sha256' in setup and 'hashlib.sha256' in setup
    version=(root/'app/version_info.py').read_text()
    assert re.search(r'pyproject',version)


def test_desktop_copy_uses_scoped_request_labels_and_actual_size_cap():
    root = Path(__file__).resolve().parents[2]
    app = (root / 'app/web-modern/src/App.svelte').read_text()
    form = (root / 'app/web-modern/src/lib/SwarmStudio.svelte').read_text()
    assert '0 tracked requests' in app and 'not a complete network monitor' in app
    assert '0 outbound requests' not in app and '$7,200' not in app
    assert 'in seconds' not in app.lower() and 'in seconds' not in form.lower()
    assert 'Choose a starter brief' in form
    assert 'Selected sizes ({customSizes.length}/21)' in form


def test_embedded_music_policy_is_limited_to_marketing(client):
    tour = client.get('/sales/assets/product-demo/tour.html')
    assert tour.status_code == 200
    assert "media-src 'self' data:" in tour.headers['content-security-policy']
    assert "frame-ancestors 'none'" in tour.headers['content-security-policy']
    api = client.get('/api/session')
    assert "media-src 'self' data:" not in api.headers['content-security-policy']
