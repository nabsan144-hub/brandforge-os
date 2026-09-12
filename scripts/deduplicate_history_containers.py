"""Deduplicate loose archived contents already present in preserved Git ZIP blobs."""
import hashlib
import io
import json
from pathlib import Path
import zipfile


def optimize(path):
    path=Path(path);temp=path.with_suffix('.optimized')
    with zipfile.ZipFile(path) as source:
        index=json.loads(source.read('INDEX.json'));objects={i.filename.split('/')[-1]:i for i in source.infolist() if i.filename.startswith('objects/')}
        containers={};aliases={}
        for sha,entry in objects.items():
            if entry.file_size>500000:
                with source.open(entry) as stream:signature=stream.read(4)
                if signature!=b'PK\x03\x04':continue
                raw=source.read(entry)
                try:
                    with zipfile.ZipFile(io.BytesIO(raw)) as z:
                        if sum(i.file_size for i in z.infolist())>500000000:continue
                        containers[sha]=raw
                except zipfile.BadZipFile:pass
        for container,data in containers.items():
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for entry in z.infolist():
                    if entry.is_dir() or entry.flag_bits&1:continue
                    blob=z.read(entry);sha=hashlib.sha256(blob).hexdigest()
                    if sha in objects and sha not in containers:aliases.setdefault(sha,{'container':container,'member':entry.filename})
        index['object_aliases']=aliases
        index['notice']+=' Some logical objects are verified members of retained ZIP blobs; use restore_workspace_history.py rather than treating every hash as a loose file.'
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as dest:
            for sha,entry in objects.items():
                if sha not in aliases:dest.writestr(entry.filename,source.read(entry))
            dest.writestr('INDEX.json',json.dumps(index,indent=2))
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        for sha in objects:
            if sha in aliases:
                alias=aliases[sha]
                with zipfile.ZipFile(io.BytesIO(z.read('objects/'+alias['container']))) as c:data=c.read(alias['member'])
            else:data=z.read('objects/'+sha)
            assert hashlib.sha256(data).hexdigest()==sha
    temp.replace(path)
    report={'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'archive_bytes':path.stat().st_size,'logical_objects':len(objects),'redundant_loose_objects_removed':len(aliases),'all_logical_objects_verified':True,'original_uploads_untouched':True,'note':'Original member bytes and Git objects preserved; superseded packaging containers may be reconstructed with different compressed bytes.'}
    path.with_suffix('.verification.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('archive');a=p.parse_args();print(json.dumps(optimize(a.archive),indent=2))
