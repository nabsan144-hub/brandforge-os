"""LOW-02 regression: MemoryManager uses ONE long-lived SQLite connection
under a lock (was: connect/close per call — fine solo, latent under the
concurrent chat load the threadpool produces)."""

import threading


def _fresh_manager(tmp_path):
    from modules.memory_manager import MemoryManager
    return MemoryManager(base_dir=str(tmp_path))


def test_shared_connection_reused_across_calls(tmp_path):
    mm = _fresh_manager(tmp_path)
    mm.add_chat("user", "hello world")
    mm.add_chat("assistant", "hi")
    assert mm._conn is not None, "connection should be created lazily and KEPT"
    conn_obj = mm._conn
    assert mm.count_history() == 2
    assert mm._conn is conn_obj, "subsequent calls must reuse the same connection"
    # Search must find the matching doc whether the vector backend is installed
    # (semantic, may return related docs too) or SQL-only (exact LIKE).
    hits = mm.search_history("hello")
    assert hits, "search must return the matching doc"
    assert any("hello world" in str(h["message"]) for h in hits)
    assert mm._conn is conn_obj
    mm.save_campaign_insight("camp", "prod", "insight")
    assert mm._conn is conn_obj


def test_concurrent_writes_all_land(tmp_path):
    mm = _fresh_manager(tmp_path)
    n_threads, per_thread = 8, 25

    def worker(tid):
        for i in range(per_thread):
            mm.add_chat("user", f"t{tid}-m{i}")

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert mm.count_history() == n_threads * per_thread


def test_broken_connection_is_recreated(tmp_path):
    mm = _fresh_manager(tmp_path)
    mm.add_chat("user", "x")
    dead = mm._conn
    dead.close()  # simulate the db dropping under a running process
    mm.add_chat("user", "y")  # must recover via _db_run's re-init retry
    assert mm.count_history() == 2
    assert mm._conn is not dead
