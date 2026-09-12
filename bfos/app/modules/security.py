"""Single source of truth for input and file-safety helpers.

Sanitize customer-controlled values as data at input boundaries. Escape them
again at render boundaries (SVG, HTML, Markdown viewers and reports). State
files are written through the atomic helpers so a process crash cannot leave a
truncated JSON, environment or document file.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Any, Optional

ALLOWED_FILE_EXTS = {".svg", ".html", ".md", ".json", ".txt", ".png", ".jpg", ".csv"}


# A deliberately small set of patterns handles both complete and common
# unterminated tags without destroying normal prose such as "revenue < target".
_UNTERMINATED_TAG_RE = re.compile(
    r"<(?:!--|/?(?:script|style|iframe|object|embed|img|svg|a|form|input|meta|link)\b)[^>]*$",
    re.IGNORECASE,
)


def safe_slug(name: str, max_len: int = 60, lower: bool = True, fallback: str = "default") -> str:
    """Return a filesystem/URL-safe identifier.

    Only ASCII letters, digits, underscores and hyphens survive. This makes
    traversal impossible by construction; the final checks remain defense in
    depth for callers that change the normalization rules later.
    """
    if not name or not isinstance(name, str):
        return fallback
    try:
        max_len = max(1, int(max_len))
    except (TypeError, ValueError):
        max_len = 60
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_-")
    if lower:
        safe = safe.lower()
    safe = safe[:max_len]
    if not safe or safe in (".", ".."):
        return fallback
    if ".." in safe or "/" in safe or "\\" in safe:
        return fallback
    return safe


def safe_text(text: Any, max_len: int = 500) -> str:
    """Strip markup-like tags and control characters while preserving prose.

    This is data sanitization, not HTML escaping. Newlines and tabs are kept so
    campaign briefs remain readable; output renderers must still escape values.
    """
    if text is None:
        return ""
    try:
        max_len = max(0, int(max_len))
    except (TypeError, ValueError):
        max_len = 500
    value = str(text)[:max_len]
    value = re.sub(r"<[^>]*>", "", value)
    value = _UNTERMINATED_TAG_RE.sub("", value)
    # Remove NUL and other non-printing controls, but retain whitespace useful
    # in briefs. This also keeps ReportLab and terminal output from choking.
    value = "".join(ch for ch in value if ch in "\n\r\t" or ord(ch) >= 32)
    return value.strip()


def safe_hex(color: str, fallback: str = "#E8B54A") -> str:
    """Validate and normalize a CSS hex color; invalid input falls back."""
    if not color or not isinstance(color, str):
        return fallback
    value = color.strip()
    if not value.startswith("#"):
        value = "#" + value
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    if len(value) != 7:
        return fallback
    try:
        int(value[1:], 16)
    except ValueError:
        return fallback
    return value.upper()


def safe_filename(fname: str, max_len: int = 80) -> str:
    """Keep one filename (including a known extension) and block traversal."""
    try:
        max_len = max(1, int(max_len))
    except (TypeError, ValueError):
        max_len = 80
    base = os.path.basename(str(fname or ""))[:max_len]
    base = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", base).strip(" ._")
    if not base or base in (".", ".."):
        return "file.txt"
    ext = os.path.splitext(base)[1].lower()
    if ext not in ALLOWED_FILE_EXTS:
        base += ".txt"
    return base


def safe_client_id(name: str) -> str:
    """Stricter profile identifier: lowercase letters, digits and underscores."""
    if not name or not isinstance(name, str):
        return "default"
    safe = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")[:40]
    if not safe or safe in (".", "..") or ".." in safe or "/" in safe or "\\" in safe:
        return "default"
    return safe


def _atomic_write(path: str, data: bytes, mode: Optional[int] = None) -> None:
    """Write bytes to *path* using fsync + same-directory replace."""
    target = os.path.abspath(path)
    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{os.path.basename(target)}.", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            # os.fchmod is Unix-only: on Windows (the desktop buyer's actual
            # OS) it raises AttributeError and crashed every mode'd write.
            # Permissions stay best-effort there (NTFS ACLs are out of scope
            # for the stdlib); data integrity (fsync + atomic replace) is not.
            if mode is not None and hasattr(os, "fchmod"):
                os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            try:
                os.chmod(temp, mode)
            except OSError:
                pass
        os.replace(temp, target)
    finally:
        try:
            if os.path.exists(temp):
                os.remove(temp)
        except OSError:
            pass


def atomic_write_bytes(path: str, content: bytes, mode: Optional[int] = None) -> None:
    """Atomically write bytes."""
    _atomic_write(path, bytes(content), mode=mode)


def atomic_write_text(path: str, content: str, mode: Optional[int] = None) -> None:
    """Atomically write UTF-8 text."""
    _atomic_write(path, str(content).encode("utf-8"), mode=mode)


def atomic_write_json(path: str, value: Any, mode: Optional[int] = None) -> None:
    """Atomically serialize JSON with stable, human-editable formatting."""
    content = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    _atomic_write(path, content.encode("utf-8"), mode=mode)
