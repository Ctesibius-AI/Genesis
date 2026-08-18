from __future__ import annotations

from genesys.tasks.cli import main
from genesys.tasks.department import tasks_department
from genesys.tasks.emit import record_created, record_done, record_due_moved


def test_emitters_roundtrip_through_department(tmp_path):
    tid = record_created(tmp_path, ts="2026-08-17T10:00:00Z", source_episode="EP-1",
                         title="send INV-042", kind="commitment", due="2026-08-31")
    assert tid == "TS-2026-08-17.0000"
    record_due_moved(tmp_path, ts="2026-08-18T10:00:00Z", task_id=tid, due="2026-08-20",
                     source_episode="EP-2")
    views = tasks_department(tmp_path, now="2026-08-17T00:00:00Z")
    assert views[0].state.task_id == tid and views[0].state.due == "2026-08-20"
    record_done(tmp_path, ts="2026-08-19T10:00:00Z", task_id=tid, source_episode="EP-3")
    assert tasks_department(tmp_path, now="2026-08-17T00:00:00Z") == []  # terminal dropped


def test_cli_create_then_list(tmp_path, capsys):
    rc = main(["create", "--data-root", str(tmp_path), "--title", "ship it",
               "--due", "2026-08-18", "--now", "2026-08-17T09:00:00Z", "--episode", "EP-1"])
    assert rc == 0
    tid = capsys.readouterr().out.strip()
    assert tid.startswith("TS-2026-08-17.")

    rc = main(["list", "--data-root", str(tmp_path), "--now", "2026-08-17T09:00:00Z"])
    assert rc == 0
    out = capsys.readouterr().out
    assert tid in out and "ship it" in out


def test_cli_done_removes_from_active_list(tmp_path, capsys):
    main(["create", "--data-root", str(tmp_path), "--title", "x", "--due", "2026-08-18",
          "--now", "2026-08-17T09:00:00Z", "--episode", "EP-1"])
    tid = capsys.readouterr().out.strip()
    main(["done", "--data-root", str(tmp_path), "--task-id", tid,
          "--now", "2026-08-17T10:00:00Z", "--episode", "EP-2"])
    capsys.readouterr()
    main(["list", "--data-root", str(tmp_path), "--now", "2026-08-17T11:00:00Z"])
    assert tid not in capsys.readouterr().out
