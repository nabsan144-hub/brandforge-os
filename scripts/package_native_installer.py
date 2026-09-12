"""Build platform-native unsigned installers from a verified native runtime.
Signing/notarization and target-device acceptance remain separately authorized gates.
"""
import argparse
import hashlib
import json
import os
import plistlib
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def verify_runtime(folder):
    folder=Path(folder).resolve();manifest=json.loads((folder/'runtime-manifest.json').read_text())
    if manifest.get('platform')!=platform.system(): raise ValueError('Build the installer on the same OS as its runtime.')
    for item in manifest['files']:
        rel=Path(item['name'])
        if rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe manifest path')
        p=folder/rel
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']: raise ValueError('Runtime verification failed: '+str(rel))
    actual={p.relative_to(folder).as_posix() for p in (folder/'BrandForge').rglob('*') if p.is_file()}
    if actual!={i['name'] for i in manifest['files']}: raise ValueError('Runtime includes unmanifested files')
    return folder


def version():
    return re.search(r'^version = "([0-9.]+)"',(ROOT/'app/pyproject.toml').read_text(),re.M).group(1)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('runtime');parser.add_argument('--output',default='installers');args=parser.parse_args()
    folder=verify_runtime(args.runtime);output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    if not (folder/'BrandForge/THIRD-PARTY-NOTICES/DEPENDENCIES.json').is_file(): raise SystemExit('Collect and include dependency notices before packaging.')
    if sys.platform=='win32':
        compiler=shutil.which('ISCC.exe') or shutil.which('ISCC')
        if not compiler: raise SystemExit('Install Inno Setup 6 and add ISCC to PATH.')
        subprocess.run([compiler,'/DSourceDir='+str(folder/'BrandForge'),'/DVersion='+version(),'/O'+str(output),str(ROOT/'packaging/windows/BrandForge.iss')],check=True)
    elif sys.platform=='darwin':
        stage=output/'mac-stage'
        if stage.exists():shutil.rmtree(stage)
        app=stage/'BrandForge OS.app';mac=app/'Contents/MacOS';mac.mkdir(parents=True,exist_ok=True)
        shutil.copytree(folder/'BrandForge',mac/'runtime',dirs_exist_ok=True)
        launcher=mac/'BrandForge';launcher.write_text('#!/bin/sh\ncd "$(dirname "$0")/runtime" || exit 1\nexec ./BrandForge "$@"\n');launcher.chmod(0o755)
        info={'CFBundleIdentifier':'com.brandforgeos.desktop','CFBundleName':'BrandForge OS','CFBundleExecutable':'BrandForge','CFBundleVersion':version(),'CFBundleShortVersionString':version(),'LSMinimumSystemVersion':'12.0','NSHighResolutionCapable':True}
        with (app/'Contents/Info.plist').open('wb') as f: plistlib.dump(info,f)
        # Ad-hoc signing only validates local bundle structure; it is NOT developer identity/notarization.
        subprocess.run(['codesign','--force','--deep','--sign','-',str(app)],check=True)
        subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(output/f'BrandForge-{version()}-macos-unsigned.zip')],check=True)
        subprocess.run(['hdiutil','create','-volname','BrandForge OS','-srcfolder',str(stage),'-ov','-format','UDZO',str(output/f'BrandForge-{version()}-macos-unsigned.dmg')],check=True)
    elif sys.platform.startswith('linux'):
        target=output/f'BrandForge-{version()}-linux'
        if target.exists():shutil.rmtree(target)
        shutil.copytree(folder/'BrandForge',target/'runtime',dirs_exist_ok=True)
        shutil.copyfile(ROOT/'packaging/linux-install.sh',target/'install.sh');(target/'install.sh').chmod(0o755)
        manifest=json.loads((folder/'runtime-manifest.json').read_text())
        (target/'SHA256SUMS').write_text(''.join(i['sha256']+'  runtime/'+i['name'].removeprefix('BrandForge/')+'\n' for i in manifest['files']))
        shutil.make_archive(str(output/f'BrandForge-{version()}-linux-unsigned'),'xztar',root_dir=output,base_dir=target.name)
    else: raise SystemExit('Unsupported build OS; build on the target platform.')
    (output/'INSTALLER-STATUS.json').write_text(json.dumps({'version':version(),'signed_by_verified_publisher':False,'notarized':False,'production_approved':False,'notice':'Unsigned/ad-hoc candidate; target-device, license/source-offer and signing acceptance required.'},indent=2)+'\n')
if __name__=='__main__':main()
