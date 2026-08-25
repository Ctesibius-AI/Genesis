"""Integration wiring tests: link_episode recording, save structural linking, drain semantic linking (spec §4.6, DR-09, DR-20)."""
from __future__ import annotations

from genesis.graph.engine import FakeGraph
from genesis.ledger.store import read_all
from genesis.linking.relatedness import FakeRelatednessScorer


def test_fakegraph_link_episode_records():
    g = FakeGraph()
    g.link_episode("EP-1", "EP-2", "NEXT_EPISODE")
    assert ("EP-1", "EP-2", "NEXT_EPISODE") in g.links_for("EP-1")


def test_save_derives_prev_via_structural_linker(tmp_path):
    from genesis.save import fast_path_save
    fast_path_save(tmp_path, raw_span="a", summary="first", session_id="s1",
                   speakers=["the principal"], span_start="0", span_end="1",
                   ts="2026-08-17T10:00:00Z")
    second = fast_path_save(tmp_path, raw_span="b", summary="second", session_id="s1",
                            speakers=["the principal"], span_start="1", span_end="2",
                            ts="2026-08-17T10:05:00Z")
    assert second.links.prev is not None  # derived, not passed
    ids = {e.entry_id: e for e in read_all(tmp_path)}
    assert ids[second.links.prev].links.next == second.entry_id


def test_save_respects_explicit_prev_override(tmp_path):
    """When caller passes prev explicitly, structural linker must NOT overwrite it."""
    from genesis.save import fast_path_save
    fast_path_save(tmp_path, raw_span="a", summary="first", session_id="s1",
                   speakers=["the principal"], span_start="0", span_end="1",
                   ts="2026-08-17T10:00:00Z")
    second = fast_path_save(tmp_path, raw_span="b", summary="second", session_id="s1",
                            speakers=["the principal"], span_start="1", span_end="2",
                            ts="2026-08-17T10:05:00Z", prev="EXPLICIT-PREV")
    assert second.links.prev == "EXPLICIT-PREV"  # kept as-is


def test_drain_applies_semantic_links(tmp_path):
    # minimal drain smoke: two saved+queued entries, a scorer that links them
    from genesis.save import fast_path_save
    from genesis.extraction.drain import drain_once
    from genesis.workers.backend import FakeLLMBackend

    e1 = fast_path_save(tmp_path, raw_span="GRAFIX invoicing detail", summary="GRAFIX invoicing",
                        session_id="s1", speakers=["the principal"], span_start="0", span_end="1",
                        ts="2026-08-17T10:00:00Z")
    e2 = fast_path_save(tmp_path, raw_span="GRAFIX PHR008 detail", summary="GRAFIX PHR008",
                        session_id="s1", speakers=["the principal"], span_start="1", span_end="2",
                        ts="2026-08-17T10:05:00Z")
    scorer = FakeRelatednessScorer()
    scorer.set("GRAFIX invoicing", "GRAFIX PHR008", 0.9)

    drain_once(tmp_path, FakeGraph(), FakeLLMBackend('{"verdict": "PASS", "flags": []}'),
               ts="2026-08-17T10:06:00Z", scorer=scorer)

    ids = {e.entry_id: e for e in read_all(tmp_path)}
    assert e1.entry_id in ids[e2.entry_id].links.same_topic


def test_drain_records_supersession_and_projects_edges(tmp_path):
    from genesis.save import fast_path_save
    from genesis.extraction.drain import drain_once
    from genesis.workers.backend import FakeLLMBackend
    from genesis.linking.decision import SupersessionDecision
    from genesis.graph.engine import GraphEdge

    prior = fast_path_save(tmp_path, raw_span="old plan", summary="old plan",
                           session_id="s1", speakers=["the principal"], span_start="0", span_end="1",
                           ts="2026-08-17T10:00:00Z")
    cur = fast_path_save(tmp_path, raw_span="new plan supersedes it", summary="new plan",
                         session_id="s1", speakers=["the principal"], span_start="1", span_end="2",
                         ts="2026-08-17T10:05:00Z")

    g = FakeGraph()
    g.seed(GraphEdge(edge_id="edge-old", fact="the old plan", episodes=[prior.entry_id]))
    decision = SupersessionDecision(superseded_entry_ids=[prior.entry_id],
                                    superseded_edge_ids=["edge-old"],
                                    caused_by=[prior.entry_id])

    drain_once(tmp_path, g, FakeLLMBackend('{"verdict": "PASS", "flags": []}'),
               ts="2026-08-17T10:06:00Z",
               supersessions={cur.entry_id: decision}, project=True)

    ids = {e.entry_id: e for e in read_all(tmp_path)}
    # ledger truth: supersedes + caused_by recorded on the current entry
    assert ids[cur.entry_id].links.supersedes == [prior.entry_id]
    assert ids[cur.entry_id].links.caused_by == [prior.entry_id]
    # graph projection: superseded_by written, and typed edges emitted from the entry
    assert g.get("edge-old").superseded_by == cur.entry_id
    labels = {label for _, _, label in g.links_for(cur.entry_id)}
    assert "SUPERSEDES" in labels
    assert "CAUSED_BY" in labels
    assert "PREV_ENTRY" in labels  # structural prev also projected


def test_drain_without_project_or_supersession_is_unchanged(tmp_path):
    # existing callers pass neither: no typed edges, no supersession writes, still drains.
    from genesis.save import fast_path_save
    from genesis.extraction.drain import drain_once
    from genesis.workers.backend import FakeLLMBackend

    e = fast_path_save(tmp_path, raw_span="solo", summary="solo",
                       session_id="s1", speakers=["the principal"], span_start="0", span_end="1",
                       ts="2026-08-17T10:00:00Z")
    g = FakeGraph()
    processed = drain_once(tmp_path, g, FakeLLMBackend('{"verdict": "PASS", "flags": []}'),
                           ts="2026-08-17T10:06:00Z")
    assert e.entry_id in processed
    assert g.links_for(e.entry_id) == []  # projection off by default
