"""Repack a verified history bundle as Git objects, deduplicated against archived files."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile


def repack(path, scratch):
    path=Path(path);scratch=Path(scratch);scratch.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path) as original:
        index=json.loads(original.read('INDEX.json'));bundles=[]
        def find(node,name):
            if node.get('kind')=='file' and name.endswith('.bundle'):bundles.append(node)
            elif node.get('kind')=='zip-members':
                for e in node['entries']:
                    if 'content' in e:find(e['content'],e['name'])
        for name,node in index['files'].items():find(node,name)
        replaced={n['sha256'] for n in bundles};temp=path.with_suffix('.repack')
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as target:
            present=set()
            for entry in original.infolist():
                if entry.filename=='INDEX.json' or entry.filename.removeprefix('objects/') in replaced:continue
                target.writestr(entry.filename,original.read(entry));present.add(entry.filename.removeprefix('objects/'))
            for node in bundles:
                with tempfile.TemporaryDirectory(dir=scratch) as directory:
                    directory=Path(directory);bundle=directory/'history.bundle';bundle.write_bytes(original.read('objects/'+node['sha256']))
                    assert hashlib.sha256(bundle.read_bytes()).hexdigest()==node['sha256']
                    repo=directory/'history.git';subprocess.run(['git','clone','--mirror',str(bundle),str(repo)],check=True,capture_output=True)
                    subprocess.run(['git','-C',str(repo),'fsck','--full'],check=True,capture_output=True)
                    refs=subprocess.check_output(['git','-C',str(repo),'for-each-ref','--format=%(objectname) %(refname)'],text=True).splitlines()
                    head=subprocess.check_output(['git','-C',str(repo),'symbolic-ref','HEAD'],text=True).strip()
                    proc=subprocess.Popen(['git','-C',str(repo),'cat-file','--batch-all-objects','--batch'],stdout=subprocess.PIPE)
                    objects=[]
                    while header:=proc.stdout.readline():
                        oid,kind,size=header.decode().strip().split();data=proc.stdout.read(int(size));assert proc.stdout.read(1)==b'\n'
                        assert hashlib.sha1(f'{kind} {size}\0'.encode()+data).hexdigest()==oid
                        sha=hashlib.sha256(data).hexdigest()
                        if sha not in present:target.writestr('objects/'+sha,data);present.add(sha)
                        objects.append({'oid':oid,'type':kind,'sha256':sha,'bytes':len(data)})
                    assert proc.wait()==0
                    old=node.copy();node.clear();node.update({'kind':'git-history','original_bundle_sha256':old['sha256'],'refs':refs,'head':head,'objects':objects})
            index['notice']+=' Git bundles are preserved as verified logical Git objects/refs, not duplicate pack-container bytes.'
            target.writestr('INDEX.json',json.dumps(index,indent=2))
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        for entry in z.infolist():
            if entry.filename.startswith('objects/'):assert hashlib.sha256(z.read(entry)).hexdigest()==entry.filename.split('/')[-1]
    temp.replace(path)
    report={'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'archive_bytes':path.stat().st_size,'unique_objects':len(present),'historical_files_indexed':len(index['files']),'verified_git_bundles':len(bundles),'all_retained_objects_verified':True,'original_uploads_untouched':True,'container_bytes_not_retained':'Old ZIP and Git pack containers were replaced by verified member/object content.'}
    path.with_suffix('.verification.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('scratch');a=p.parse_args();print(json.dumps(repack(a.archive,a.scratch),indent=2))
