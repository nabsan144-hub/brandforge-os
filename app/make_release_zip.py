#!/usr/bin/env python3
"""Build the BrandForge OS customer release zip — and prove it's clean.

Why this script exists
----------------------
An early zip was built with an ad-hoc `zip -r` of the working tree and
shipped a security-test client profile and build caches inside the customer
artifact. Worse, every tier got a byte-identical zip — the top tier's
differentiators (resell license, dashboard source, CI) were in every buyer's
download, contradicting the EULA. This packager fixes both.

Current pricing (keep in sync with sales/pricing.html):
    Owner            $199 one-time   ->  --tier owner
    Agency+Source    $499 one-time   ->  --tier source

Legacy tier names still work as aliases (solo/agency -> owner, os -> source)
so older notes and scripts don't break, but always build with the new names.

How this stays clean and tiered
-------------------------------
1. The archive is the **committed git tree** (`git archive HEAD`), never the
   working directory — runtime state (campaigns, memory, config, client
   profiles, .env) and tool caches cannot leak in.
2. `--tier` selects the contents:
     owner  — the app (runs as-is via START-HERE.bat), no resell license,
              no dashboard source, no hosted SaaS code
     source — everything the $499 tier sells: resell license, Svelte
              dashboard source, CI, hosted variant
   Tiers are license/support/white-label rights, not code gates — a local
   install cannot enforce code gating honestly — so the Owner tier ships
   the full app, and Source additionally ships what its license grants.
3. The output filename carries the tier (brandforge-os-owner.zip,
   brandforge-os-source.zip) so the two products can never be mixed up at
   upload time: uploading the wrong file to a Paddle product would sell
   $499 resell rights at $199.
4. After building, the script walks every entry of the final zip and fails
   the build if any forbidden pattern is present or any required file for
   the tier is missing. The packager is its own auditor.

Usage
-----
    python app/make_release_zip.py --tier owner  [output-dir]
    python app/make_release_zip.py --tier source [output-dir]

Each emits brandforge-os-<tier>.zip. Upload the matching file to the
matching private Supabase Storage release path — verify the file and manifest before
publishing the release.
"""
import argparse
import stat
import os
import re
import subprocess
import sys
import zipfile
import json
import hashlib
from pathlib import Path
from version_info import __version__

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP_DIR = "brandforge-os"

TIERS = ("owner", "source")
# Legacy tier names from the pre-launch price sheet, kept as aliases so
# old notes/commands keep working. They map 1:1 onto the current tiers.
TIER_ALIASES = {"solo": "owner", "agency": "owner", "os": "source"}

FORBIDDEN = [
    r"\.env$",                       # secrets
    r"local-capability\.token$",
    r"setup-state\.json$",
    r"\.settings-transaction\.json$",
    r"license\.json$",               # license grants
    r"approvals\.json$",             # approval-link tokens (hashed, but still runtime state)
    r"__pycache__/",
    r"\.pyc$",
    r"\.ruff_cache/",
    r"\.cache/",
    r"\.pytest_cache/",
    r"\.git/",
    r"egg-info/",
    r"build/lib/",
    r"bdist\.",
    r"(?:^|/)(?:node_modules|\.venv|venv)(?:/|$)",
    r"output/",                      # campaign runtime state
    r"memory/",                      # chat/long-term memory
    r"config\.json$",                # dev-machine provider config
    r"active_client\.json$",
    r"\.db(-wal|-shm)?$",            # any SQLite runtime db (+ WAL/SHM sidecars)
    r"agency_clients/(?!default_studio\.json$).*\.json$",  # dev client profiles
]
FORBIDDEN_RES = [re.compile(p) for p in FORBIDDEN]

REQUIRED_COMMON = [
    "app/server.py", "app/brandforge.py", "app/requirements.txt",
    "app/brandforge_assets/dashboard/index.html", "app/brandforge_assets/fonts/NotoSans-Regular.ttf",
    "START-HERE.bat", "SETUP-WINDOWS.bat", "START-HERE.md", "README.md", "LICENSE",
    "app/setup_env.py", "docs/DESKTOP-USER-GUIDE.md", "docs/NETWORK-PRIVACY.md",
]
REQUIRED_SOURCE = ["RESALE-LICENSE.md", "app/web-modern/package.json", ".github/workflows/ci.yml",
    "cloud/api/_lib/routes/campaigns.js", "sales/index.html", "sales/pricing.html", "sales/demo.html",
    "sales/assets/product-demo/tour.html", "sales/assets/product-demo/demo.mp4",
    "sales/assets/product-demo/poster.jpg", "sales/assets/product-demo/captions.vtt",
    "sales/assets/product-demo/manifest.json", "sales/build.mjs", "docs/PRODUCT-DEMO.md"]
# Owner tier must NOT ship these.
EXCLUDE_OWNER = [
    r"RESALE-LICENSE\.md$",
    r"app/web-modern/",
    r"\.github/",
    r"app/make_release_zip\.py$",
    r"cloud/",
    r"supabase/",
    r"hosted/",  # cloud multi-tenant SaaS — not part of desktop one-time license
]
EXCLUDE_OWNER_RES = [re.compile(p) for p in EXCLUDE_OWNER]


def included_in_tier(name, tier):
    relative = name.removeprefix(TOP_DIR + "/")
    if tier == "source": return True
    if any(rx.search(name) for rx in EXCLUDE_OWNER_RES): return False
    roots = {"START-HERE.bat", "SETUP-WINDOWS.bat", "START-HERE.md", "README.md", "LICENSE", "CHANGELOG.md", "SECURITY.md"}
    if relative in roots: return True
    if relative.startswith("app/"):
        return not relative.startswith(("app/tests/", "app/web-modern/"))
    if relative.startswith("sales/"): return False
    return relative in {"docs/DESKTOP-USER-GUIDE.md", "docs/NETWORK-PRIVACY.md"}


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, **kw)


def write_release_manifest(out_path, tier, commit):
    """Append one manifest, excluding itself; never duplicate an archived one."""
    name = TOP_DIR + '/RELEASE-MANIFEST.json'
    with zipfile.ZipFile(out_path, 'a', zipfile.ZIP_DEFLATED) as archive:
        if name in archive.namelist():
            raise ValueError('Existing release manifest must be excluded before packaging')
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError('Duplicate ZIP entries are not allowed')
        records = [{'name': i.filename, 'bytes': i.file_size,
                    'sha256': hashlib.sha256(archive.read(i.filename)).hexdigest()}
                   for i in archive.infolist() if not i.is_dir()]
        manifest = {'schema': 2, 'version': __version__, 'tier': tier, 'commit': commit,
                    'scope': 'Exact artifact bytes; excludes this manifest itself. Not production approval.',
                    'files': records}
        archive.writestr(name, json.dumps(manifest, indent=2))
    with zipfile.ZipFile(out_path) as archive:
        for item in records:
            if hashlib.sha256(archive.read(item['name'])).hexdigest() != item['sha256']:
                raise ValueError('Post-write artifact verification failed')


def main():
    ap = argparse.ArgumentParser(description="Build a BrandForge OS customer release zip")
    ap.add_argument("--tier", required=True, choices=TIERS + tuple(TIER_ALIASES))
    ap.add_argument("out_dir", nargs="?", default=os.path.dirname(REPO))
    args = ap.parse_args()

    tier = TIER_ALIASES.get(args.tier, args.tier)
    if args.tier != tier:
        print(f"note: legacy tier name '{args.tier}' -> building as '{tier}'")

    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"brandforge-os-{tier}-v{__version__}.zip")

    dirty = run(["git", "status", "--porcelain"]).stdout.strip()
    if dirty:
        print("FATAL: commit the reviewed changes before packaging; never label old HEAD with a new working-tree version")
        sys.exit(1)
    subprocess.run([sys.executable,"scripts/check_release_quality.py"],cwd=REPO,check=True)
    if run(["git","status","--porcelain"]).stdout.strip():
        print("FATAL: quality/build steps changed tracked outputs. Review and commit them, then rerun.")
        sys.exit(1)

    # 1. Archive the committed tree with the documented top-level dir.
    tmp_path = os.path.join(out_dir, ".brandforge-release.tmp.zip")
    r = run(["git", "archive", "--format=zip", f"--prefix={TOP_DIR}/",
             "-o", tmp_path, "HEAD"])
    if r.returncode != 0:
        print("FATAL: git archive failed:\n", r.stderr)
        sys.exit(1)

    # 2. Re-pack (tier exclusions) into the final artifact.
    with zipfile.ZipFile(tmp_path) as zin, \
         zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            if info.filename == TOP_DIR + "/RELEASE-MANIFEST.json" or not included_in_tier(info.filename, tier):
                continue
            payload = zin.read(info.filename)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Source releases must not contain filesystem symlinks: '+info.filename)
            if tier == 'owner' and info.filename == TOP_DIR+'/README.md':
                payload = zin.read(TOP_DIR+'/app/brandforge_assets/OWNER-README.md')
            zout.writestr(info.filename, payload)

    # 3. Self-audit the final artifact.
    problems = []
    with zipfile.ZipFile(out_path) as zf:
        final = zf.namelist()
        for name in final:
            for rx in FORBIDDEN_RES:
                if rx.search(name):
                    problems.append(f"forbidden entry: {name}")
                    break
        files = {n for n in final if not n.endswith("/")}
        required = REQUIRED_COMMON + (REQUIRED_SOURCE if tier == "source" else [])
        for req in required:
            if f"{TOP_DIR}/{req}" not in files:
                problems.append(f"missing required file: {TOP_DIR}/{req}")
        html_path=f"{TOP_DIR}/app/brandforge_assets/dashboard/index.html"
        if html_path in files:
            html=zf.read(html_path).decode("utf-8")
            for asset in re.findall(r'(?:src|href)="(?:\./|/)?(assets/[^"?]+)',html):
                if f"{TOP_DIR}/app/brandforge_assets/dashboard/{asset}" not in files:
                    problems.append("missing built dashboard asset: "+asset)
        demo_manifest = f"{TOP_DIR}/sales/assets/product-demo/manifest.json"
        if demo_manifest in files:
            media_manifest = json.loads(zf.read(demo_manifest))
            for item in media_manifest["files"]:
                name = f"{TOP_DIR}/sales/assets/product-demo/{item['name']}"
                if name not in files:
                    problems.append("missing product tour asset: " + name)
                elif hashlib.sha256(zf.read(name)).hexdigest() != item["sha256"]:
                    problems.append("product tour asset checksum mismatch: " + name)
        if tier == "owner":
            for rx in EXCLUDE_OWNER_RES:
                for name in files:
                    if rx.search(name):
                        problems.append(f"tier leak (owner): {name}")

    os.remove(tmp_path)

    if problems:
        print(f"BUILD FAILED — {len(problems)} problem(s) in brandforge-os-{tier}.zip:\n")
        for p in problems:
            print("  -", p)
        os.remove(out_path)
        sys.exit(1)

    size = os.path.getsize(out_path)
    print(f"OK  {out_path}  (tier: {tier})")
    print(f"    entries: {len(final)}  size: {size/1024:.0f} KB  top dir: {TOP_DIR}/")
    print("    self-audit: 0 forbidden entries, tier contents correct")

    write_release_manifest(out_path, tier, run(["git","rev-parse","HEAD"]).stdout.strip())
    Path(out_path+".sha256").write_text(hashlib.sha256(Path(out_path).read_bytes()).hexdigest()+"  "+os.path.basename(out_path)+"\n")


if __name__ == "__main__":
    main()
