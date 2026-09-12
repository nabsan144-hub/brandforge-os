"""Local client/brand profiles with safe, atomic persistence."""

from __future__ import annotations

import json
import hashlib
import unicodedata
import os
from modules.runtime_paths import data_dir as default_data_dir
from modules.state_locks import state_lock
from typing import Dict, List, Optional

from modules.security import (
    atomic_write_bytes,
    atomic_write_json,
    safe_client_id as _safe_id,
    safe_hex,
    safe_text,
)


class ClientManager:
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = default_data_dir()
        self.base_dir = base_dir
        self.clients_dir = os.path.join(base_dir, "agency_clients")
        os.makedirs(self.clients_dir, exist_ok=True)
        self.active_file = os.path.join(base_dir, "active_client.json")
        self._lock = state_lock(base_dir)
        has_profile = any(name.endswith(".json") for name in os.listdir(self.clients_dir))
        if not has_profile:
            self._create_default_clients()

    def _create_default_clients(self):
        defaults = [
            {
                "client_id": "default_studio",
                "client_name": "Default Studio",
                "agency_brand": "BRANDFORGE OS",
                "industry": "Marketing & SaaS",
                "tone_of_voice": "Executive, Bold, High-Converting",
                "brand_promise": "",
                "proof_points": "",
                "prohibited_claims": "",
                "primary_color": "#E8B54A",
                "secondary_color": "#0F172A",
            },
            {
                "client_id": "agency_client",
                "client_name": "Agency Client",
                "agency_brand": "CLIENT BRAND",
                "industry": "E-commerce & DTC",
                "tone_of_voice": "Friendly, Direct, Conversion-Focused",
                "brand_promise": "",
                "proof_points": "",
                "prohibited_claims": "",
                "primary_color": "#3B82F6",
                "secondary_color": "#0F172A",
            },
        ]
        for profile in defaults:
            self.save_client(profile)
        self.set_active_client("default_studio")

    def _profile_path(self, client_id: str) -> str:
        safe = _safe_id(client_id)
        path = os.path.join(self.clients_dir, f"{safe}.json")
        try:
            if os.path.commonpath([os.path.realpath(self.clients_dir), os.path.realpath(path)]) != os.path.realpath(self.clients_dir):
                raise ValueError("Path traversal blocked")
        except ValueError as exc:
            raise ValueError("Path traversal blocked") from exc
        return path

    def _read_json(self, path: str) -> Dict:
        try:
            if os.path.commonpath([os.path.realpath(self.clients_dir), os.path.realpath(path)]) != os.path.realpath(self.clients_dir):
                return {}
            with open(path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _write_json(self, path: str, data: Dict):
        if os.path.commonpath([os.path.realpath(self.clients_dir), os.path.realpath(path)]) != os.path.realpath(self.clients_dir):
            raise ValueError("Path traversal blocked")
        atomic_write_json(path, data, mode=0o600)

    def identifier_for_name(self, name: str) -> str:
        normalized = unicodedata.normalize('NFKC', str(name)).strip().casefold()
        stem = _safe_id(normalized)
        existing = self.get_client(stem)
        if not normalized.isascii() or (existing and existing.get('client_name', '').strip().casefold() != normalized):
            stem = ('brand' if stem == 'default' else stem[:24]) + '_' + hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:12]
        return stem

    def save_named_client(self, data: Dict):
        # Resolve collisions and write under one lock. Omitted fields must not
        # erase an existing logo, proof points or other saved brand context.
        with self._lock:
            cid = self.identifier_for_name(data['client_name'])
            existing = self.get_client(cid)
            profile = dict(existing or {})
            profile.update(data)
            profile['client_id'] = cid
            return self.save_client(profile), bool(existing)

    def save_client(self, data: Dict) -> str:
        if not isinstance(data, dict):
            raise ValueError("Invalid client data")
        with self._lock:
            profile = dict(data)
            cid = _safe_id(profile["client_id"]) if profile.get("client_id") else self.identifier_for_name(profile.get("client_name", "Client"))
            profile["client_id"] = cid
            profile["client_name"] = safe_text(profile.get("client_name") or "Client", 80) or "Client"
            required_fields = {"industry", "tone_of_voice", "agency_brand"}
            for key, default, limit in (
                ("industry", "General", 80),
                ("tone_of_voice", "Direct, confident", 80),
                ("target_audience", "", 120),
                ("brand_promise", "", 240),
                ("proof_points", "", 500),
                ("prohibited_claims", "", 300),
                ("agency_footer", "", 180),
                ("agency_brand", "BRANDFORGE OS", 80),
            ):
                cleaned = safe_text(profile.get(key, default), limit)
                profile[key] = (cleaned or default) if key in required_fields else cleaned
            profile["show_brandforge_branding"] = bool(profile.get("show_brandforge_branding", True))
            profile["primary_color"] = safe_hex(profile.get("primary_color", "#E8B54A"), "#E8B54A")
            profile["secondary_color"] = safe_hex(profile.get("secondary_color", "#0F172A"), "#0F172A")
            self._write_json(self._profile_path(cid), profile)
            return cid

    def save_logo(self, client_id: str, source_path: str) -> str:
        """Validate and atomically store a PNG/JPEG logo for a client."""
        from PIL import Image, UnidentifiedImageError

        cid = _safe_id(client_id)
        with self._lock:
            if not self.get_client(cid):
                raise ValueError("Client not found")
            try:
                if os.path.getsize(source_path) > 5_000_000:
                    raise ValueError("Logo must not exceed 5 MB")
                with Image.open(source_path) as image:
                    image.verify()
                with Image.open(source_path) as image:
                    if image.format not in ("PNG", "JPEG"):
                        raise ValueError("Logo must be PNG or JPEG")
                    if image.width > 4000 or image.height > 4000:
                        raise ValueError("Logo dimensions are too large")
                    fmt = image.format
            except UnidentifiedImageError as exc:
                raise ValueError("Invalid image file") from exc
            except OSError as exc:
                raise ValueError("Invalid image file") from exc

            with open(source_path, "rb") as handle:
                data = handle.read(5_000_001)
            ext = ".png" if fmt == "PNG" else ".jpg"
            logos = os.path.join(self.clients_dir, "logos")
            os.makedirs(logos, exist_ok=True)
            target = os.path.join(logos, cid + ext)
            atomic_write_bytes(target, data)
            profile = self.get_client(cid) or {}
            profile["logo_path"] = target
            self.save_client(profile)
            return target

    def list_clients(self) -> List[Dict]:
        with self._lock:
            clients = []
            try:
                names = sorted(name for name in os.listdir(self.clients_dir) if name.endswith(".json"))
            except OSError:
                return []
            for name in names:
                value = self._read_json(os.path.join(self.clients_dir, name))
                if value:
                    clients.append(value)
            return clients

    def get_active_client(self) -> Dict:
        with self._lock:
            try:
                if os.path.exists(self.active_file):
                    with open(self.active_file, "r", encoding="utf-8") as handle:
                        content = json.load(handle)
                    active_id = _safe_id(content.get("active_client_id", "")) if isinstance(content, dict) else "default"
                    data = self._read_json(self._profile_path(active_id))
                    if data:
                        return data
            except (OSError, ValueError, TypeError):
                pass
            clients = self.list_clients()
            if clients:
                return clients[0]
            return {
                "client_id": "default",
                "client_name": "Default Studio",
                "agency_brand": "BRANDFORGE OS",
                "industry": "General",
                "tone_of_voice": "Executive",
                "primary_color": "#E8B54A",
                "secondary_color": "#0F172A",
            }

    def set_active_client(self, client_id: str):
        with self._lock:
            safe_id = _safe_id(client_id)
            if not self._read_json(self._profile_path(safe_id)):
                clients = self.list_clients()
                if clients:
                    safe_id = clients[0].get("client_id", "default_studio")
            atomic_write_json(self.active_file, {"active_client_id": safe_id}, mode=0o600)

    def get_client(self, client_id: str) -> Optional[Dict]:
        with self._lock:
            try:
                return self._read_json(self._profile_path(_safe_id(client_id))) or None
            except ValueError:
                return None
