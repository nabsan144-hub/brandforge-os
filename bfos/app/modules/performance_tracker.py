"""Manual campaign-performance tracker — the loop neither Jasper nor
AdCreative close at this price.

The owner enters what actually happened after publishing (spend, clicks,
leads, revenue); the app computes CPC / CPL / ROAS / ROI% and shows it next
to the campaign's own quality score, so "was the AI's output any good"
becomes a number instead of a feeling. Entries are manual by design — no
pixels, no tracking scripts, nothing leaves the machine.
"""
from __future__ import annotations

import os
from modules.state_locks import state_lock
from modules.state_io import read_object, LocalStateError
from datetime import datetime
from typing import Any, Dict, List, Optional

from modules.security import atomic_write_json, safe_slug, safe_text

MAX_ENTRIES_PER_CAMPAIGN = 500
_LIMITS = {
    "spend": 10_000_000.0, "revenue": 10_000_000.0,
    "clicks": 1_000_000_000, "leads": 1_000_000_000,
}


def _num(value: Any, field: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number") from None
    if out < 0 or out != out or out > _LIMITS[field]:  # NaN + bounds
        raise ValueError(f"{field} out of range")
    return out


class PerformanceTracker:
    def __init__(self, base_dir: str) -> None:
        self.path = os.path.join(base_dir, "performance.json")
        self._lock = state_lock(base_dir)

    def _load(self) -> Dict[str, List[Dict[str, Any]]]:
        value = read_object(self.path)
        try:
            for rows in value.values():
                if not isinstance(rows, list): raise ValueError('invalid rows')
                for row in rows:
                    if not isinstance(row, dict): raise ValueError('invalid entry')
                    for key in _LIMITS: _num(row.get(key,0),key)
        except (ValueError, TypeError) as exc:
            raise LocalStateError('Performance records are unreadable. Existing data was preserved.') from exc
        return value

    def add_entry(self, campaign: str, spend: Any, clicks: Any = 0,
                  leads: Any = 0, revenue: Any = 0, note: str = "") -> Dict[str, Any]:
        spend = _num(spend, "spend")
        clicks = int(_num(clicks, "clicks"))
        leads = int(_num(leads, "leads"))
        revenue = _num(revenue, "revenue")
        entry = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "spend": spend, "clicks": clicks, "leads": leads,
            "revenue": revenue, "note": safe_text(note, 300),
        }
        key = safe_slug(campaign, 60)
        with self._lock:
            data = self._load()
            rows = data.get(key) if isinstance(data.get(key), list) else []
            rows.append(entry)
            data[key] = rows[-MAX_ENTRIES_PER_CAMPAIGN:]
            atomic_write_json(self.path, data, mode=0o600)
        return entry

    def entries(self, campaign: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._load().get(safe_slug(campaign, 60), [])
        return rows if isinstance(rows, list) else []

    @staticmethod
    def _safe_div(a: float, b: float) -> Optional[float]:
        return round(a / b, 4) if b else None

    def summary(self, campaign: str) -> Dict[str, Any]:
        rows = self.entries(campaign)
        spend = sum(float(r.get("spend", 0)) for r in rows)
        revenue = sum(float(r.get("revenue", 0)) for r in rows)
        clicks = sum(int(r.get("clicks", 0)) for r in rows)
        leads = sum(int(r.get("leads", 0)) for r in rows)
        profit = revenue - spend
        return {
            "entries": len(rows),
            "spend": round(spend, 2), "revenue": round(revenue, 2),
            "clicks": clicks, "leads": leads,
            "profit": round(profit, 2),
            "cpc": self._safe_div(spend, clicks),
            "cpl": self._safe_div(spend, leads),
            "roas": self._safe_div(revenue, spend),
            "roi_pct": self._safe_div(profit, spend) and round(self._safe_div(profit, spend) * 100, 1),
        }
