import importlib.util
import json
import hashlib
import platform
import subprocess
import sys
from pathlib import Path
import pytest
from modules.instance_lock import instance_lock

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('installer',ROOT/'scripts/package_native_installer.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_native_manifest_rejects_tampering_unmanifested_files_and_wrong_os(tmp_path):
    folder=tmp_path/'BrandForge';folder.mkdir();p=folder/'program';p.write_bytes(b'exe')
    manifest={'platform':platform.system(),'files':[{'name':'BrandForge/program','sha256':hashlib.sha256(b'exe').hexdigest()}]}
    (tmp_path/'runtime-manifest.json').write_text(json.dumps(manifest));assert module.verify_runtime(tmp_path)==tmp_path
    (folder/'extra').write_text('not authorized')
    with pytest.raises(ValueError):module.verify_runtime(tmp_path)
    (folder/'extra').unlink();p.write_bytes(b'tampered')
    with pytest.raises(ValueError):module.verify_runtime(tmp_path)
    manifest['platform']='Other';(tmp_path/'runtime-manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):module.verify_runtime(tmp_path)


def test_native_data_lock_blocks_second_process_and_releases(tmp_path):
    code="import sys;sys.path.insert(0,sys.argv[1]);from modules.instance_lock import instance_lock\nwith instance_lock(sys.argv[2]): print('locked')"
    with instance_lock(tmp_path):
        result=subprocess.run([sys.executable,'-c',code,str(ROOT/'app'),str(tmp_path)],capture_output=True,text=True)
        assert result.returncode!=0 and 'already running' in result.stderr
    result=subprocess.run([sys.executable,'-c',code,str(ROOT/'app'),str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==0
