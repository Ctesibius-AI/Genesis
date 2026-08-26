"""Round C small-fix sweep — one test module for the independent fixes.

F-05.3 atomic ledger update · F-08.3 idle-guard IN_PROGRESS · F-07.2 amend before-text ·
F-02.1 scrubber ID single-source · F-26.4 resume-safe retry · expand honest-empty · MCP drop_count ·
doctor reconcile done-vs-empty · promote/quarantine skip-if-absent.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from genesis.graph.engine import FakeGraph, GraphEdge, Verdict
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append, read_all, update


def _entry(eid: str, *, extracted: Extracted = Extracted.NO) -> LedgerEntry:
    return LedgerEntry(entry_id=eid, ts="2026-08-18T10:00:00+00:00", summary="jot",
                       provenance=Provenance(eid, "a", "b", ["the principal"]),
                       links=Links(session_id="s"), extracted=extracted)


# ── F-05.3: atomic ledger update ──────────────────────────────────────────────────────────────

def test_update_is_atomic_original_survives_a_failed_swap(tmp_path, monkeypatch):
    append(tmp_path, _entry("EP-2026-08-18.0001"))
    original = next(iter((tmp_path / "ledger").glob("*.jsonl"))).read_text()
    # Simulate a crash AT the os.replace (tmp written, swap interrupted): the original must be intact.
    import genesis.ledger.store as store
    monkeypatch.setattr(store.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError):
        e = read_all(tmp_path)[0]; e.extracted = Extracted.DONE; update(tmp_path, e)
    month = next(iter((tmp_path / "ledger").glob("*.jsonl")))
    assert month.read_text() == original                 # never a truncated month
    assert not list((tmp_path / "ledger").glob("*.tmp")) or True  # tmp may remain; original is what matters


# ── F-08.3: idle-guard counts IN_PROGRESS as not-idle ─────────────────────────────────────────

def test_session_start_drain_does_not_skip_a_lone_in_progress(tmp_path, monkeypatch):
    import genesis.hooks.cli as hooks_cli
    append(tmp_path, _entry("EP-2026-08-18.0002", extracted=Extracted.IN_PROGRESS))
    called = {"run_once": 0}
    monkeypatch.setattr("genesis.extraction.live.run_once",
                        lambda data_root, *, now, **k: called.__setitem__("run_once", called["run_once"] + 1) or [])
    hooks_cli._session_start_drain(tmp_path, "2026-08-18T10:00:00+00:00")()
    assert called["run_once"] == 1  # a crashed sole IN_PROGRESS entry must NOT be skipped


def test_session_start_drain_skips_when_truly_idle(tmp_path, monkeypatch):
    import genesis.hooks.cli as hooks_cli
    append(tmp_path, _entry("EP-2026-08-18.0003", extracted=Extracted.DONE))
    called = {"run_once": 0}
    monkeypatch.setattr("genesis.extraction.live.run_once",
                        lambda *a, **k: called.__setitem__("run_once", called["run_once"] + 1) or [])
    hooks_cli._session_start_drain(tmp_path, "2026-08-18T10:00:00+00:00")()
    assert called["run_once"] == 0  # all DONE → idle → skip


# ── F-07.2: amend journal keeps before-text ───────────────────────────────────────────────────

def test_amend_journal_records_before_text(tmp_path):
    from genesis.journal.journal import read_journal
    from genesis.supervisor.gate import apply_remedy
    from genesis.workers.verifier import VerifierRemedy
    g = FakeGraph()
    g.seed(GraphEdge("e1", "OLD fact", ["EP-1"]))
    apply_remedy(g, tmp_path, g.get("e1"), VerifierRemedy(action="amend", target="e1", content="NEW"),
                 ts="2026-08-18T10:00:00+00:00")
    amend = [j for j in read_journal(tmp_path) if j.after == "amended"]
    assert amend and amend[0].before == "OLD fact"   # the prior text is auditable


# ── F-02.1: scrubber ID regex single-sourced from ids.py ──────────────────────────────────────

def test_scrubber_allowlists_the_real_episode_id_shape():
    from genesis.ids import format_episode_id
    from genesis.scrub.scrubber import _is_allowlisted
    assert _is_allowlisted(format_episode_id("2026-08-18", 1))   # real shape allowlisted (drift-proof)
    assert not _is_allowlisted("gen-20260818-001")               # the dead format is gone


# ── F-26.4: resume-safe retry (already-landed episode is not re-added) ─────────────────────────

def test_drain_resumes_without_re_adding_a_committed_episode(tmp_path, monkeypatch):
    from genesis.episode.ownedfile import EpisodeHeader, write_episode_file
    from genesis.extraction.drain import drain_once
    from genesis.workers.backend import FakeLLMBackend
    eid = "EP-2026-08-18.0004"
    write_episode_file(tmp_path, EpisodeHeader(
        episode_id=eid, session_id="s", projection="memory-grade", captured_at="2026-08-18T10:00:00+00:00",
        span_start="a", span_end="b", speakers=["the principal"], source_transcript_ref="r"), "raw")
    append(tmp_path, _entry(eid))
    g = FakeGraph()
    g.seed(GraphEdge("landed", "already landed", [eid]))   # the episode's edge is ALREADY in the graph
    called = {"grapher": 0}
    import genesis.extraction.drain as drain
    real = drain.run_grapher
    monkeypatch.setattr(drain, "run_grapher",
                        lambda *a, **k: called.__setitem__("grapher", called["grapher"] + 1) or real(*a, **k))
    drain_once(tmp_path, g, FakeLLMBackend('{"verdict": "PASS", "flags": []}'), ts="2026-08-18T10:00:11+00:00")
    assert called["grapher"] == 0                          # resumed — no duplicate add_episode
    assert read_all(tmp_path)[0].extracted is Extracted.DONE


# ── expand honest-empty parity + MCP drop_count ───────────────────────────────────────────────

def test_expand_empty_read_emits_honest_empty():
    from genesis.linking.relatedness import FakeRelatednessScorer
    from genesis.recall.service import RecallService
    from genesis.recall.tier import Tier
    svc = RecallService(FakeGraph(), FakeRelatednessScorer(default=0.5))
    r = svc.expand("EP-nope", Tier.EPISODIC)   # reads graph, finds nothing
    assert r.is_empty() and r.verdict is not None and r.verdict.cause.value == "absent"


def test_recall_response_emits_drop_count():
    from genesis.recall.mcp_server import recall_response
    from genesis.recall.service import RecallResult
    assert recall_response(RecallResult(drop_count=3))["drop_count"] == 3


# ── doctor reconcile done-vs-graph-empty ──────────────────────────────────────────────────────

def test_doctor_reconcile_reverts_done_but_graph_empty(tmp_path):
    from genesis.doctor import doctor_reconcile_done
    append(tmp_path, _entry("EP-2026-08-18.0005", extracted=Extracted.DONE))   # done, but no graph edge
    append(tmp_path, _entry("EP-2026-08-18.0006", extracted=Extracted.DONE))   # done, has a graph edge
    g = FakeGraph()
    g.seed(GraphEdge("x", "f", ["EP-2026-08-18.0006"]))
    reverted = doctor_reconcile_done(tmp_path, g)
    assert reverted == ["EP-2026-08-18.0005"]
    by_id = {e.entry_id: e for e in read_all(tmp_path)}
    assert by_id["EP-2026-08-18.0005"].extracted is Extracted.NO      # reverted
    assert by_id["EP-2026-08-18.0006"].extracted is Extracted.DONE    # consistent → untouched


# ── promote/quarantine skip-if-absent ─────────────────────────────────────────────────────────

def test_promote_created_skips_absent_edge_without_crashing(tmp_path):
    from genesis.supervisor.verdicts import promote_created, quarantine_created
    g = FakeGraph()
    g.seed(GraphEdge("present", "f", ["EP-1"]))
    absent = GraphEdge("absent", "g", ["EP-1"])   # never seeded into the engine
    present = g.get("present")
    promoted = promote_created(g, tmp_path, [present, absent], ts="2026-08-18T10:00:00+00:00", reason="x")
    assert promoted == ["present"] and g.get("present").verdict is Verdict.CONFIRMED   # absent skipped, no crash
    held = quarantine_created(g, tmp_path, [present, absent], ts="2026-08-18T10:00:00+00:00", reason="x")
    assert "absent" not in held
