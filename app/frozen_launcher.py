"""Entry point for an explicitly built native runtime; no package manager at launch."""
import argparse
import os
import threading
import urllib.request
import webbrowser


def main():
    parser = argparse.ArgumentParser(description='BrandForge local workspace')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Choose a port between 1024 and 65535')
    # Frozen bundles must not write customer data beside executable/resources.
    from modules.runtime_paths import data_dir
    os.environ['BRANDFORGE_DATA_DIR'] = data_dir()
    from modules.instance_lock import instance_lock
    with instance_lock(os.environ['BRANDFORGE_DATA_DIR']):
        import uvicorn
        from server import app
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=args.port,log_level='info'))
        stop=threading.Event()
        url=f'http://127.0.0.1:{args.port}'
        if not args.no_browser:
            def open_when_ready():
                for _ in range(120):
                    if stop.wait(.5):return
                    if not server.started:continue
                    try:
                        with urllib.request.urlopen(url+'/health',timeout=1) as response:
                            if response.status==200:
                                webbrowser.open(url)
                                return
                    except OSError:pass
            threading.Thread(target=open_when_ready,daemon=True).start()
        try:server.run()
        finally:stop.set()


if __name__ == '__main__':
    main()
