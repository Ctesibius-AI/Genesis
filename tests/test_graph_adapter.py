from __future__ import annotations

import pytest

from genesis.graph.adapter import GraphitiEngine, to_graph_edge
from genesis.graph.client import ClientEdge, CommitMarker, FakeGraphitiClient
from genesis.graph.engine import Verdict


def _clock(seq):
    it = iter(seq)
    return lambda: next(it)


def test_to_graph_edge_maps_native_and_attributes():
    ce = ClientEdge(
        uuid="e1", fact="uses Y", episodes=["ep-1"], valid_at="v", expired_at="x",
        attributes={"author": "stated", "verdict": "confirmed", "contested": True,
                    "evidence_against": ["ep-2"], "superseded_by": "e9", "class": "C3"},
    )
    ge = to_graph_edge(ce)
    assert ge.edge_id == "e1" and ge.fact == "uses Y" and ge.episodes == ["ep-1"]
    assert ge.valid_at == "v" and ge.expired_at == "x"
    assert ge.author == "stated" and ge.verdict == Verdict.CONFIRMED and ge.contested is True
    assert ge.evidence_against == ["ep-2"] and ge.superseded_by == "e9" and ge.class_ == "C3"


def test_to_graph_edge_defaults_for_bare_edge():
    ge = to_graph_edge(ClientEdge(uuid="e2", fact="f", episodes=["ep-0"]))
    assert ge.author == "inferred" and ge.verdict == Verdict.PROVISIONAL
    assert ge.contested is False and ge.evidence_against == [] and ge.class_ is None


def test_add_episode_returns_created_only_and_records_window():
    c = FakeGraphitiClient()
    c.seed(ClientEdge(uuid="e-old", fact="uses X", episodes=["ep-0"]))
    new = ClientEdge(uuid="e-new", fact="uses Y", episodes=[])
    c.script_episode("ep-1", creates=[new], expires=["e-old"], at="2026-08-17T10:00:00Z")
    eng = GraphitiEngine(c, marker=CommitMarker(),
                         clock=_clock(["2026-08-17T09:59:59Z", "2026-08-17T10:00:01Z"]))

    res = eng.add_episode("ep-1", "he now uses Y")

    assert [e.edge_id for e in res.created] == ["e-new"]  # F-11: created only
    assert eng.window_for("ep-1") == ("2026-08-17T09:59:59Z", "2026-08-17T10:00:01Z")


def test_created_in_episode():
    c = FakeGraphitiClient()
    new = ClientEdge(uuid="e-new", fact="uses Y", episodes=[])
    c.script_episode("ep-1", creates=[new], at="t")
    eng = GraphitiEngine(c, clock=_clock(["s", "e"]))
    eng.add_episode("ep-1", "body")
    assert [e.edge_id for e in eng.created_in_episode("ep-1")] == ["e-new"]


def test_clock_required_when_not_injected():
    eng = GraphitiEngine(FakeGraphitiClient())
    with pytest.raises(RuntimeError):
        eng.add_episode("ep-1", "body")


def test_invalidated_in_window_reads_expired_edges():
    from genesis.graph.adapter import GraphitiEngine
    from genesis.graph.client import ClientEdge, FakeGraphitiClient

    c = FakeGraphitiClient()
    c.seed(ClientEdge(uuid="e-old", fact="uses X", episodes=["ep-0"]))
    new = ClientEdge(uuid="e-new", fact="uses Y", episodes=[])
    c.script_episode("ep-1", creates=[new], expires=["e-old"], at="2026-08-17T10:00:00Z")
    eng = GraphitiEngine(c, clock=_clock(["2026-08-17T09:59:59Z", "2026-08-17T10:00:01Z"]))
    eng.add_episode("ep-1", "body")

    start, end = eng.window_for("ep-1")
    inv = eng.invalidated_in_window(start, end)
    assert [e.edge_id for e in inv] == ["e-old"]
    assert inv[0].expired_at == "2026-08-17T10:00:00Z"


def test_get_returns_translated_edge():
    from genesis.graph.adapter import GraphitiEngine
    from genesis.graph.client import ClientEdge, FakeGraphitiClient

    c = FakeGraphitiClient()
    c.seed(ClientEdge(uuid="e1", fact="f", episodes=["ep-0"], attributes={"verdict": "quarantined"}))
    eng = GraphitiEngine(c)
    from genesis.graph.engine import Verdict
    assert eng.get("e1").verdict == Verdict.QUARANTINED


def _engine_with(edge):
    from genesis.graph.adapter import GraphitiEngine
    from genesis.graph.client import FakeGraphitiClient
    c = FakeGraphitiClient()
    c.seed(edge)
    return GraphitiEngine(c), c


def test_reopen_clears_invalidation_and_marks_contested():
    from genesis.graph.client import ClientEdge
    eng, c = _engine_with(ClientEdge(uuid="e1", fact="f", episodes=["ep-0"],
                                     invalid_at="t", expired_at="t"))
    eng.reopen("e1", "ep-9")
    e = c.get_edge("e1")
    assert e.invalid_at is None and e.expired_at is None
    assert e.attributes["contested"] is True
    assert e.attributes["evidence_against"] == ["ep-9"]
    # idempotent on the same episode
    eng.reopen("e1", "ep-9")
    assert c.get_edge("e1").attributes["evidence_against"] == ["ep-9"]


def test_set_verdict_write_superseded_write_fact():
    from genesis.graph.client import ClientEdge
    from genesis.graph.engine import Verdict
    eng, c = _engine_with(ClientEdge(uuid="e1", fact="old", episodes=["ep-0"]))
    eng.set_verdict("e1", Verdict.CONFIRMED)
    eng.write_superseded_by("e1", "e2")
    eng.write_fact("e1", "new fact")
    e = c.get_edge("e1")
    assert e.attributes["verdict"] == "confirmed"
    assert e.attributes["superseded_by"] == "e2"
    assert e.fact == "new fact"
    # round-trips through the engine's own reader
    assert eng.get("e1").verdict == Verdict.CONFIRMED


def test_link_episode_records_typed_edge():
    """link_episode projects a Genesis-side typed edge onto the client (spec §4.6, D-SPINE-4)."""
    eng, c = _engine_with(ClientEdge(uuid="e1", fact="f", episodes=["ep-0"]))
    eng.link_episode("EP-1", "EP-2", "NEXT_EPISODE")
    assert ("EP-1", "EP-2", "NEXT_EPISODE") in c._typed


# --- graph-harness T2: GraphitiEngine.close() delegates to the client's shutdown/persist --- #

class _ClosableClient:
    def __init__(self, *, boom: bool = False) -> None:
        self.closed = 0
        self._boom = boom

    def close(self) -> None:
        self.closed += 1
        if self._boom:
            raise RuntimeError("driver shutdown failed")


def test_close_delegates_to_client_close():
    c = _ClosableClient()
    GraphitiEngine(c, clock=lambda: "t").close()
    assert c.closed == 1  # the real client SAVEs the RDB + stops its loop here


def test_close_is_noop_when_client_has_no_close():
    # FakeGraphitiClient exposes no close(); engine.close() must be a safe no-op, never AttributeError.
    eng, _ = _engine_with(ClientEdge(uuid="e1", fact="f", episodes=["ep-0"]))
    eng.close()  # no raise


def test_close_swallows_and_logs_client_error():
    c = _ClosableClient(boom=True)
    GraphitiEngine(c, clock=lambda: "t").close()  # best-effort: logs, does not raise
    assert c.closed == 1
