"""Version-one content archive. Never extract or execute imported artifacts."""
import base64
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from modules.security import atomic_write_json
from modules.state_locks import state_lock

NOTICE = 'Archive transfer only: original files and text preserved. Native editor recipes, IDs, approvals, billing, providers and revision history are not transferred. Imported files are untrusted; they are never executed or extracted automatically.'


def validate(pack):
    if not isinstance(pack, dict) or set(pack) - {'omitted_files'} != {'format', 'version', 'origin', 'name', 'sections', 'files'}:
        raise ValueError('Unsupported portable fields')
    if pack['format'] != 'brandforge-portable' or type(pack['version']) is not int or pack['version'] != 1 or pack['origin'] not in ('cloud', 'desktop'):
        raise ValueError('Unsupported portable version')
    if not isinstance(pack['name'], str) or not pack['name'].strip() or len(pack['name']) > 80:
        raise ValueError('Invalid archive name')
    if len(json.dumps(pack, ensure_ascii=False, separators=(',', ':')).encode()) > 3_000_000:
        raise ValueError('Portable packs are limited to 3 MB; keep larger files in the original ZIP')
    if not isinstance(pack['sections'], dict) or set(pack['sections']) != {'strategy', 'copy', 'seo'} or any(not isinstance(v, str) or len(v) > 20000 for v in pack['sections'].values()):
        raise ValueError('Invalid text sections')
    if not isinstance(pack['files'], list) or len(pack['files']) > 64:
        raise ValueError('Invalid file list')
    names = set()
    for f in pack['files']:
        if not isinstance(f, dict) or set(f) != {'name', 'encoding', 'content', 'bytes', 'sha256'}:
            raise ValueError('Invalid file fields')
        if not isinstance(f['name'], str) or not re.fullmatch(r'[^\W_][\w.\-]{0,119}', f['name']) or f['name'] in names or not re.search(r'\.(svg|png|jpe?g|webp|pdf|docx|txt|md|csv|json|html)$', f['name'], re.I):
            raise ValueError('Invalid or duplicate filename')
        names.add(f['name'])
        if f['encoding'] != 'base64' or not isinstance(f['content'], str):
            raise ValueError('Invalid encoding')
        try:
            raw = base64.b64decode(f['content'], validate=True)
        except Exception as exc:
            raise ValueError('Invalid base64') from exc
        if type(f['bytes']) is not int or len(raw) != f['bytes'] or hashlib.sha256(raw).hexdigest() != f['sha256']:
            raise ValueError('Archive checksum mismatch')
    omitted = pack.get('omitted_files', [])
    if not isinstance(omitted, list) or len(omitted) > 128 or any(not isinstance(f, dict) or set(f) != {'name', 'reason'} or not isinstance(f['name'], str) or len(f['name']) > 120 or not isinstance(f['reason'], str) or len(f['reason']) > 200 for f in omitted):
        raise ValueError('Invalid omission report')
    return pack


def export_campaign(pm, name, core=False):
    c = pm.get_campaign(name)
    if not c:
        raise FileNotFoundError('Campaign not found')
    files = []
    omitted = []
    total = 0
    # campaign.json is internal authorization/workflow metadata, not a transferred artifact.
    for item in c['files']:
        if item['name'] == 'campaign.json':
            continue
        if core and item['name'] != 'hero_banner.svg':
            omitted.append({'name': item['name'], 'reason': 'Core transfer selected; retain the original ZIP for this file.'})
            continue
        path = pm.get_campaign_file(name, item['name'])
        if not path:
            raise ValueError('A source file is unavailable')
        total += Path(path).stat().st_size
        if total > 2_200_000:
            raise ValueError("This pack exceeds portable capacity; use its original ZIP")
        raw = Path(path).read_bytes()
        files.append({'name': item['name'], 'encoding': 'base64', 'content': base64.b64encode(raw).decode(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    return validate({'format': 'brandforge-portable', 'version': 1, 'origin': 'desktop', 'name': c.get('campaign_name', name)[:80], **({'omitted_files': omitted} if core else {}), 'sections': {'strategy': c.get('strategy', {}).get('strategy_text', ''), 'copy': c.get('copy', {}).get('copy_text', ''), 'seo': c.get('analysis', {}).get('seo_analysis', '')}, 'files': files})


class ArchiveStore:
    def __init__(self, base):
        self.folder = Path(base)/'portable_archives'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = state_lock(base)

    def path(self, key):
        try:
            value = str(uuid.UUID(key))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError('Invalid archive ID') from exc
        path = self.folder/(value+'.json')
        if path.is_symlink():
            raise ValueError('Symbolic links are not archive files')
        return path

    def save(self, pack, request_id):
        validate(pack)
        path = self.path(request_id)
        with self.lock:
            if path.exists():
                if json.loads(path.read_text()) != pack:
                    raise ValueError('Request ID already used for a different archive')
                return {'ok': True, 'id': path.stem, 'replayed': True}
            if len(list(self.folder.glob('*.json'))) >= 10:
                raise ValueError('Ten-archive limit reached; delete an archive first')
            atomic_write_json(str(path), pack)
        return {'ok': True, 'id': path.stem}

    def list(self):
        with self.lock:
            return [{'id': p.stem, 'name': json.loads(p.read_text())['name'], 'created_at': str(os.path.getmtime(p))} for p in sorted(self.folder.glob('*.json'))]

    def read(self, key):
        with self.lock:
            return validate(json.loads(self.path(key).read_text()))

    def delete(self, key):
        with self.lock:
            self.path(key).unlink(missing_ok=True)
