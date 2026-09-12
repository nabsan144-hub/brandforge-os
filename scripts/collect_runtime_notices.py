"""Collect installed dependency metadata and verbatim license notices, not legal approval."""
import argparse
import importlib.metadata as metadata
import json
import re
import shutil
import sys
import sysconfig
from pathlib import Path
from packaging.requirements import Requirement

ROOT=Path(__file__).resolve().parents[1]

def collect(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    queue=[]
    for line in (ROOT/'app/requirements.txt').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'): queue.append(Requirement(line).name)
    queue.append('pyinstaller');seen=set();records=[]
    while queue:
        name=queue.pop();key=re.sub(r'[-_.]+','-',name).lower()
        if key in seen: continue
        seen.add(key)
        try: dist=metadata.distribution(name)
        except metadata.PackageNotFoundError: records.append({'name':name,'missing':True});continue
        record={'name':dist.metadata['Name'],'version':dist.version,'license':dist.metadata.get('License-Expression') or dist.metadata.get('License'),'notices':[]}
        for file in dist.files or []:
            if re.match(r'(?i)^(licen[sc]e|copying|notice|copyright)([._-].*)?$',Path(str(file)).name):
                source=Path(dist.locate_file(file))
                if source.is_file() and source.stat().st_size<2000000:
                    dest=output/key/str(file).replace('..','_').lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest);record['notices'].append(dest.relative_to(output).as_posix())
        for dependency in dist.requires or []:
            req=Requirement(dependency)
            if req.marker is None or req.marker.evaluate({'extra':''}): queue.append(req.name)
        records.append(record)
    for source in [ROOT/'LICENSE',ROOT/'END-CUSTOMER-LICENSE.md',ROOT/'RESALE-LICENSE.md']:
        shutil.copyfile(source,output/source.name)
    python_license=next((p for p in [Path(sys.base_prefix)/'LICENSE.txt',Path(sysconfig.get_path('stdlib'))/'LICENSE.txt'] if p.exists()),None)
    if python_license:shutil.copyfile(python_license,output/'PYTHON-LICENSE.txt')
    for name in ['svelte','@lucide/svelte']:
        package=ROOT/'app/web-modern/node_modules'/name
        if not package.exists():raise RuntimeError('Missing frontend dependency notices: '+name)
        for file in package.iterdir():
            if file.is_file() and re.match(r'(?i)^(licen[sc]e|notice|copying)',file.name):
                dest=output/'frontend'/name/file.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
    for source in (ROOT/'app/brandforge_assets/licenses').glob('*'):
        if source.is_file():shutil.copyfile(source,output/source.name)
    shutil.copyfile(ROOT/'app/brandforge_assets/fonts/OFL.txt',output/'Noto-OFL.txt')
    for name in ['libssl3t64','libgcc-s1','libstdc++6','libzstd1','zlib1g','libexpat1','libffi8','liblzma5','libbz2-1.0']:
        source=Path('/usr/share/doc')/name/'copyright'
        if source.is_file():
            dest=output/'system'/name/'copyright';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    report={'schema':1,'python':sys.version.split()[0],'legal_approved':False,'notice':'Verbatim installed-package notices, not a complete legal/source-offer certification. Review missing notices, Python/native libraries, generated frontend/font licenses and any copyleft source/relinking obligations before distribution.','dependencies':sorted(records,key=lambda r:r['name'].lower())}
    (output/'DEPENDENCIES.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');args=p.parse_args();collect(args.output)
