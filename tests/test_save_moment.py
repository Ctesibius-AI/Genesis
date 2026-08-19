"""Tests for save_moment — find_current_transcript + save_moment (CS4, offline/tmp_path).

All tests are offline: tmp_path ledgers, fixture transcripts, no network, no API key.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from genesys.ledger.store import read_all
from genesys.save_moment import (
    find_current_transcript,
    find_transcript_by_session_id,
    save_moment,
)
from genesys.wal.annotate import is_annotation


def _write_transcript(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")


def _fixture_transcript(tmp_path: Path) -> Path:
    p = tmp_path / "t.jsonl"
    records = [
        {"type": "user", "message": {"role": "user", "content": "hello from save_moment test"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "Sure, here's the answer."}
        ]}},
    ]
    _write_transcript(p, records)
    return p


# --------------------------------------------------------------------------- #
# find_current_transcript                                                       #
# --------------------------------------------------------------------------- #

def test_find_current_transcript_returns_newest(tmp_path: Path):
    proj = Path("/fake/project")
    encoded = str(proj).replace("/", "-")
    proj_dir = tmp_path / encoded
    proj_dir.mkdir(parents=True)
    a = proj_dir / "session-aaa.jsonl"
    a.write_text("{}", encoding="utf-8")
    time.sleep(0.02)  # ensure distinct mtime
    b = proj_dir / "session-bbb.jsonl"
    b.write_text("{}", encoding="utf-8")
    result = find_current_transcript(proj, projects_root=tmp_path)
    assert result == b


def test_find_current_transcript_returns_none_when_empty(tmp_path: Path):
    proj = Path("/fake/project")
    encoded = str(proj).replace("/", "-")
    (tmp_path / encoded).mkdir(parents=True)
    assert find_current_transcript(proj, projects_root=tmp_path) is None


def test_find_current_transcript_returns_none_when_no_dir(tmp_path: Path):
    proj = Path("/fake/project")
    assert find_current_transcript(proj, projects_root=tmp_path) is None


def test_find_current_transcript_newest_across_different_dirs(tmp_path: Path):
    """Regression: newest .jsonl must be found even if NOT under project_cwd-encoded dir."""
    # Create two project dirs
    proj_a = Path("/Users/principal/ProjectA")
    proj_b = Path("/Users/principal/ProjectB")
    encoded_a = str(proj_a).replace("/", "-")
    encoded_b = str(proj_b).replace("/", "-")

    dir_a = tmp_path / encoded_a
    dir_b = tmp_path / encoded_b
    dir_a.mkdir(parents=True)
    dir_b.mkdir(parents=True)

    # Create older transcript in dir_a
    old_file = dir_a / "old.jsonl"
    old_file.write_text("{}", encoding="utf-8")
    import os
    os.utime(old_file, (1000, 1000))  # mtime=1000

    # Create newer transcript in dir_b
    new_file = dir_b / "new.jsonl"
    new_file.write_text("{}", encoding="utf-8")
    os.utime(new_file, (2000, 2000))  # mtime=2000

    # Call with proj_a as project_cwd, but newest is in proj_b dir
    result = find_current_transcript(proj_a, projects_root=tmp_path)
    # Must return the global newest (new_file), not None or old_file
    assert result == new_file


def test_find_current_transcript_newest_by_mtime_deterministic(tmp_path: Path):
    """Verify mtime ordering is deterministic (no time.sleep)."""
    import os
    proj = Path("/fake/project")
    encoded = str(proj).replace("/", "-")
    proj_dir = tmp_path / encoded
    proj_dir.mkdir(parents=True)

    a = proj_dir / "a.jsonl"
    a.write_text("{}", encoding="utf-8")
    os.utime(a, (100, 100))

    b = proj_dir / "b.jsonl"
    b.write_text("{}", encoding="utf-8")
    os.utime(b, (200, 200))

    c = proj_dir / "c.jsonl"
    c.write_text("{}", encoding="utf-8")
    os.utime(c, (150, 150))

    result = find_current_transcript(proj, projects_root=tmp_path)
    assert result == b  # mtime=200 is newest


# --------------------------------------------------------------------------- #
# save_moment                                                                   #
# --------------------------------------------------------------------------- #

def test_save_moment_creates_salient_annotation(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    t = _fixture_transcript(tmp_path)
    note = "end of design session"
    entry = save_moment(
        data_root,
        transcript_path=t,
        session_id="sess-001",
        now="2026-08-19T10:00:00+00:00",
        note=note,
    )
    assert entry is not None
    assert is_annotation(entry) is True
    assert entry.enrichment.get("salience") is True
    assert entry.summary == note
    entries = read_all(data_root)
    assert len(entries) == 1


def test_save_moment_returns_none_when_empty_transcript(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    t = tmp_path / "empty.jsonl"
    t.write_text("", encoding="utf-8")
    result = save_moment(
        data_root,
        transcript_path=t,
        session_id="sess-002",
        now="2026-08-19T10:00:00+00:00",
        note="nothing",
    )
    assert result is None


# --------------------------------------------------------------------------- #
# CLI main() — the entry the /save command invokes via `python -m`             #
# --------------------------------------------------------------------------- #

def test_find_transcript_by_session_id_is_exact(tmp_path: Path):
    """The invoking session's transcript is found by its id — even when ANOTHER terminal's
    transcript is newer (the cross-terminal race that mtime-guessing would lose)."""
    import os
    mine_dir = tmp_path / "-Users-x-Ctesibius-Genesys"
    other_dir = tmp_path / "-Users-x-Ctesibius"
    mine_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)
    mine = mine_dir / "sess-mine.jsonl"
    mine.write_text("{}", encoding="utf-8")
    os.utime(mine, (1000, 1000))          # OLDER
    other = other_dir / "sess-other.jsonl"
    other.write_text("{}", encoding="utf-8")
    os.utime(other, (9000, 9000))          # NEWER (another active terminal)

    # By id → mine, exactly (not the newer other):
    assert find_transcript_by_session_id("sess-mine", projects_root=tmp_path) == mine
    # mtime-guess would wrongly pick the other terminal:
    assert find_current_transcript(Path("/x"), projects_root=tmp_path) == other


def test_find_transcript_by_session_id_none_cases(tmp_path: Path):
    assert find_transcript_by_session_id("", projects_root=tmp_path) is None
    assert find_transcript_by_session_id("nope", projects_root=tmp_path) is None


def test_cli_main_uses_exact_session_transcript(tmp_path: Path, monkeypatch, capsys):
    """`/save` passes --session-id ($CLAUDE_CODE_SESSION_ID); main() must capture THAT
    session's transcript, not the globally-newest one from another terminal."""
    from genesys.save_moment import main
    data_root = tmp_path / "data"; data_root.mkdir()
    projects = tmp_path / "projects"
    mine_dir = projects / "-mine"; mine_dir.mkdir(parents=True)
    other_dir = projects / "-other"; other_dir.mkdir(parents=True)
    # my session (older) with real content:
    mine = mine_dir / "sess-mine.jsonl"
    _write_transcript(mine, [
        {"type": "user", "message": {"role": "user", "content": "my session content"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "captured from MY session"}]}},
    ])
    import os
    os.utime(mine, (1000, 1000))
    # another terminal's transcript, NEWER, with different content:
    other = other_dir / "sess-other.jsonl"
    _write_transcript(other, [
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "the OTHER terminal — must NOT be captured"}]}},
    ])
    os.utime(other, (9000, 9000))
    monkeypatch.setattr("genesys.save_moment.find_transcript_by_session_id",
                        lambda sid, projects_root=None: find_transcript_by_session_id(sid, projects_root=projects))
    monkeypatch.setattr("sys.argv", [
        "genesys-save-moment", "--note", "exact save",
        "--data-root", str(data_root), "--session-id", "sess-mine",
        "--now", "2026-08-19T10:00:00+00:00", "--no-extract",
    ])
    main()
    out = capsys.readouterr().out
    assert "saved (salient)" in out
    entries = read_all(data_root)
    assert len(entries) == 1
    assert entries[0].links.session_id == "sess-mine"  # attributed to MY session


def test_cli_main_saves_and_prints(tmp_path: Path, monkeypatch, capsys):
    """The `/save` command runs `python -m genesys.save_moment` -> main(); it must actually
    parse argv, save a salient annotation, and print a confirmation (regression: a missing
    __main__ guard / silent main made the command a no-op)."""
    from genesys.save_moment import main

    data_root = tmp_path / "data"
    data_root.mkdir()
    t = _fixture_transcript(tmp_path)
    monkeypatch.setattr("sys.argv", [
        "genesys-save-moment",
        "--note", "cli save test",
        "--data-root", str(data_root),
        "--transcript", str(t),
        "--session-id", "sess-cli",
        "--now", "2026-08-19T10:00:00+00:00",
        "--no-extract",
    ])
    main()
    out = capsys.readouterr().out
    assert "saved (salient)" in out, f"CLI must confirm the save; got: {out!r}"
    entries = read_all(data_root)
    assert len(entries) == 1
    assert is_annotation(entries[0]) is True
    assert (entries[0].enrichment or {}).get("salience") is True


def test_cli_main_extract_runs_the_extraction_team(tmp_path: Path, monkeypatch, capsys):
    """Owner model: a save must trigger the extraction team IMMEDIATELY (default --extract).
    We monkeypatch the live run_once (offline can't hit anthropic/falkordb) and assert it's
    invoked with the same data_root/now the save used."""
    from genesys.save_moment import main
    data_root = tmp_path / "data"; data_root.mkdir()
    t = _fixture_transcript(tmp_path)
    calls = {}

    def fake_run_once(dr, *, now):
        calls["data_root"] = dr
        calls["now"] = now
        return ["EP-2026-08-19.0001"]

    monkeypatch.setattr("genesys.extraction.live.run_once", fake_run_once)
    monkeypatch.setattr("sys.argv", [
        "genesys-save-moment", "--note", "extract me",
        "--data-root", str(data_root), "--transcript", str(t),
        "--session-id", "sess-x", "--now", "2026-08-19T10:00:00+00:00",
        "--extract",
    ])
    main()
    out = capsys.readouterr().out
    assert "saved (salient)" in out
    assert calls, "extraction team (run_once) must run immediately after the save"
    assert str(calls["data_root"]) == str(data_root)
    assert calls["now"] == "2026-08-19T10:00:00+00:00"
    assert "extracted 1 item" in out


def test_cli_main_no_extract_only_queues(tmp_path: Path, monkeypatch, capsys):
    """--no-extract queues the save WITHOUT running extraction (the manual/deferred path)."""
    from genesys.save_moment import main
    data_root = tmp_path / "data"; data_root.mkdir()
    t = _fixture_transcript(tmp_path)
    called = {"n": 0}
    monkeypatch.setattr("genesys.extraction.live.run_once",
                        lambda dr, *, now: called.__setitem__("n", called["n"] + 1) or [])
    monkeypatch.setattr("sys.argv", [
        "genesys-save-moment", "--note", "queue only",
        "--data-root", str(data_root), "--transcript", str(t),
        "--session-id", "sess-y", "--now", "2026-08-19T10:00:00+00:00",
        "--no-extract",
    ])
    main()
    out = capsys.readouterr().out
    assert "saved (salient)" in out
    assert called["n"] == 0, "--no-extract must NOT run the extraction team"
