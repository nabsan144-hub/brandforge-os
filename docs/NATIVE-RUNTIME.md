# Unsigned native runtime candidate

Not a signed installer or approved customer distribution. Build on the target OS using Python 3.13 and Node 20. Build dependencies require network access; launch does not invoke pip/npm.

```text
python -m pip install -r app/requirements.txt pyinstaller==6.22.2
npm ci --prefix app/web-modern
npm run build --prefix app/web-modern
python scripts/build_desktop_runtime.py native-candidate
```

Run `python scripts/smoke_native_runtime.py native-candidate/BrandForge/BrandForge.exe` on Windows; omit `.exe` on macOS/Linux. The smoke uses an isolated temporary data directory, disables provider credentials, starts loopback only, generates offline output, checks ZIP/PDF, and checks explicit partial-core portable export. The manifest enumerates actual binary bytes and declares signed/production approval false.

The manual GitHub workflow builds and smokes on Windows/macOS runners. A workflow definition is not evidence it ran. Linux 1.13.0 was rebuilt and tested locally, including Canvas save and real installer repair/rollback/tamper/failure/uninstall with customer-data preservation. Do not cross-label its binaries as Windows/macOS builds.

Before any redistribution: use an isolated environment; inspect the build file allowlist and third-party dependencies; collect required copyright/license/notice files and source offers applicable to the exact bundled wheels, Python, native libraries, fonts and bootloader; have licensing reviewed; obtain platform signing/notarization; package/install/uninstall/update and rollback; test clean supported Windows/macOS devices without Python/Node installed, standard-user and Unicode paths, restrictive security software, offline launch and data persistence. Never include local settings, provider keys, customer work or signing credentials. Keep native-candidate output outside Git/source ZIPs. Do not call an unsigned runtime a finished nontechnical customer installer.
