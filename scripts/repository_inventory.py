#!/usr/bin/env python3
"""Hash and syntax inventory of tracked/current files; NOT a line-by-line audit.
Never executes scanned source and never prints suspected secret values.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def inventory():
    try:
        git_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
        if Path(git_root).resolve() != ROOT:
            raise ValueError('The source directory is nested inside a different Git repository')
        paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT,stderr=subprocess.DEVNULL).decode().split('\0')
    except (subprocess.CalledProcessError,FileNotFoundError,ValueError):
        excluded={'.git','.cache','node_modules','__pycache__','qa-results','build','dist','native-candidate','installers','.venv','.pytest_cache','.ruff_cache','output','memory','agency_clients'}
        paths=[p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and not excluded.intersection(p.relative_to(ROOT).parts)]
    rows = []
    for name in sorted(set(paths) - {''}):
        p = ROOT / name
        if not p.is_file():
            continue
        b = p.read_bytes()
        row = {'path': name, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(),
               'lines': None, 'syntax': 'not applicable', 'manual_review': 'not claimed'}
        try:
            text = b.decode('utf-8')
            row['lines'] = len(text.splitlines())
        except UnicodeDecodeError:
            text = None
        try:
            if p.suffix == '.py':
                ast.parse(text, filename=name); row['syntax'] = 'Python AST passed'
            elif p.suffix in ('.js', '.mjs', '.cjs'):
                result = subprocess.run(['node', '--check', str(p)], capture_output=True, text=True, timeout=20)
                row['syntax'] = 'Node syntax passed' if result.returncode == 0 else 'FAILED: ' + result.stderr[:300]
            elif p.suffix == '.json':
                json.loads(text); row['syntax'] = 'JSON parsed'
            elif p.suffix in ('.svg', '.xml'):
                ET.fromstring(b); row['syntax'] = 'XML parsed'
            elif p.suffix == '.sh':
                result = subprocess.run(['bash', '-n', str(p)], capture_output=True, text=True, timeout=10)
                row['syntax'] = 'Bash syntax passed' if result.returncode == 0 else 'FAILED: ' + result.stderr[:300]
        except Exception as error:
            row['syntax'] = 'FAILED: ' + type(error).__name__ + ' ' + str(error)[:200]
        if text:
            # Heuristic only. Fixtures are explicitly separated for triage.
            patterns = [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', r'\b(?:sk_live_|sk-proj-|sb_secret_)[A-Za-z0-9_-]{20,}']
            row['credential_pattern_lines'] = [i for i, line in enumerate(text.splitlines(), 1) if any(re.search(pat, line) for pat in patterns)]
            row['fixture_or_document'] = any(x in p.parts for x in ('tests', 'docs'))
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    rows = inventory(); args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'notice': 'Inventory and syntax only; not proof of complete manual review or test coverage.', 'files': rows}, indent=2) + '\n')
    bad = [r for r in rows if r['syntax'].startswith('FAILED')]
    print(json.dumps({'files': len(rows), 'text_lines': sum(r['lines'] or 0 for r in rows), 'syntax_failures': bad, 'credential_patterns': [{'path':r['path'],'lines':r.get('credential_pattern_lines')} for r in rows if r.get('credential_pattern_lines')]}, indent=2))
    raise SystemExit(bool(bad))


if __name__ == '__main__':
    main()
