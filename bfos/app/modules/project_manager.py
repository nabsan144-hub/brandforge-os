"""Local campaign storage and export helpers.

Campaign identifiers and filenames are normalized before they reach the
filesystem. Existing campaigns are immutable on regeneration: a new run gets a
revision instead of silently resetting approval status or deleting deliverables.
"""

from __future__ import annotations

import json
import os
from modules.runtime_paths import data_dir as default_data_dir
import re
import shutil
import tempfile
from modules.state_locks import state_lock
import zipfile
from datetime import datetime
from typing import Any, Dict, List

from modules.campaign_pack import build_campaign_pack
from modules.security import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    safe_filename as _safe_filename,
    safe_slug as _safe_slug_base,
)


def _safe_slug(name: str, max_len: int = 60) -> str:
    return _safe_slug_base(name, max_len, fallback="default_campaign")


class ProjectManager:
    CAMPAIGN_STATUSES = (
        "draft",
        "internal_review",
        "ready_for_client",
        "changes_requested",
        "approved",
        "delivered",
    )

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = default_data_dir()
        self.base_dir = base_dir
        self.campaigns_dir = os.path.join(base_dir, "output", "campaigns")
        os.makedirs(self.campaigns_dir, exist_ok=True)
        # Serialize check → choose revision → write within this process.
        self._lock = state_lock(base_dir)

    @staticmethod
    def _revision_name(root: str, revision: int, max_len: int = 60) -> str:
        """Build a revision slug without truncating its ``_vN`` suffix."""
        suffix = f"_v{max(2, int(revision))}"
        root_len = max(1, max_len - len(suffix))
        root = _safe_slug_base(root, root_len, fallback="campaign")[:root_len].rstrip("_-") or "campaign"
        return _safe_slug_base(f"{root}{suffix}", max_len, fallback=f"campaign{suffix}")

    def _campaign_path(self, campaign_name: str) -> str:
        safe = _safe_slug(campaign_name, 60)
        path = os.path.join(self.campaigns_dir, safe)
        base_abs = os.path.realpath(self.campaigns_dir)
        path_abs = os.path.realpath(path)
        try:
            inside = os.path.commonpath([base_abs, path_abs]) == base_abs
        except ValueError:
            inside = False
        if not inside:
            raise ValueError("Path traversal blocked")
        return path

    @staticmethod
    def _write_artifact(path: str, content: Any) -> None:
        if isinstance(content, (bytes, bytearray)):
            raw = bytes(content)
            if len(raw) > 5_000_000: raise ValueError("Artifact exceeds the supported 5 MB limit; no bytes were saved")
            atomic_write_bytes(path, raw)
        else:
            text = str(content)
            if len(text.encode("utf-8")) > 5_000_000: raise ValueError("Artifact exceeds the supported 5 MB limit; no text was saved")
            atomic_write_text(path, text)

    def save_campaign(
        self,
        campaign_name: str,
        strategy_data: Dict,
        copy_data: Dict,
        visual_files: Dict,
        client_id: str = "default",
        analysis_data: Dict = None,
        lang: str = "en",
    ) -> str:
        """Persist a campaign and return the directory actually written.

        A pack-generation failure is non-fatal because the core campaign still
        has value. A storage failure is fatal and is never reported as a
        successful campaign.
        """
        strategy_data = strategy_data if isinstance(strategy_data, dict) else {}
        copy_data = copy_data if isinstance(copy_data, dict) else {}
        visual_files = visual_files if isinstance(visual_files, dict) else {}
        analysis_data = analysis_data if isinstance(analysis_data, dict) else {}
        client_id = _safe_slug(str(client_id or "default"), 40)

        try:
            pack_files = build_campaign_pack(strategy_data, copy_data, analysis_data, client_id)
        except Exception:
            pack_files = {}

        # Validate every artifact before creating a directory; never save a
        # valid-looking partial file by slicing bytes or Unicode text.
        prepared = {**visual_files, **pack_files}
        normalized = [_safe_filename(name) for name in prepared]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Artifact names collide after normalization")
        for name, content in prepared.items():
            size = len(content) if isinstance(content, (bytes,bytearray)) else len(str(content).encode("utf-8"))
            if size > 5_000_000: raise ValueError(f"{name}: artifact exceeds the supported 5 MB limit")
        with self._lock:
            safe_name = _safe_slug(campaign_name, 60)
            out_dir = self._campaign_path(safe_name)
            revision_number = 1
            revision_of = None
            if os.path.isfile(os.path.join(out_dir, "campaign.json")):
                root = re.sub(r"_v\d+$", "", safe_name)
                revision_number = 2
                while True:
                    candidate = self._revision_name(root, revision_number)
                    if not os.path.exists(self._campaign_path(candidate)):
                        break
                    revision_number += 1
                revision_of = root
                safe_name = candidate
                out_dir = self._campaign_path(safe_name)

            os.makedirs(out_dir, exist_ok=True)
            # An interrupted folder without campaign.json has no approval history;
            # clear its regular files before retrying. Do not follow directories.
            for fname in os.listdir(out_dir):
                fpath = os.path.join(out_dir, fname)
                if os.path.isfile(fpath) or os.path.islink(fpath):
                    os.remove(fpath)

            seo = analysis_data.get("seo_analysis", "") or copy_data.get("seo_analysis", "")
            report = (
                f"# {safe_name}\n\n"
                f"**Product:** {str(strategy_data.get('product_name', ''))[:80]}\n"
                f"**Industry:** {str(strategy_data.get('industry', ''))[:80]}\n"
                f"**Audience:** {str(strategy_data.get('target_audience', ''))[:80]}\n"
                f"**Client:** {client_id[:40]}\n"
                f"**Date:** {datetime.now().isoformat()}\n"
                f"**Research:** "
                + (
                    "LIVE web research (sources listed below)"
                    if strategy_data.get("research_live")
                    else "Offline template draft — no live web research was performed"
                )
                + "\n\n"
                f"## Market Research\n{str(strategy_data.get('market_research', 'None'))}\n\n"
                f"## Strategy\n{str(strategy_data.get('strategy_text', ''))}\n\n"
                f"## Copy (final)\n{str(copy_data.get('copy_text', ''))}\n\n"
                f"## SEO & conversion suggestions\n{str(seo)}\n"
            )
            self._write_artifact(os.path.join(out_dir, "campaign_report.md"), report)

            all_files = dict(visual_files)
            all_files.update(pack_files if isinstance(pack_files, dict) else {})
            for fname, content in all_files.items():
                self._write_artifact(os.path.join(out_dir, _safe_filename(fname)), content)

            now = datetime.now().isoformat()
            payload = {
                "campaign_name": safe_name,
                "client_id": client_id,
                "provider": strategy_data.get("provider", "offline"),
                "lang": str(lang or "en")[:5],
                "research_live": bool(strategy_data.get("research_live", False)),
                "strategy": strategy_data,
                "copy": copy_data,
                "analysis": analysis_data,
                "visuals": list(visual_files.keys()),
                "status": "draft",
                "revision_number": revision_number,
                "status_history": [{"status": "draft", "at": now}],
                "created": now,
            }
            if revision_of:
                payload["revision_of"] = revision_of
            target = os.path.join(out_dir, "campaign.json")
            try:
                atomic_write_json(target, payload)
            except Exception:
                # There is no valid campaign.json yet, so removing this folder
                # cannot destroy a prior saved campaign (revisions use new dirs).
                shutil.rmtree(out_dir, ignore_errors=True)
                raise
            return out_dir

    def revise_text(self, campaign_name: str, changes: Dict[str,str]) -> Dict[str,Any]:
        """New draft revision; keep original approvals and immutable assets."""
        with self._lock:
            source = self.get_campaign(campaign_name)
            if not source: raise FileNotFoundError("Campaign not found")
            strategy, copy, analysis = (dict(source.get(k) or {}) for k in ("strategy","copy","analysis"))
            for key, value in changes.items():
                if key not in ("strategy","copy","seo") or not isinstance(value,str) or len(value)>20000:
                    raise ValueError("Only strategy, copy and SEO text up to 20,000 characters can be edited")
                if key=="strategy": strategy["strategy_text"]=value
                elif key=="copy": copy["copy_text"]=value
                else: analysis["seo_analysis"]=value
            from modules.claim_guard import review_marketing_copy
            from modules.campaign_quality import score_campaign
            analysis["claim_review"]=review_marketing_copy(copy.get("copy_text", ""))
            analysis["quality_score"]=score_campaign(copy.get("copy_text",""),"","",analysis["claim_review"])
            analysis["edit_note"]="Manual text revision. Visuals are unchanged; generate again to redesign them."
            files={}
            for name in source.get("visuals",[]):
                path=os.path.join(self._campaign_path(campaign_name),_safe_filename(name))
                if not os.path.isfile(path) or os.path.islink(path): continue
                with open(path,"rb") as handle: content=handle.read(5_000_001)
                if len(content)>5_000_000: raise ValueError("Original artifact exceeds export limit")
                files[name]=content if name.lower().endswith((".png",".jpg",".jpeg")) else content.decode("utf-8")
            directory=self.save_campaign(campaign_name,strategy,copy,files,source.get("client_id","default"),analysis,source.get("lang","en"))
            return {"name":os.path.basename(directory),"status":"draft","note":analysis["edit_note"]}

    def update_campaign_status(self, campaign_name: str, status: str) -> Dict[str, Any]:
        """Persist a validated workflow status and bounded audit history."""
        normalized = str(status or "").strip().lower()
        if normalized not in self.CAMPAIGN_STATUSES:
            raise ValueError("Invalid campaign status")
        with self._lock:
            safe = _safe_slug(campaign_name, 60)
            path = self._campaign_path(safe)
            json_path = os.path.join(path, "campaign.json")
            if not os.path.isfile(json_path):
                raise FileNotFoundError("Campaign not found")
            with open(json_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("Campaign data is corrupt")
            if data.get("status") != normalized:
                history = data.get("status_history") if isinstance(data.get("status_history"), list) else []
                history.append({"status": normalized, "at": datetime.now().isoformat()})
                data["status"] = normalized
                data["status_history"] = history[-50:]
                atomic_write_json(json_path, data)
            return {
                "name": safe,
                "status": data.get("status", normalized),
                "status_history": data.get("status_history", []),
            }

    def create_revision(self, campaign_name: str) -> Dict[str, Any]:
        """Copy a campaign into a new draft revision without mutating its source."""
        with self._lock:
            source_name = _safe_slug(campaign_name, 60)
            source_path = self._campaign_path(source_name)
            source_json = os.path.join(source_path, "campaign.json")
            if not os.path.isfile(source_json):
                raise FileNotFoundError("Campaign not found")
            with open(source_json, "r", encoding="utf-8") as handle:
                source = json.load(handle)
            if not isinstance(source, dict):
                raise ValueError("Campaign data is corrupt")

            root = re.sub(r"_v\d+$", "", source_name)
            try:
                current_revision = int(source.get("revision_number") or 1)
            except (TypeError, ValueError) as exc:
                raise ValueError("Invalid campaign revision number") from exc
            revision = max(1, current_revision) + 1
            while True:
                target_name = self._revision_name(root, revision)
                target_path = self._campaign_path(target_name)
                if not os.path.exists(target_path):
                    break
                revision += 1

            try:
                shutil.copytree(source_path, target_path, ignore=shutil.ignore_patterns("*_export.zip", "*.tmp"))
                now = datetime.now().isoformat()
                source_label = source.get("campaign_name", source_name)
                source["campaign_name"] = target_name
                source["revision_of"] = source.get("revision_of") or source_label
                source["revision_number"] = revision
                source["status"] = "draft"
                source["status_history"] = [
                    {"status": "draft", "at": now, "note": f"Revision {revision} created from {source_name}"}
                ]
                source["created"] = now
                atomic_write_json(os.path.join(target_path, "campaign.json"), source)
            except Exception:
                shutil.rmtree(target_path, ignore_errors=True)
                raise
            return {
                "name": target_name,
                "revision_of": source["revision_of"],
                "revision_number": revision,
                "status": "draft",
            }

    def list_campaigns(self) -> List[Dict[str, Any]]:
        with self._lock:
            out = []
            try:
                entries = os.listdir(self.campaigns_dir)
            except OSError:
                return []
            for name in entries:
                path = os.path.join(self.campaigns_dir, name)
                if not os.path.isdir(path) or os.path.islink(path):
                    continue
                json_path = os.path.join(path, "campaign.json")
                try:
                    with open(json_path, "r", encoding="utf-8") as handle:
                        data = json.load(handle)
                    if not isinstance(data, dict):
                        continue
                    info = {
                        "name": name,
                        "files": len(os.listdir(path)),
                        "created": data.get("created"),
                        "client_id": data.get("client_id", "default"),
                        "product": (data.get("strategy") or {}).get("product_name", ""),
                        "status": data.get("status", "draft"),
                        "revision_number": data.get("revision_number", 1),
                        "revision_of": data.get("revision_of"),
                    }
                    out.append(info)
                except (OSError, json.JSONDecodeError, TypeError):
                    continue
            out.sort(key=lambda item: (item.get("created") or ""), reverse=True)
            return out[:50]

    def campaign_dir(self, campaign_name: str) -> str:
        """Public accessor for the on-disk folder of a (slug-safe) campaign."""
        return self._campaign_path(_safe_slug(str(campaign_name or ""), 60))

    def get_campaign(self, campaign_name: str) -> Dict[str, Any]:
        with self._lock:
            safe = _safe_slug(campaign_name, 60)
            path = self._campaign_path(safe)
            json_path = os.path.join(path, "campaign.json")
            try:
                with open(json_path, "r", encoding="utf-8") as handle:
                    result = json.load(handle)
                if not isinstance(result, dict):
                    return {}
            except (OSError, json.JSONDecodeError, TypeError):
                return {}
            result["files"] = []
            try:
                names = sorted(os.listdir(path))
            except OSError:
                return result
            for fname in names:
                fpath = os.path.join(path, fname)
                if not os.path.isfile(fpath) or os.path.islink(fpath) or fname.endswith("_export.zip"):
                    continue
                try:
                    size = os.path.getsize(fpath)
                    entry = {"name": fname, "size": size, "ext": os.path.splitext(fname)[1].lower()}
                    if entry["ext"] in {".svg", ".html", ".md", ".txt", ".csv", ".json"} and size < 300_000:
                        with open(fpath, "r", encoding="utf-8") as handle:
                            entry["content"] = handle.read()
                    result["files"].append(entry)
                except (OSError, UnicodeDecodeError):
                    continue
            return result

    def get_campaign_file(self, campaign_name: str, filename: str):
        with self._lock:
            safe = _safe_slug(campaign_name, 60)
            path = self._campaign_path(safe)
            full = os.path.join(path, _safe_filename(filename))
            try:
                base_real = os.path.realpath(path)
                full_real = os.path.realpath(full)
                inside = os.path.commonpath([base_real, full_real]) == base_real
            except ValueError:
                inside = False
            if not inside or os.path.islink(full) or not os.path.isfile(full_real):
                return None
            return full

    def export_zip(self, campaign_name: str) -> str:
        """Build a unique temporary export ZIP and return its path."""
        with self._lock:
            safe = _safe_slug(campaign_name, 60)
            path = self._campaign_path(safe)
            if not os.path.isdir(path) or not os.path.isfile(os.path.join(path, "campaign.json")):
                raise FileNotFoundError("Campaign not found")
            fd, zip_path = tempfile.mkstemp(prefix=f"{safe}_", suffix="_export.zip")
            os.close(fd)
            try:
                base_real = os.path.realpath(path)
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    for root, dirs, files in os.walk(path, followlinks=False):
                        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
                        for fname in files:
                            full = os.path.join(root, fname)
                            if fname.endswith("_export.zip") or os.path.islink(full):
                                continue
                            if os.path.commonpath([base_real, os.path.realpath(full)]) != base_real:
                                continue
                            archive.write(full, os.path.relpath(full, path))
                return zip_path
            except Exception:
                try:
                    os.remove(zip_path)
                except OSError:
                    pass
                raise
