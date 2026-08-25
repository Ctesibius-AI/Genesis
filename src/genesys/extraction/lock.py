"""Single-instance drain lock (spec §4.14, D-SUP-7; D-GCW-2/-3, AC-X1).

Exactly one drain writes the spine at a time (single durable writer). A second concurrent drain
fails loudly (journal `lock-violation`) rather than running two writers. The lockfile records the
owner's **PID + start-time** at creation; a lock whose owner is **dead** (PID-reuse-guarded by the
start-time) is cleared before draining, so a SIGKILL/crash never permanently wedges ingestion
(AC-X1). Self-healing: `single_instance` clears a dead-owner lock and retries once; a live owner's
lock still raises `LockHeld`.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
from pathlib import Path

from genesys.journal.journal import JournalEntry, append_journal

LOCK_NAME = ".drain.lock"


class LockHeld(RuntimeError):
    pass


def _proc_start_time(pid: int) -> str | None:
    """Best-effort process start-time token for the PID-reuse guard.

    Linux: field 22 of ``/proc/<pid>/stat`` (start time in clock ticks). BSD/macOS:
    ``ps -o lstart=``. Returns None when neither is available — the guard then falls back to
    liveness-only (a crashed PID is still cleared; only reuse within a live PID is unguarded).
    """
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.exists():  # pragma: no cover - Linux only; CI/dev here is macOS
        try:
            fields = proc_stat.read_text().rsplit(") ", 1)[-1].split()
            return fields[19]  # starttime is field 22 (index 19 after "comm) ")
        except (OSError, IndexError):
            return None
    try:
        out = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip() or None
    except (subprocess.CalledProcessError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # alive but owned by another user
        return True
    return True


def _owner_alive(pid: int, start: str | None) -> bool:
    """True iff `pid` is alive AND (start unknown, or its current start-time matches `start`).

    A dead PID → False (clear it). A live PID whose start-time no longer matches the recorded
    one → the recorded owner is dead and the PID was reused → False (clear it).
    """
    if not _pid_alive(pid):
        return False
    if start is None:
        return True
    now_start = _proc_start_time(pid)
    if now_start is None:
        return True  # cannot re-read start-time; be conservative, treat live PID as the owner
    return now_start == start


def _read_lock(lock: Path) -> dict | None:
    try:
        raw = lock.read_text(encoding="utf-8")
    except (OSError, IOError):
        return None
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}  # present but unparsable (e.g. legacy empty lock) — no owner info
    return obj if isinstance(obj, dict) else {}


def clear_if_dead(data_root: Path, *, ts: str = "") -> bool:
    """Clear a `.drain.lock` whose recorded owner is dead (PID-reuse-guarded). Returns cleared?

    Called at drain-start and by the P1 doctor. A missing lock, or one held by a live owner, is
    left untouched. A legacy/empty lock with no PID is treated as stale (nothing else writes it)
    and cleared, so a pre-existing empty lock never wedges ingestion forever.
    """
    lock = Path(data_root) / LOCK_NAME
    if not lock.exists():
        return False
    info = _read_lock(lock)
    pid = info.get("pid") if isinstance(info, dict) else None
    if isinstance(pid, int) and _owner_alive(pid, info.get("start") if info else None):
        return False  # live owner — do not clear
    with contextlib.suppress(FileNotFoundError):
        lock.unlink()
    append_journal(data_root, JournalEntry(ts=ts, action="stale-lock-cleared", scope="drain",
                   reason=f"cleared dead-owner lock (pid={pid})", author="supervisor"))
    return True


@contextlib.contextmanager
def single_instance(data_root: Path, *, ts: str):
    lock = Path(data_root) / LOCK_NAME
    lock.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"pid": os.getpid(), "start": _proc_start_time(os.getpid()), "ts": ts})
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # Self-heal: a dead-owner lock is cleared, then we retry once. A live owner is not
        # cleared, so a genuine concurrent drain still fails loudly (AC-D2 / D-SUP-7).
        if clear_if_dead(data_root, ts=ts):
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        else:
            append_journal(data_root, JournalEntry(ts=ts, action="lock-violation", scope="drain",
                           reason="a drain is already running", author="supervisor"))
            raise LockHeld("a drain is already holding the single-instance lock")
    with os.fdopen(fd, "w") as fh:
        fh.write(payload)  # PID + start-time INTO the lock (AC-X1)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()
