"""Bounded editable source storage; never extract or execute imported artifacts."""
import base64
import copy
import hashlib
import io
import json
import math
import re
import uuid
from pathlib import Path
from PIL import Image
from modules.security import atomic_write_json
from modules.state_locks import state_lock


def validate_document(d):
    def keys(obj, allowed):
        return isinstance(obj, dict) and not set(obj)-set(allowed)
    def number(v, low, high):
        return type(v) in (int, float) and math.isfinite(v) and low <= v <= high
    def text(v, size):
        return isinstance(v, str) and not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]', v) and len(v.encode('utf-16-le'))//2 <= size
    def color(v):
        return isinstance(v, str) and re.fullmatch(r'#[a-fA-F0-9]{6}', v)
    if not keys(d, ['format','version','name','width','height','background','watermark','sections','layers']) or d.get('format') != 'brandforge-canvas' or type(d.get('version')) is not int or d['version'] != 1 or not text(d.get('name'),80) or not d['name'].strip() or any(type(d.get(k)) is not int or not 50 <= d[k] <= 5000 for k in ['width','height']) or not color(d.get('background')) or type(d.get('watermark')) is not bool or not keys(d.get('sections'), ['strategy','copy','seo']) or any(not text(d['sections'].get(k),20000) for k in ['strategy','copy','seo']) or not isinstance(d.get('layers'),list) or len(d['layers']) > 80 or len(json.dumps(d,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()) > 1000000:
        raise ValueError('Invalid canvas document or capacity exceeded')
    ids=set();images=0
    for layer in d['layers']:
        if not keys(layer,['id','type','x','y','width','height','rotation','fill','text','fontSize','font','bold','align','direction','src','fit','anchor','opacity']) or not text(layer.get('id'),60) or not re.fullmatch(r'[-a-zA-Z0-9]+',layer['id']) or layer['id'] in ids or layer.get('type') not in ['text','rect','ellipse','image'] or not number(layer.get('x'),0,d['width']) or not number(layer.get('y'),0,d['height']) or not number(layer.get('width'),1,d['width']) or not number(layer.get('height'),1,d['height']) or layer['x']+layer['width'] > d['width']+.001 or layer['y']+layer['height'] > d['height']+.001 or not number(layer.get('rotation'),-180,180) or not number(layer.get('opacity'),0,1) or not color(layer.get('fill')):
            raise ValueError('Invalid layer geometry or fields')
        ids.add(layer['id'])
        if layer['type']=='text' and (not text(layer.get('text'),2000) or not number(layer.get('fontSize'),8,300) or layer.get('font') not in ['sans-serif','serif','monospace'] or type(layer.get('bold')) is not bool or layer.get('align') not in ['left','center','right'] or layer.get('direction') not in ['ltr','rtl']):
            raise ValueError('Invalid text layer')
        if layer['type']=='image':
            images+=1
            if not text(layer.get('src'),450000) or not re.fullmatch(r'data:image/(png|jpeg);base64,(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?',layer['src']) or layer.get('fit') not in ['contain','crop'] or layer.get('anchor') not in ['xMinYMin','xMidYMin','xMaxYMin','xMinYMid','xMidYMid','xMaxYMid','xMinYMax','xMidYMax','xMaxYMax'] or images>8:
                raise ValueError('Invalid image layer')
            try:
                data=base64.b64decode(layer['src'].split(',')[1],validate=True)
                with Image.open(io.BytesIO(data)) as im:
                    if im.format not in ('PNG','JPEG') or im.width*im.height>4000000 or getattr(im,'n_frames',1)!=1:
                        raise ValueError('Image limit exceeded')
                    im.verify()
                with Image.open(io.BytesIO(data)) as im:
                    im.load()
            except Exception as exc:
                raise ValueError('Invalid or oversized image') from exc
    return d


class CanvasStore:
    def __init__(self,base):
        self.folder=Path(base)/'canvas_projects';self.folder.mkdir(parents=True,exist_ok=True);self.lock=state_lock(base)

    def path(self,key):
        try: value=str(uuid.UUID(key))
        except (ValueError,TypeError,AttributeError) as exc: raise ValueError('Invalid project ID') from exc
        p=self.folder/(value+'.json')
        if p.is_symlink(): raise ValueError('Symbolic links are not projects')
        return p

    def read(self,key,version=None):
        with self.lock:
            row=json.loads(self.path(key).read_text())
            revision=version or row['revision']
            document=row['history'].get(str(revision))
            if document is None: raise ValueError('Version is no longer retained; no new write occurred')
            return {'id':key,'revision':revision,'document':validate_document(document),'versions':sorted(map(int,row['history']),reverse=True)}

    def list(self):
        with self.lock:
            result=[]
            for p in self.folder.glob('*.json'):
                row=self.read(p.stem)
                result.append({'id':p.stem,'name':row['document']['name'],'revision':row['revision']})
            return result

    def save(self,body):
        if not isinstance(body,dict) or set(body)-{'id','revision','request_id','document','restore','consent'} or body.get('consent') is not True or type(body.get('revision')) is not int or body['revision']<0 or ('restore' in body and (type(body['restore']) is not int or body['restore']<1 or 'document' in body)):
            raise ValueError('Invalid canvas save request')
        request_id=str(uuid.UUID(body.get('request_id','')));key=body.get('id') or request_id;path=self.path(key)
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        if 'restore' not in body: validate_document(body.get('document'))
        with self.lock:
            row=json.loads(path.read_text()) if path.exists() else {'revision':0,'history':{},'requests':{}}
            if body.get('id') and not path.exists(): raise FileNotFoundError('Canvas not found')
            prior=row['requests'].get(request_id)
            if prior:
                if prior['hash']!=digest: raise ValueError('Request ID belongs to different content')
                return {**self.read(key,prior['revision']),'replayed':True}
            if row['revision']!=body['revision']: raise ValueError('A newer revision exists. Reload before saving')
            if not path.exists() and len(list(self.folder.glob('*.json')))>=10: raise ValueError('Ten-project limit reached')
            document=copy.deepcopy(body.get('document')) if 'restore' not in body else row['history'].get(str(body['restore']))
            validate_document(document);revision=row['revision']+1
            row['revision']=revision;row['history'][str(revision)]=document;row['requests'][request_id]={'hash':digest,'revision':revision}
            row['history']={k:v for k,v in row['history'].items() if int(k)>=revision-9}
            row['requests']={k:v for k,v in row['requests'].items() if v['revision']>=revision-19}
            atomic_write_json(str(path),row)
            return self.read(key)

    def delete(self,key):
        with self.lock: self.path(key).unlink(missing_ok=True)
