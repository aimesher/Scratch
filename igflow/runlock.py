"""Only one Reel Studio may run per data folder; two copies would both publish the same post."""
from __future__ import annotations

import os
from pathlib import Path


class AlreadyRunning(RuntimeError):
    pass


class RunLock:
    def __init__(self, data_dir: Path):
        self.path = data_dir / ".running.lock"
        self.handle = None

    def acquire(self) -> "RunLock":
        self.handle = open(self.path, "a+")
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            self.handle = None
            raise AlreadyRunning(
                "Reel Studio is already running in another window (the normal or the online version). "
                "Close that window first, then start this one again.")
        return self

    def release(self) -> None:
        if self.handle:
            self.handle.close()  # closing the file releases the lock on every platform
            self.handle = None
