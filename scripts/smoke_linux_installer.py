"""Exercise a real local Linux candidate with isolated HOME; never user data."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import json

ROOT=Path(__file__).resolve().parents[1]


def smoke(package):
    package=Path(package).resolve()
    with tempfile.TemporaryDirectory(dir=ROOT/'.cache',prefix='installer-test-') as temporary:
        home=Path(temporary)/'Home with spaces';home.mkdir();env={**os.environ,'HOME':str(home)}
        data=home/'.local/share/BrandForgeOS';data.mkdir(parents=True);sentinel=data/'customer-data.json';sentinel.write_text('{"retained":true}')
        command=['sh',str(package/'install.sh')]
        def run(*args,ok=True,environment=None):
            result=subprocess.run([*command,*args],env=environment or env,capture_output=True,text=True)
            assert (result.returncode==0)==ok,result.stdout+result.stderr
            assert sentinel.read_text()=='{"retained":true}'
            return result
        run();dest=home/'.local/opt/brandforge-os';original=hashlib.sha256((dest/'BrandForge').read_bytes()).hexdigest()
        subprocess.run(['python',str(ROOT/'scripts/smoke_native_runtime.py'),str(dest/'BrandForge')],env=env,check=True)
        (dest/'repair-marker').write_text('old runtime');run('--repair');assert not (dest/'repair-marker').exists();assert (Path(str(dest)+'.previous')/'repair-marker').exists()
        run('--rollback');assert (dest/'repair-marker').exists();run('--discard-backup');run('--repair');run('--discard-backup')
        # A failed copy cannot delete the currently installed runtime.
        fake=home/'fakebin';fake.mkdir();cp=fake/'cp';cp.write_text('#!/bin/sh\nexit 1\n');cp.chmod(0o755)
        run('--repair',ok=False,environment={**env,'PATH':str(fake)+os.pathsep+env['PATH']});assert hashlib.sha256((dest/'BrandForge').read_bytes()).hexdigest()==original
        # Failed pre-install integrity check leaves both runtime and data alone.
        sums=package/'SHA256SUMS';saved=sums.read_bytes()
        try:sums.write_text('0'*64+'  runtime/BrandForge\n');run('--repair',ok=False)
        finally:sums.write_bytes(saved)
        run('--uninstall');assert not dest.exists();assert not Path(str(dest)+'.previous').exists();assert not (home/'.local/share/applications/brandforge-os.desktop').exists()
        return {'real_linux_install':'pass','installed_runtime_smoke':'pass','repair':'pass','rollback':'pass','copy_failure_preserves_runtime':'pass','tamper_rejected':'pass','uninstall':'pass','customer_data_preserved':'pass','home_with_spaces':'pass','windows_macos_execution':'not performed'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('package');args=parser.parse_args();print(json.dumps(smoke(args.package)))
