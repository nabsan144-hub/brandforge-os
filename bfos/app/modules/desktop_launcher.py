"""Managed loopback Desktop startup; do not mistake another open port for readiness."""
from dataclasses import dataclass
import ipaddress
import threading
import time


def validate_bind(host, port):
    value = str(host).strip().lower()
    try:
        address = ipaddress.ip_address(value)
        local = (address.ipv4_mapped or address).is_loopback if address.version == 6 else address.is_loopback
    except ValueError:
        local = value == 'localhost'
    if not local or isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError('Desktop must use a loopback host and a valid port. Use the separate Cloud service for remote access.')
    return value


def make_server(host='127.0.0.1', port=8000, engine=None):
    host = validate_bind(host, port)
    import uvicorn
    import server as runtime
    if engine is not None:
        from modules.project_manager import ProjectManager
        # A CLI --provider override must be the engine used by HTTP requests,
        # not an unused second engine while the server reloads old settings.
        with runtime._core_lock:
            runtime._engine = engine
            runtime._cm = engine.clients
            runtime._pm = ProjectManager(base_dir=engine.base_dir)
            runtime._tools = engine.tools
            runtime._approvals = None
    config = uvicorn.Config(runtime.app, host=host, port=port, proxy_headers=False,
                            timeout_graceful_shutdown=5, log_level='warning')
    return uvicorn.Server(config)


@dataclass
class RunningDesktop:
    server: object
    thread: threading.Thread
    host: str
    port: int

    @property
    def url(self):
        host = f'[{self.host}]' if ':' in self.host else self.host
        return f'http://{host}:{self.port}/'

    def stop(self, timeout=8):
        self.server.should_exit = True
        self.thread.join(timeout)
        return not self.thread.is_alive()


def start_background(engine=None, *, host='127.0.0.1', port=8000, timeout=10):
    server = make_server(host, port, engine)
    failed = threading.Event()
    def run():
        try:
            server.run()
        except (Exception, SystemExit):
            failed.set()
    thread = threading.Thread(target=run, daemon=True, name='brandforge-desktop')
    handle = RunningDesktop(server, thread, host, port)
    thread.start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not failed.is_set() and thread.is_alive():
        if server.started:
            if port == 0:
                handle.port = server.servers[0].sockets[0].getsockname()[1]
            return handle
        thread.join(.025)
    handle.stop()
    return None


def run_foreground(engine=None, *, host='127.0.0.1', port=8000, open_browser=False):
    server = make_server(host, port, engine)
    done = threading.Event()
    opener = None
    if open_browser:
        def open_when_ready():
            deadline = time.monotonic() + 15
            while not done.is_set() and time.monotonic() < deadline:
                if server.started:
                    try:
                        import webbrowser
                        value = f'[{host}]' if ':' in host else host
                        webbrowser.open(f'http://{value}:{port}/')
                    except Exception:
                        pass  # Browser launch is optional; the server remains usable.
                    return
                done.wait(.025)
        opener = threading.Thread(target=open_when_ready, daemon=True, name='brandforge-browser')
        opener.start()
    try:
        server.run()
    finally:
        done.set()
        if opener is not None:
            opener.join(1)
