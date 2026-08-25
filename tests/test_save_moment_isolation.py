"""F-06.3: /save transcript selection is workspace-isolated — never crosses projects.

The bug: `find_current_transcript` used a GLOBAL newest-mtime across all ~/.claude/projects, so a
concurrent OTHER project's (newer) transcript could be ingested into this workspace's memory. Fix:
exact session-id match first; the mtime fallback is scoped to THIS project's dir only, fail-loud else.
"""
from __future__ import annotations

import time
from pathlib import Path

from genesis.save_moment import (
    _encoded_project_dir, find_current_transcript, find_transcript_by_session_id)


def _mk(dir_: Path, name: str) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    p = dir_ / name
    p.write_text("{}", encoding="utf-8")
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
