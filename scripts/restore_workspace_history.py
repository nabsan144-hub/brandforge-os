"""Restore indexed historical material to a NEW directory; never execute it.
Reconstructed ZIP/bundle container hashes can differ; member/Git object hashes
must match. This does not deploy a historical tree or overwrite current work.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile
import zlib


def restore(archive,destination,only=None):
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Use a new destination directory')
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        index=json.loads(z.read('INDEX.json'))
        def raw(sha):
            if sha in index.get('object_aliases',{}):
                alias=index['object_aliases'][sha]
                with zipfile.ZipFile(io.BytesIO(z.read('objects/'+alias['container']))) as container:data=container.read(alias['member'])
            else:data=z.read('objects/'+sha)
            if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Archive hash mismatch')
            return data
        def material(node):
            if node['kind']=='file':return raw(node['sha256'])
            if node['kind']=='zip-members':
                out=io.BytesIO()
                with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as pack:
                    for entry in node['entries']:
                        name=entry['name'];rel=Path(name)
                        if rel.is_absolute() or '..' in rel.parts or '\\' in name:raise ValueError('Unsafe historical path')
                        if entry.get('directory'):pack.writestr(name,b'');continue
                        pack.writestr(name,material(entry['content']))
                return out.getvalue()
            if node['kind']=='git-history':
                with tempfile.TemporaryDirectory() as tmp:
                    repo=Path(tmp)/'history.git';subprocess.run(['git','init','--bare',str(repo)],check=True,capture_output=True)
                    for obj in node['objects']:
                        data=raw(obj['sha256']);body=f"{obj['type']} {len(data)}\0".encode()+data
                        if hashlib.sha1(body).hexdigest()!=obj['oid']:raise ValueError('Git object mismatch')
                        p=repo/'objects'/obj['oid'][:2]/obj['oid'][2:];p.parent.mkdir(exist_ok=True);p.write_bytes(zlib.compress(body))
                    for ref in node['refs']:
                        oid,name=ref.split(' ',1);subprocess.run(['git','check-ref-format',name],check=True,capture_output=True);subprocess.run(['git','-C',str(repo),'update-ref',name,oid],check=True)
                    subprocess.run(['git','-C',str(repo),'symbolic-ref','HEAD',node['head']],check=True)
                    subprocess.run(['git','-C',str(repo),'fsck','--full'],check=True,capture_output=True)
                    bundle=Path(tmp)/'history.bundle';subprocess.run(['git','-C',str(repo),'bundle','create',str(bundle),'--all'],check=True,capture_output=True);return bundle.read_bytes()
            raise ValueError('Unknown history record')
        if only and set(only)-set(index['files']):raise ValueError('Unknown historical selection')
        for name,node in index['files'].items():
            if only and name not in only:continue
            relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts or '\\' in name:raise ValueError('Unsafe historical path')
            target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(material(node))
    print('Historical contents restored; do not deploy them. Current source and uploads were untouched.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('destination');p.add_argument('--only',action='append');a=p.parse_args();restore(a.archive,a.destination,a.only)
