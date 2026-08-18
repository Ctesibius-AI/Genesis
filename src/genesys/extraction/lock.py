"""Single-instance drain lock (spec §4.14, D-SUP-7).

Exactly one drain writes the spine at a time (single durable writer). A second concurrent drain
fails loudly (journal `lock-violation`) rather than running two writers. A wedged lock from a
crashed drain is cleared by the P1 `doctor` restart path re-queuing in-progress work; the lockfile
itself is best-effort and removed on normal exit.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from genesys.journal.journal import JournalEntry, append_journal


class LockHeld(RuntimeError):
    pass


@contextlib.contextmanager
def single_instance(data_root: Path, *, ts: str):
    lock = Path(data_root) / ".drain.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        append_journal(data_root, JournalEntry(ts=ts, action="lock-violation", scope="drain",
                       reason="a drain is already running", author="supervisor"))
        raise LockHeld("a drain is already holding the single-instance lock")
    os.close(fd)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()
