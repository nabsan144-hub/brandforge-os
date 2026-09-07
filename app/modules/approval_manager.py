"""Local, token-protected campaign approval workflow."""

from __future__ import annotations

import hashlib
import re
import os
import secrets
from modules.state_locks import state_lock
from modules.state_io import read_object, LocalStateError
from datetime import datetime

from modules.security import atomic_write_json, safe_slug, safe_text

MAX_COMMENTS_PER_TOKEN = 30
MAX_AUDIT_PER_TOKEN = 100
MAX_TOKENS = 5000


class ApprovalManager:
    def __init__(self, base_dir):
        self.path = os.path.join(base_dir, "approvals.json")
        self._lock = state_lock(base_dir)

    def _load(self):
        value = read_object(self.path)
        if any(not isinstance(row, dict) for row in value.values()):
            raise LocalStateError('Approval records are unreadable. Existing data was preserved.')
        return value

    def _save(self, data):
        atomic_write_json(self.path, data, mode=0o600)

    def _mutate(self, fn):
        """Serialize each load → mutate → save cycle."""
        with self._lock:
            data = self._load()
            out = fn(data)
            if out is not None:
                self._save(data)
            return out

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

    def create(self, campaign, store_token=False):
        """store_token=True keeps the raw token in the record so the agency
        inbox can list open links. Desktop-local ONLY: approvals.json there is
        0600 operator-private, and a reader of it already owns every campaign.
        Hosted/multi-tenant must keep the hash-only design (a leaked store
        file must not leak review URLs)."""
        def _do(data):
            if len(data) >= MAX_TOKENS:
                oldest = min(data, key=lambda key: str(data.get(key, {}).get("created", "")))
                data.pop(oldest, None)
            token = secrets.token_urlsafe(32)
            now = datetime.now().isoformat()
            record = {
                "campaign": safe_slug(campaign, 60),
                "created": now,
                "revoked": False,
                "decision": "pending",
                "comments": [],
                "audit": [{"event": "created", "at": now}],
            }
            if store_token:
                record["token"] = token
            data[self._key(token)] = record
            return token

        return self._mutate(_do)

    def get(self, token):
        with self._lock:
            return self._load().get(self._key(token))

    def update(self, token, decision=None, comment="", asset=""):
        key = self._key(token)

        def _do(data):
            item = data.get(key)
            if not isinstance(item, dict) or item.get("revoked"):
                return None
            now = datetime.now().isoformat()
            audit = item.get("audit") if isinstance(item.get("audit"), list) else []
            comments = item.get("comments") if isinstance(item.get("comments"), list) else []
            clean_comment = safe_text(comment, 1000)
            # Anchors must match real filenames (dots included) — whitelist,
            # not slug: safe_slug would mangle "hero_banner.svg".
            clean_asset = (str(asset).strip()
                           if asset and re.match(r"^[A-Za-z0-9._-]{1,120}$", str(asset).strip())
                           else "")
            if decision in ("approved", "changes_requested"):
                item["decision"] = decision
                audit.append({"event": decision, "at": now})
            if clean_comment and len(comments) < MAX_COMMENTS_PER_TOKEN:
                entry = {"text": clean_comment, "at": now}
                if clean_asset:
                    entry["asset"] = clean_asset  # anchored to one deliverable
                comments.append(entry)
                audit.append({"event": "comment", "at": now})
                # A comment-only action must be visible in the workflow rather
                # than leaving the reviewer with an indistinguishable pending item.
                if decision not in ("approved", "changes_requested") and item.get("decision") == "pending":
                    item["decision"] = "commented"
                    audit.append({"event": "commented", "at": now})
            item["comments"] = comments[-MAX_COMMENTS_PER_TOKEN:]
            item["audit"] = audit[-MAX_AUDIT_PER_TOKEN:]
            return item

        return self._mutate(_do)

    def list_all(self):
        """Inbox view: every token record, newest first (desktop-local)."""
        with self._lock:
            data = self._load()
        rows = []
        for record in data.values():
            if not isinstance(record, dict):
                continue
            comments = record.get("comments") if isinstance(record.get("comments"), list) else []
            rows.append({
                "token": record.get("token", ""),
                "campaign": record.get("campaign", ""),
                "created": record.get("created", ""),
                "revoked": bool(record.get("revoked")),
                "decision": record.get("decision", "pending"),
                "last_comment": (comments[-1] or {}).get("text", "") if comments else "",
                "comment_count": len(comments),
            })
        rows.sort(key=lambda r: str(r.get("created", "")), reverse=True)
        return rows[:200]

    def revoke(self, token):
        key = self._key(token)

        def _do(data):
            item = data.get(key)
            if not isinstance(item, dict):
                return False
            item["revoked"] = True
            audit = item.get("audit") if isinstance(item.get("audit"), list) else []
            audit.append({"event": "revoked", "at": datetime.now().isoformat()})
            item["audit"] = audit[-MAX_AUDIT_PER_TOKEN:]
            return True

        return self._mutate(_do)
