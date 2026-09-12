"""Local memory layers: SQLite and editable Markdown.

All chat queries are client-scoped when a client is supplied. SQLite access is
serialized per manager and uses WAL mode so concurrent dashboard requests do not
silently lose writes. Experimental Chroma initialization is disabled in this release.
"""

from __future__ import annotations

import logging
import os
from modules.runtime_paths import data_dir as default_data_dir
import secrets
import sqlite3
from modules.state_locks import state_lock
from datetime import datetime
from typing import Dict, List

from modules.security import atomic_write_text, safe_slug, safe_text

log = logging.getLogger(__name__)


def _slug_client(client_id: str) -> str:
    return safe_slug(str(client_id or "default"), 40, fallback="default")


class MemoryManager:
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = default_data_dir()
        self.base_dir = base_dir
        self.db_path = os.path.join(base_dir, "brandforge_memory.db")
        self.memory_dir = os.path.join(base_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        self.long_term_file = os.path.join(self.memory_dir, "long_term.md")
        self.preferences_file = os.path.join(self.memory_dir, "preferences.md")
        self._lock = state_lock(base_dir)
        self._conn = None
        self.last_error = None
        self._init_db()
        self._init_markdown_files()
        self.vector_db = None
        self._init_vector_db()

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        # Best-effort finalization also covers short-lived CLI/daemon engines.
        try:
            self.close()
        except Exception:
            pass

    def _db_run(self, fn, commit: bool = False):
        """Run a cursor callback on the shared connection, retrying once."""
        for attempt in (1, 2):
            try:
                with self._lock:
                    if self._conn is None:
                        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
                        self._conn.execute("PRAGMA busy_timeout=10000")
                    cursor = self._conn.cursor()
                    try:
                        result = fn(cursor)
                        if commit:
                            self._conn.commit()
                        self.last_error = None
                        return result
                    finally:
                        cursor.close()
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                with self._lock:
                    try:
                        if self._conn is not None:
                            self._conn.rollback()
                            self._conn.close()
                    except Exception:
                        pass
                    self._conn = None
                if attempt == 1:
                    self._init_db()
                    continue
                self.last_error = 'Memory database is unavailable; this operation was not confirmed.'
                return None
            except Exception:
                with self._lock:
                    try:
                        if self._conn is not None:
                            self._conn.rollback()
                    except Exception:
                        pass
                self.last_error = 'Memory database operation failed; no success was confirmed.'
                return None
        return None

    def _init_db(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    role TEXT,
                    message TEXT,
                    client_id TEXT DEFAULT 'default'
                )"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS campaigns_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    campaign_name TEXT,
                    product_name TEXT,
                    key_insights TEXT,
                    client_id TEXT DEFAULT 'default'
                )"""
            )
            # Migrations for databases created before client-scoped insights.
            try:
                cursor.execute("ALTER TABLE campaigns_memory ADD COLUMN client_id TEXT DEFAULT 'default'")
            except sqlite3.OperationalError:
                pass
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_client ON chat_history(client_id, id DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_memory_client ON campaigns_memory(client_id, id DESC)")
            conn.commit()
        except Exception:
            pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _init_markdown_files(self):
        defaults = (
            (self.long_term_file, "# BrandForge Long-Term Memory\n\n> Editable by Founder\n\n## Memory\n\n"),
            (self.preferences_file, "# Founder Preferences\n\n- Tone: Executive, Bold\n- Brand: BrandForge OS\n\n"),
        )
        for path, content in defaults:
            if not os.path.exists(path):
                try:
                    atomic_write_text(path, content)
                except OSError:
                    pass

    def _init_vector_db(self):
        # Disabled in 1.4 while upstream advisories remain unresolved. Do not
        # auto-enable an old Chroma install just because it is importable.
        # Existing SQLite/Markdown records stay available; no server starts.
        self.vector_db = None

    def add_chat(self, role: str, message: str, client_id: str = "default") -> bool:
        client_id = _slug_client(client_id)
        role = safe_text(role, 20) or "unknown"
        message = str(message or "")
        if len(message) > 30000:
            self.last_error = 'Chat message exceeds the memory storage limit; it was not truncated or saved.'
            return False

        def _insert(cursor):
            cursor.execute(
                "INSERT INTO chat_history (timestamp, role, message, client_id) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), role, message, client_id),
            )
            return True

        saved = self._db_run(_insert, commit=True) is True
        if self.vector_db and message:
            try:
                self.vector_db.add(
                    documents=[f"{role}: {message[:500]}"],
                    ids=[f"chat_{secrets.token_hex(12)}"],
                    metadatas=[
                        {
                            "role": role,
                            "timestamp": datetime.now().isoformat(),
                            "client_id": client_id,
                        }
                    ],
                )
            except Exception:
                pass

        return saved

    @staticmethod
    def _limit(value: int, maximum: int = 100, default: int = 10) -> int:
        try:
            return max(0, min(int(value), maximum))
        except (TypeError, ValueError):
            return default

    def get_recent_chat_history(self, limit: int = 10, client_id: str = None) -> List[Dict]:
        limit = self._limit(limit)

        def _query(cursor):
            if client_id:
                cursor.execute(
                    "SELECT timestamp, role, message FROM chat_history WHERE client_id = ? ORDER BY id DESC LIMIT ?",
                    (_slug_client(client_id), limit),
                )
            else:
                cursor.execute("SELECT timestamp, role, message FROM chat_history ORDER BY id DESC LIMIT ?", (limit,))
            return cursor.fetchall()

        rows = self._db_run(_query) or []
        return [{"timestamp": row[0], "role": row[1], "message": row[2]} for row in reversed(rows)]

    def count_history(self) -> int:
        def _count(cursor):
            cursor.execute("SELECT COUNT(*) FROM chat_history")
            return cursor.fetchone()[0]

        return self._db_run(_count) or 0

    def prune_chat_history(self, keep: int = 20000) -> int:
        """Delete the oldest chat rows beyond a positive opt-in limit."""
        try:
            keep = max(0, int(keep))
        except (TypeError, ValueError):
            return 0
        if keep <= 0:
            return 0

        def _prune(cursor):
            cursor.execute(
                "DELETE FROM chat_history WHERE id NOT IN "
                "(SELECT id FROM chat_history ORDER BY id DESC LIMIT ?)",
                (keep,),
            )
            return cursor.rowcount

        return self._db_run(_prune, commit=True) or 0

    def search_history(self, query: str, limit: int = 5, client_id: str = "default") -> List[Dict]:
        """Search history without allowing negative LIMIT values or cross-client leaks."""
        query = str(query or "")
        if not query or len(query) > 200:
            return []
        limit = max(1, min(self._limit(limit), 100))
        client_id = _slug_client(client_id)
        if self.vector_db:
            try:
                results = self.vector_db.query(
                    query_texts=[query[:200]], n_results=limit, where={"client_id": client_id}
                )
                docs = results.get("documents", [[]])[0] or []
                metas = results.get("metadatas", [[]])[0] or []
                if docs:
                    # strict=True: a malformed vector-DB response with
                    # mismatched documents/metadatas lengths must fall through
                    # to the SQLite path, not silently truncate/misalign.
                    return [{"message": doc, "metadata": meta} for doc, meta in zip(docs, metas, strict=True)]
            except Exception as exc:
                log.debug("vector search failed for client %s (%s) — falling back to SQLite LIKE", client_id, exc)

        # Escape LIKE metacharacters so a query of '%' does not become an
        # unbounded table scan/result dump.
        escaped = query[:50].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

        def _like(cursor):
            cursor.execute(
                "SELECT timestamp, role, message FROM chat_history "
                "WHERE client_id = ? AND message LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT ?",
                (client_id, f"%{escaped}%", limit),
            )
            return cursor.fetchall()

        rows = self._db_run(_like) or []
        return [{"timestamp": row[0], "role": row[1], "message": row[2]} for row in rows]

    def _long_term_path(self, client_id: str = "default") -> str:
        slug = _slug_client(client_id)
        if slug == "default":
            return self.long_term_file
        path = os.path.join(self.memory_dir, f"long_term_{slug}.md")
        try:
            memory_real = os.path.realpath(self.memory_dir)
            path_real = os.path.realpath(path)
            if os.path.commonpath([memory_real, path_real]) != memory_real:
                raise ValueError("Path traversal blocked")
        except ValueError:
            raise ValueError('Memory path is outside the configured folder') from None
        return path

    def save_long_term(self, key: str, value: str, client_id: str = 'default') -> bool:
        if len(str(key)) > 80 or len(str(value)) > 1000:
            self.last_error = 'Memory note exceeds its supported length; it was not saved.'
            return False
        key, value = safe_text(key,80), safe_text(value,1000)
        if not key or not value:
            self.last_error = 'Memory note is empty; it was not saved.'
            return False
        path = self._long_term_path(client_id)
        try:
            with self._lock:
                existing = ''
                if os.path.exists(path):
                    with open(path,'r',encoding='utf-8') as handle:
                        existing = handle.read(65537)
                if len(existing.encode('utf-8')) > 50*1024:
                    stem=os.path.splitext(os.path.basename(path))[0]
                    archive=os.path.join(self.memory_dir,f"{stem}_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}.md")
                    os.replace(path,archive)
                    existing=''
                if not existing: existing='# BrandForge Long-Term Memory\n\n## Memory\n\n'
                entry=f"\n## {key} - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{value}\n"
                atomic_write_text(path,existing+entry)
                if self.vector_db:
                    try:
                        self.vector_db.add(documents=[f"{key}: {value[:500]}"],
                            ids=[f"lt_{_slug_client(client_id)}_{secrets.token_hex(12)}"],
                            metadatas=[{'type':'long_term','key':key,'client_id':_slug_client(client_id)}])
                    except Exception:
                        pass  # The durable Markdown write succeeded; the optional cache did not.
                self.last_error = None
                return True
        except (OSError, UnicodeError):
            self.last_error = 'Memory note could not be saved; preserve the existing file and check storage.'
            return False

    def get_long_term_memory(self, client_id: str = 'default') -> str:
        try:
            with open(self._long_term_path(client_id),'rb') as handle:
                size=handle.seek(0,os.SEEK_END)
                start=max(0,size-24000);handle.seek(start)
                data=handle.read(24000)
            return data.decode('utf-8',errors='replace' if start else 'strict')[-5000:]
        except FileNotFoundError:
            return ''
        except (OSError,UnicodeError):
            self.last_error='Long-term memory could not be read.'
            return ''

    def save_campaign_insight(
        self, campaign_name: str, product_name: str, insight: str, client_id: str = "default"
    ) -> None:
        client_id = _slug_client(client_id)

        def _insert(cursor):
            cursor.execute(
                "INSERT INTO campaigns_memory "
                "(timestamp, campaign_name, product_name, key_insights, client_id) VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(),
                    str(campaign_name or "")[:80],
                    str(product_name or "")[:80],
                    str(insight or "")[:500],
                    client_id,
                ),
            )

        self._db_run(_insert, commit=True)
        self.save_long_term(
            f"Campaign: {str(campaign_name or '')[:40]} [{client_id[:20]}]",
            f"Product: {str(product_name or '')[:40]}\nInsight: {str(insight or '')[:200]}",
            client_id=client_id,
        )

    def get_all_memories_for_prompt(self, client_id: str = "default") -> str:
        long_term = self.get_long_term_memory(client_id)[-1500:]
        recent = self.get_recent_chat_history(limit=2, client_id=client_id)
        recent_text = "\n".join(f"{item['role']}: {item['message'][:80]}" for item in recent)
        return f"[LONG TERM]:\n{long_term}\n[RECENT]:\n{recent_text}\n"
