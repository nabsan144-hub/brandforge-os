"""One-shot native-binary smoke; temporary data, loopback, no provider keys."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
import zipfile
import io
import uuid


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('executable');args=p.parse_args()
    exe=str(Path(args.executable).resolve())
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='bf-native-') as d:
        env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('API_KEY','TOKEN','SECRET','PYTHONPATH'))}
        env['BRANDFORGE_DATA_DIR']=d
        with open(Path(d)/'server.txt','w+') as log:
            proc=subprocess.Popen([exe,'--no-browser','--port',str(port)],cwd=d,env=env,stdout=log,stderr=subprocess.STDOUT)
            def get(path,body=None,cap=None):
                req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json',**({'X-BrandForge-Token':cap} if cap else {})})
                try:
                    return urllib.request.urlopen(req,timeout=60)
                except urllib.error.HTTPError as exc:
                    print('HTTP error body:',exc.read().decode()[:1000]);raise
            try:
                for _ in range(100):
                    if proc.poll() is not None:break
                    try:
                        with get('/health') as r:health=json.load(r)
                        break
                    except OSError:time.sleep(.2)
                else:raise RuntimeError('Native startup timed out')
                if proc.poll() is not None:raise RuntimeError('Native executable exited')
                with get('/') as r:assert b'<html' in r.read().lower()
                with get('/api/session') as r:cap=json.load(r)['capability']
                with get('/api/swarm/run',{'campaign_name':'Native smoke','product_name':'Coffee','industry':'Retail','target_audience':'Adults','key_benefits':'Whole beans'},cap) as r:name=json.load(r)['campaign_name']
                with get('/api/campaigns/'+name+'/download') as r:data=r.read()
                with zipfile.ZipFile(io.BytesIO(data)) as z:assert z.testzip() is None and z.namelist()
                with get('/api/campaigns/'+name+'/export.pdf') as r:assert r.read().startswith(b'%PDF')
                with get('/api/transfers?core=true&campaign='+name) as r:pack=json.load(r)['pack'];assert pack['format']=='brandforge-portable'
                for path in ['/canvas/','/canvas/semantic-tokens.css','/canvas/ui-font.woff2']:
                    with get(path) as r:assert r.status==200 and r.read()
                canvas={'format':'brandforge-canvas','version':1,'name':'Native canvas','width':1200,'height':630,'background':'#ffffff','watermark':False,'sections':{'strategy':'Plan','copy':'Copy','seo':'Notes'},'layers':[]}
                with get('/api/canvas',{'id':None,'revision':0,'request_id':str(uuid.uuid4()),'document':canvas,'consent':True},cap) as r:assert json.load(r)['document']==canvas
                print(json.dumps({'canvas_assets_and_save':'pass','native_start':'pass','health_version':health['version'],'dashboard':'pass','offline_campaign':'pass','ZIP':'pass','PDF':'pass','portable_core_export':'pass','data_isolated':True}))
            except Exception:
                log.flush();log.seek(0);print(log.read()[-6000:]);raise
            finally:
                proc.terminate()
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
if __name__=='__main__':main()
