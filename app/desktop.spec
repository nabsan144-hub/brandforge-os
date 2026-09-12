# Native build recipe. Run from repository root with a clean build environment.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_submodules, copy_metadata
root = Path(SPECPATH).resolve()
# No .env, license grant, portable_archives, campaign data or signing keys.
datas = [(str(root/'brandforge_assets'),'brandforge_assets'),(str(root/'pyproject.toml'),'.')]
hidden = collect_submodules('modules') + collect_submodules('engines') + collect_submodules('gateway')
a = Analysis([str(root/'frozen_launcher.py')],pathex=[str(root)],binaries=[],datas=datas,hiddenimports=hidden,
             excludes=['pytest','playwright','tkinter','matplotlib','pandas','IPython','jedi','numpy','scipy','sympy'],noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='BrandForge',debug=False,bootloader_ignore_signals=False,strip=sys.platform.startswith('linux'),upx=False,console=True)
coll = COLLECT(exe,a.binaries,a.datas,strip=sys.platform.startswith('linux'),upx=False,name='BrandForge')
