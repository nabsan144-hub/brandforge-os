"""Cross-process native lock for one customer-data directory."""
from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def instance_lock(directory):
    folder=Path(directory);folder.mkdir(parents=True,exist_ok=True)
    path=folder/'desktop-instance.lock'
    if path.is_symlink(): raise RuntimeError('Instance lock cannot be a symbolic link')
    handle=path.open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            if path.stat().st_size==0: handle.write(b'0');handle.flush()
            handle.seek(0)
            try: msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as exc: raise RuntimeError('BrandForge is already running for this data directory.') from exc
        else:
            import fcntl
            try: fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc: raise RuntimeError('BrandForge is already running for this data directory.') from exc
        yield
    finally:
        handle.close()
