"""F-06.3: /save transcript selection is workspace-isolated — never crosses projects.

The bug: `find_current_transcript` used a GLOBAL newest-mtime across all ~/.claude/projects, so a
concurrent OTHER project's (newer) transcript could be ingested into this workspace's memory. Fix:
exact session-id match first; the mtime fallback is scoped to THIS project's dir only, fail-loud else.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from genesis.ledger.store import read_all
from genesis.save_moment import (
    _encoded_project_dir, find_current_transcript, find_transcript_by_session_id, main)


def _mk(dir_: Path, name: str) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    p = dir_ / name
    p.write_text("{}", encoding="utf-8")
    return p


def _mk_transcript(dir_: Path, name: str) -> Path:
    """A transcript with real capturable content (one user + one assistant turn)."""
    dir_.mkdir(parents=True, exist_ok=True)
    p = dir_ / name
    p.write_text("\n".join(json.dumps(r) for r in [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "content to capture"}]}},
    ]), encoding="utf-8")
    return p


def test_project_scoped_selection_ignores_a_newer_foreign_transcript(tmp_path):
    projects = tmp_path / "projects"
    proj_a = tmp_path / "projectA"
    proj_a.mkdir()
    _mk(_encoded_project_dir(proj_a, projects), "sessA.jsonl")          # ours
    time.sleep(0.01)
    _mk(projects / "-some-other-project", "sessB.jsonl")               # foreign, NEWER mtime
    got = find_current_transcript(proj_a, projects_root=projects)
    assert got is not None and got.name == "sessA.jsonl"               # never the newer foreign B


def test_fail_loud_when_this_project_has_no_transcript(tmp_path):
    projects = tmp_path / "projects"
    _mk(projects / "-other", "x.jsonl")                                # a neighbour has one; we don't
    proj_a = tmp_path / "projectA"
    proj_a.mkdir()
    assert find_current_transcript(proj_a, projects_root=projects) is None  # refuse; caller fails loud


def test_session_id_match_is_exact_across_projects(tmp_path):
    projects = tmp_path / "projects"
    _mk(projects / "-p1", "the-session.jsonl")
    _mk(projects / "-p2", "other.jsonl")
    assert find_transcript_by_session_id("the-session", projects_root=projects).name == "the-session.jsonl"
    assert find_transcript_by_session_id("missing", projects_root=projects) is None


# --------------------------------------------------------------------------- #
# main() layer-2 env-fallback + both fail-loud refuse branches (Athena F-06.3  #
# Condition 2: the safety net was inspection-only; these guard against a silent #
# refactor reopening the cross-project door).                                   #
# --------------------------------------------------------------------------- #

def _run_main(monkeypatch, projects, data_root, *, argv_extra):
    """Invoke main() with the project-scoped finders bound to `projects` (main() takes no
    projects_root, so we bind it exactly as the shipped code resolves ~/.claude/projects)."""
    monkeypatch.setattr(
        "genesis.save_moment.find_transcript_by_session_id",
        lambda sid, projects_root=None: find_transcript_by_session_id(sid, projects_root=projects))
    monkeypatch.setattr(
        "genesis.save_moment.find_current_transcript",
        lambda cwd, projects_root=None: find_current_transcript(cwd, projects_root=projects))
    monkeypatch.setattr("sys.argv", [
        "genesis-save-moment", "--data-root", str(data_root),
        "--now", "2026-08-19T10:00:00+00:00", "--no-extract", *argv_extra])
    main()


def test_main_layer2_env_fallback_uses_session_env(tmp_path, monkeypatch, capsys):
    """(i) No --session-id but CLAUDE_CODE_SESSION_ID set → the env id's exact transcript is used,
    BEFORE any mtime path (layer 2), and attributed to that session."""
    data_root = tmp_path / "data"; data_root.mkdir()
    projects = tmp_path / "projects"
    _mk_transcript(projects / "-mine", "sess-env.jsonl")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-env")
    _run_main(monkeypatch, projects, data_root, argv_extra=["--note", "env save"])  # no --session-id
    assert "saved" in capsys.readouterr().out
    entries = read_all(data_root)
    assert len(entries) == 1 and entries[0].links.session_id == "sess-env"


def test_main_fail_loud_when_no_session_and_empty_project_dir(tmp_path, monkeypatch, capsys):
    """(ii) No --session-id, no env, and THIS project has no transcript → 'cannot identify' and
    nothing is saved (never borrows a neighbour's newer transcript)."""
    data_root = tmp_path / "data"; data_root.mkdir()
    projects = tmp_path / "projects"
    _mk_transcript(projects / "-a-neighbour", "someone-else.jsonl")   # a neighbour has one; we don't
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    _run_main(monkeypatch, projects, data_root,
              argv_extra=["--project-cwd", "/no/such/project", "--note", "should refuse"])
    assert "cannot identify" in capsys.readouterr().out
    assert read_all(data_root) == []          # fail-loud: no save from a foreign transcript


def test_main_fail_loud_when_session_id_has_no_transcript(tmp_path, monkeypatch, capsys):
    """(iii) --session-id given but no transcript on disk for it → 'refusing to guess' and no save
    (never falls through to a global newest that could be a neighbour's)."""
    data_root = tmp_path / "data"; data_root.mkdir()
    projects = tmp_path / "projects"
    _mk_transcript(projects / "-other", "not-mine.jsonl")            # exists, but not my id
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    _run_main(monkeypatch, projects, data_root,
              argv_extra=["--session-id", "sess-ghost", "--note", "should refuse"])
    assert "refusing to guess" in capsys.readouterr().out
    assert read_all(data_root) == []          # fail-loud: no save
