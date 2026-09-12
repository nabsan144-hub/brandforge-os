import json
import subprocess
import uuid
from pathlib import Path
import pytest
from modules.canvas_projects import CanvasStore, validate_document


def document():
    return {'format':'brandforge-canvas','version':1,'name':'Canvas','width':1200,'height':630,'background':'#ffffff','watermark':True,'sections':{'strategy':'Plan','copy':'Copy','seo':'Notes'},'layers':[{'id':'text-1','type':'text','x':10,'y':10,'width':500,'height':100,'rotation':0,'opacity':1,'fill':'#112233','text':'Coffee & tea','fontSize':24,'font':'serif','bold':False,'align':'left','direction':'ltr'}]}


def test_editable_roundtrip_shared_js_and_python(tmp_path):
    d=document();f=tmp_path/'input.json';f.write_text(json.dumps(d));root=Path(__file__).resolve().parents[2]
    r=subprocess.run(['node','--input-type=module','-e',"import {readFileSync} from 'node:fs';import {validateDocument} from './shared/canvas/model.js';console.log(JSON.stringify(validateDocument(JSON.parse(readFileSync(process.argv[1])))));",str(f)],cwd=root,capture_output=True,text=True,check=True)
    assert validate_document(json.loads(r.stdout))==d
    for name in ['model.js','editor.js','index.html','style.css','image-dimensions.js']:
        assert (root/'shared/canvas'/name).read_bytes()==(root/'cloud/public/canvas'/name).read_bytes()==(root/'app/brandforge_assets/canvas'/name).read_bytes()


def test_save_restore_replay_limits_and_safe_paths(tmp_path):
    store=CanvasStore(tmp_path);b={'id':None,'revision':0,'request_id':str(uuid.uuid4()),'document':document(),'consent':True}
    c=store.save(b);assert store.save(b)['replayed']
    with pytest.raises(ValueError):store.save({**b,'document':{**document(),'name':'Different'}})
    for i in range(12):c=store.save({'id':c['id'],'revision':c['revision'],'request_id':str(uuid.uuid4()),'document':{**document(),'name':str(i)},'consent':True})
    assert len(c['versions'])==10
    restored=store.save({'id':c['id'],'revision':c['revision'],'request_id':str(uuid.uuid4()),'restore':c['versions'][-1],'consent':True})
    assert restored['document']['name']!=c['document']['name']
    with pytest.raises(ValueError):store.read('../secrets')
    store.delete(c['id']);assert store.list()==[]


def test_http_capability_and_canvas_assets(client):
    b={'id':None,'revision':0,'request_id':str(uuid.uuid4()),'document':document(),'consent':True}
    r=client.post('/api/canvas',json=b);assert r.status_code==200,r.text
    key=r.json()['id'];assert client.get('/api/canvas',params={'id':key}).json()['document']==document()
    assert client.get('/canvas/').status_code==200
    assert client.get('/canvas/semantic-tokens.css').status_code==200
    assert client.get('/canvas/ui-font.woff2').status_code==200
    assert client.get('/canvas/no-such-file').status_code==404
    assert client.delete('/api/canvas',params={'id':key}).status_code==200


@pytest.mark.parametrize('change',[{'version':True},{'width':float('nan')},{'provider_key':'secret'},{'layers':[{'type':'image','src':'https://example.test/a.png'}]}])
def test_rejects_unsafe_or_nonportable_documents(change):
    with pytest.raises(ValueError):validate_document({**document(),**change})


def test_canvas_rejects_invalid_xml_text():
    d=document();d["layers"][0]["text"]="bad\x00text"
    with pytest.raises(ValueError):validate_document(d)
