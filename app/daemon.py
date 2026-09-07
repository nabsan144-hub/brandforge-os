"""Opt-in local maintenance. No generation, publishing, or hidden provider calls."""
import logging
import os
import time
from datetime import datetime
from modules.runtime_paths import data_dir
from modules.state_locks import state_lock

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    BackgroundScheduler = None

HAS_SCHEDULER = BackgroundScheduler is not None
log = logging.getLogger(__name__)


class BrandForgeDaemon:
    def __init__(self):
        self.base_dir = data_dir()
        self.is_running = False
        self.scheduler = BackgroundScheduler() if HAS_SCHEDULER else None
        self.last_error = None

    def _failed(self, message):
        self.last_error = message
        log.warning(message)
        return False

    def start(self):
        if self.is_running:
            return True
        if self.scheduler is None:
            return self._failed('Local scheduler is not installed; maintenance did not start.')
        try:
            self.scheduler.add_job(self.heartbeat, 'interval', minutes=30, id='heartbeat', replace_existing=True)
            self.scheduler.add_job(self.daily_summary, 'cron', hour=9, minute=0, id='daily_summary', replace_existing=True)
            self.scheduler.add_job(self.memory_cleanup, 'interval', hours=6, id='memory_cleanup', replace_existing=True)
            self.scheduler.start()
            self.is_running = True
            self.last_error = None
            return True
        except Exception:
            return self._failed('Local maintenance could not start.')

    def stop(self):
        try:
            if self.scheduler is not None and self.scheduler.running:
                self.scheduler.shutdown()
            self.is_running = False
            return True
        except Exception:
            return self._failed('Local maintenance shutdown was not confirmed.')

    def heartbeat(self):
        path = os.path.join(self.base_dir, 'output', 'daemon.log')
        try:
            with state_lock(self.base_dir):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if os.path.exists(path) and os.path.getsize(path) >= 1_000_000:
                    # If rotation fails, do not append indefinitely to an already
                    # oversized log. Only these daemon-owned log files are touched.
                    os.replace(path, path + '.1')
                with open(path, 'a', encoding='utf-8') as handle:
                    handle.write(datetime.now().isoformat() + ' — Local maintenance heartbeat\n')
            return True
        except OSError:
            return self._failed('Local heartbeat could not be written; check disk space and permissions.')

    def daily_summary(self):
        from modules.client_manager import ClientManager
        from modules.memory_manager import MemoryManager
        from modules.project_manager import ProjectManager
        try:
            clients = ClientManager(base_dir=self.base_dir)
            active = clients.get_active_client()
            campaigns = ProjectManager(base_dir=self.base_dir).list_campaigns()
            count = sum(c.get('client_id') == active.get('client_id') for c in campaigns)
            with MemoryManager(base_dir=self.base_dir) as memory:
                ok = memory.save_long_term('Daily Summary', f"Active brand has {count} saved campaigns. Review work before publishing.", client_id=active.get('client_id', 'default'))
            return True if ok else self._failed('Local daily summary was not saved.')
        except Exception:
            return self._failed('Local daily summary could not be completed.')

    def memory_cleanup(self):
        try:
            cap = int(os.environ.get('BRANDFORGE_MEMORY_MAX_ROWS', '0') or '0')
        except ValueError:
            return self._failed('Memory retention setting is invalid; no rows were deleted.')
        if cap <= 0:
            return 0  # Default: never delete chat history.
        from modules.memory_manager import MemoryManager
        try:
            with MemoryManager(base_dir=self.base_dir) as memory:
                count = memory.count_history()
                if memory.last_error: return self._failed('Memory could not be inspected; no cleanup was confirmed.')
                result = memory.prune_chat_history(cap) if count > cap else 0
                if memory.last_error: return self._failed('Memory cleanup was not confirmed.')
                return result
        except Exception:
            return self._failed('Memory cleanup could not be completed.')


if __name__ == '__main__':
    daemon = BrandForgeDaemon()
    if not daemon.start():
        raise SystemExit(1)
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        daemon.stop()
