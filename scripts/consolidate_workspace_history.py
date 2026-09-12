"""Archive unique historical file contents before removing superseded copies.
Superseded ZIP containers are indexed by original hash; their members are stored
losslessly by SHA-256, not by retaining duplicate compressed container bytes.
Never touches active source, latest release or original uploads.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile


def consolidate(source, destination, delete=False):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if source==destination or source in destination.parents:raise ValueError('Destination must be outside source')
    files=sorted(p for p in source.rglob('*') if p.is_file());seen=set();count=0;total=0
    temp=destination.with_suffix('.pending');temp.parent.mkdir(parents=True,exist_ok=True)
    def record(data,name,z,depth=0):
        nonlocal count,total
        count+=1;total+=len(data)
        if count>100000 or total>3000000000:raise ValueError('History exceeds safety budget; originals retained')
        sha=hashlib.sha256(data).hexdigest()
        if name.lower().endswith('.zip') and depth<8:
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as old:
                    if any(i.flag_bits&1 for i in old.infolist()):raise ValueError('Opaque encrypted ZIP')
                    if sum(i.file_size for i in old.infolist())>500000000:raise ValueError('Oversized ZIP')
                    entries=[]
                    for i in old.infolist():
                        if i.is_dir():entries.append({'name':i.filename,'directory':True});continue
                        entries.append({'name':i.filename,'date_time':i.date_time,'mode':i.external_attr,'content':record(old.read(i),i.filename,z,depth+1)})
                    return {'kind':'zip-members','original_container_sha256':sha,'original_bytes':len(data),'entries':entries}
            except (zipfile.BadZipFile,RuntimeError,ValueError):pass
        if sha not in seen:z.writestr('objects/'+sha,data);seen.add(sha)
        return {'kind':'file','sha256':sha,'bytes':len(data)}
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        index={'schema':1,'notice':'Unique historical file bytes preserved. Original ZIP container hashes are recorded, but superseded ZIP container byte-for-byte reproduction is not promised. Never extract untrusted paths automatically. Original uploads and current deliverable are outside this archive.','files':{}}
        for p in files:
            if p.is_symlink():raise ValueError('Unexpected history symlink; originals retained')
            index['files'][p.relative_to(source).as_posix()]=record(p.read_bytes(),p.name,z)
        z.writestr('INDEX.json',json.dumps(index,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        for sha in seen:assert hashlib.sha256(z.read('objects/'+sha)).hexdigest()==sha
        decoded=json.loads(z.read('INDEX.json'));assert len(decoded['files'])==len(files)
    temp.replace(destination)
    report={'original_files':len(files),'indexed_entries':count,'unique_file_objects':len(seen),'archive_bytes':destination.stat().st_size,'archive_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'all_retained_objects_verified':True,'superseded_containers_repacked':True,'originals_removed':delete}
    destination.with_suffix('.verification.json').write_text(json.dumps(report,indent=2)+'\n')
    if delete:shutil.rmtree(source)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');p.add_argument('--delete-verified-originals',action='store_true');a=p.parse_args();print(json.dumps(consolidate(a.source,a.destination,a.delete_verified_originals),indent=2))
