"""One-at-a-time lock for scheduled tasks.

Several tasks can fire at the same minute (three classes at 6:50 PM). Each is its own process,
and they all drive the same WhatsApp window, so they must take turns: each holds this lock
(a byte-range lock on a file, released by Windows even if the process dies) while it runs.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator


@contextmanager
def one_at_a_time(path: Path, wait: float = 300.0, sleep: Callable[[float], None] = time.sleep,
                  clock: Callable[[], float] = time.monotonic) -> Iterator[bool]:
    """Yields True once the lock is held, or False if it couldn't be had within `wait` seconds
    (the caller then runs anyway: a late send beats no send)."""
    try:
        import msvcrt
    except ImportError:                                   # not Windows: nothing to share
        yield True
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+b")
    held, deadline = False, clock() + wait
    try:
        while True:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                held = True
                break
            except OSError:
                if clock() >= deadline:
                    break
                sleep(1.0)
        yield held
    finally:
        if held:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        f.close()
