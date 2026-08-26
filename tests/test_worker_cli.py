"""genesis-worker CLI — the `once` path reports failure loudly on a persistence failure.

harness-savefail: a failed store SAVE must NOT be reported as "processed N". The worker exits
nonzero with a loud message; the happy path still prints "processed N" and exits 0. Offline — run_once
is monkeypatched (no graph, no API).
"""
from __future__ import annotations

import genesis.extraction.worker_cli as worker_cli
from genesis.graph.client import PersistenceError


def test_cmd_once_fails_loud_and_nonzero_on_persistence_error(monkeypatch, capsys):
    def boom(data_root, *, now):
        raise PersistenceError("SAVE failed: disk full")

    monkeypatch.setattr("genesis.extraction.live.run_once", boom)
    rc = worker_cli.main(["--data-root", "/tmp/x", "once"])
    out = capsys.readouterr()
    assert rc == 2, "a persistence failure must be a nonzero exit, not success"
    assert "PERSISTENCE FAILURE" in out.err
    assert "processed" not in out.out, "'processed N' must never be the last word on a failed save"


def test_cmd_once_reports_processed_on_success(monkeypatch, capsys):
    monkeypatch.setattr("genesis.extraction.live.run_once",
                        lambda data_root, *, now: ["EP-1", "EP-2"])
    rc = worker_cli.main(["--data-root", "/tmp/x", "once"])
    out = capsys.readouterr()
    assert rc == 0
    assert "processed 2" in out.out
