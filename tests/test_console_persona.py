"""Tests for the QA-console persona surface (spec §14 view 5, §10.1).

Four sub-surfaces, all read-only folds:
  (a) fact-conflict panel  — open ask-window C1/C2 conflicts to reconcile (§10.1a)
  (b) perceived-view panel — self-view vs perceived band/spread per anchor, PT-7 notice
                              on divergence, discuss/dispute affordances (§10.1b, D-RG-9a)
  (c) discussion-requests list — queued/served/closed (§10.2, PT-8 mirror)
  (d) release log          — opinion-ask/confirm/release/close; scope + close reason ONLY,
                             NEVER the opinion content (§14, Security-view posture)
"""

from __future__ import annotations

from pathlib import Path

from genesys.console.persona import (
    PerceivedAnchor,
    PersonaSurface,
    ReleaseEvent,
    persona_view,
)
from genesys.journal.journal import JournalEntry, append_journal
from genesys.persona.department import PerceptionDepartment
from genesys.persona.perceives import PerceivesEdge, PerceivesSample
from genesys.persona.release_machine import close_release, open_release


TS = "2026-08-17T10:00:00+00:00"


def test_empty_surface_is_honest_empty(tmp_path: Path):
    s = persona_view(tmp_path)
    assert isinstance(s, PersonaSurface)
    assert s.fact_conflicts == []
    assert s.perceived == []
    assert s.discussion_requests == []
    assert s.release_log == []


def test_perceived_panel_shows_both_records_and_alignment(tmp_path: Path):
    dept = PerceptionDepartment()
    edge = PerceivesEdge(to="Trait:rigor", band="high", spread="steady")
    edge.samples.append(PerceivesSample(anchor="Trait:rigor", episode="EP-1", valid_at=TS))
    dept.add(edge)
    # self-view has one stated sample for the same anchor → both records present → aligned
    s = persona_view(tmp_path, dept=dept, self_view={"Trait:rigor": 2})
    assert len(s.perceived) == 1
    a = s.perceived[0]
    assert isinstance(a, PerceivedAnchor)
    assert a.anchor == "Trait:rigor"
    assert a.self_samples == 2
    assert a.band == "high" and a.spread == "steady"
    assert a.perceived_strength == 1
    assert a.alignment == "aligned"
    assert a.notice is None  # aligned → no PT-7 notice


def test_perceived_panel_emits_pt7_notice_on_divergence(tmp_path: Path):
    dept = PerceptionDepartment()
    edge = PerceivesEdge(to="Trait:patience", band="low", spread="variable")
    edge.samples.append(PerceivesSample(anchor="Trait:patience", episode="EP-9", valid_at=TS))
    dept.add(edge)
    # no self-view sample → divergent → PT-7 notice, topic only
    s = persona_view(tmp_path, dept=dept, self_view={})
    a = s.perceived[0]
    assert a.self_samples == 0
    assert a.alignment == "divergent"
    assert a.notice is not None
    assert "Trait:patience" in a.notice  # topic named; the notice is a read, not a voicing


def test_perceived_panel_flags_dispute(tmp_path: Path):
    dept = PerceptionDepartment()
    edge = PerceivesEdge(to="Trait:rigor", band="high")
    edge.dispute = {"status": "disputed", "reason_ref": "R-1", "reason": "scrubbed"}
    dept.add(edge)
    s = persona_view(tmp_path, dept=dept, self_view={"Trait:rigor": 1})
    assert s.perceived[0].disputed is True


def test_perceived_panel_never_exposes_observation_text(tmp_path: Path):
    dept = PerceptionDepartment()
    edge = PerceivesEdge(to="Trait:rigor", band="high")
    edge.samples.append(PerceivesSample(anchor="Trait:rigor", episode="EP-1", valid_at=TS,
                                        observation="SECRET-OBSERVATION-TEXT"))
    dept.add(edge)
    s = persona_view(tmp_path, dept=dept, self_view={})
    # the panel is a records read (band/spread/strength), never the raw observation content
    a = s.perceived[0]
    for value in vars(a).values():
        assert "SECRET-OBSERVATION-TEXT" not in str(value)


def test_discussion_requests_folded_from_journal(tmp_path: Path):
    from genesys.persona.discussion import close, enqueue, serve

    rid = enqueue(tmp_path, ts=TS, anchor="Trait:rigor", origin="dashboard")
    serve(tmp_path, ts="2026-08-17T11:00:00+00:00", request_id=rid, anchor="Trait:rigor")
    rid2 = enqueue(tmp_path, ts="2026-08-17T12:00:00+00:00", anchor="Trait:patience")
    close(tmp_path, ts="2026-08-17T13:00:00+00:00", request_id=rid, anchor="Trait:rigor",
          reason="resolved-in-conversation")

    s = persona_view(tmp_path)
    by_id = {r.request_id: r for r in s.discussion_requests}
    assert by_id[rid].state == "served" or by_id[rid].state == "closed"
    assert by_id[rid].anchor == "Trait:rigor"
    assert by_id[rid2].state == "queued"


def test_release_log_shows_scope_and_close_reason_never_content(tmp_path: Path):
    dept = PerceptionDepartment()
    edge = PerceivesEdge(to="Trait:rigor", band="high")
    edge.samples.append(PerceivesSample(anchor="Trait:rigor", episode="EP-1", valid_at=TS,
                                        observation="PRIVATE-OPINION-CONTENT"))
    dept.add(edge)
    ctx = open_release(tmp_path, dept, asked_anchor="Trait:rigor", scope="topic",
                       ts=TS, opened_by="the principal")
    close_release(tmp_path, ctx, reason="subject-closed", ts="2026-08-17T10:30:00+00:00")

    s = persona_view(tmp_path)
    actions = [e.action for e in s.release_log]
    assert "opinion-ask" in actions
    assert "opinion-confirm" in actions
    assert "opinion-release" in actions
    assert "opinion-close" in actions
    rel = next(e for e in s.release_log if e.action == "opinion-release")
    assert isinstance(rel, ReleaseEvent)
    assert rel.scope == "topic"
    closed = next(e for e in s.release_log if e.action == "opinion-close")
    assert closed.close_reason == "subject-closed"
    # HARD FENCE (§14): the release log NEVER re-exposes opinion content
    for e in s.release_log:
        for value in vars(e).values():
            assert "PRIVATE-OPINION-CONTENT" not in str(value)
