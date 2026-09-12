"""Build an unsigned native runtime for the CURRENT OS, not a cross-compiler.
Use an isolated environment with app requirements and PyInstaller 6.22.2.
Signing and clean-machine approval are separate release gates.
"""
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');args=p.parse_args()
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    npm=shutil.which('npm')
    if not npm:raise SystemExit('Install Node and run npm ci --prefix app/web-modern before building a native runtime.')
    subprocess.run([npm,'run','build','--prefix',str(ROOT/'app/web-modern')],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'scripts/sync_canvas.py','--check'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'-m','PyInstaller','--clean','--noconfirm','--distpath',str(output),'--workpath',str(ROOT/'.cache/native-build'),'app/desktop.spec'],cwd=ROOT,check=True)
    from collect_runtime_notices import collect
    collect(output/'BrandForge/THIRD-PARTY-NOTICES')
    files=[]
    for path in sorted((output/'BrandForge').rglob('*')):
        if not path.is_file():continue
        rel=path.relative_to(output).as_posix()
        if path.name in ('.env','license.json','local-capability.token') or 'portable_archives' in path.parts:raise SystemExit('Private state in build: '+rel)
        files.append({'name':rel,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (output/'runtime-manifest.json').write_text(json.dumps({'schema':1,'platform':platform.system(),'architecture':platform.machine(),'signed':False,'production_approved':False,'notice':'Unsigned native build candidate; test on clean supported devices. Not a signed installer or native customer certification.','files':files},indent=2)+'\n')

if __name__=='__main__':main()
