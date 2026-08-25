"""Projecting a LedgerEntry.links into typed episode edges (spec §4.6, D-SPINE-4)."""
from __future__ import annotations

from genesis.graph.engine import FakeGraph
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.linking.projection import (
    CAUSED_BY,
    CONTINUES,
    NEXT,
    PREV,
    REFERENCES,
    SAME_TOPIC,
    SUPERSEDES,
    project_entry_links,
)


def _entry(eid, ts, **links):
    return LedgerEntry(entry_id=eid, ts=ts, summary=f"sum {eid}",
                       provenance=Provenance(eid, "a", "b", ["the principal"]),
                       links=Links(session_id="s1", **links), extracted=Extracted.NO)


def test_projects_scalar_links_from_entry_as_source():
    g = FakeGraph()
    e = _entry("EP-2", "2026-08-17T10:05:00Z", prev="EP-1", next="EP-3", continues="EP-1")
    n = project_entry_links(e, g)
    edges = g.links_for("EP-2")
    assert ("EP-2", "EP-1", PREV) in edges
    assert ("EP-2", "EP-3", NEXT) in edges
    assert ("EP-2", "EP-1", CONTINUES) in edges
    assert n == 3


def test_projects_list_links_one_edge_per_target():
    g = FakeGraph()
    e = _entry("EP-5", "2026-08-17T11:00:00Z",
               references=["EP-1", "EP-2"], same_topic=["EP-3"],
               supersedes=["EP-4"], caused_by=["EP-0"])
    n = project_entry_links(e, g)
    edges = g.links_for("EP-5")
    assert ("EP-5", "EP-1", REFERENCES) in edges
    assert ("EP-5", "EP-2", REFERENCES) in edges
    assert ("EP-5", "EP-3", SAME_TOPIC) in edges
    assert ("EP-5", "EP-4", SUPERSEDES) in edges
    assert ("EP-5", "EP-0", CAUSED_BY) in edges
    assert n == 5


def test_empty_links_project_nothing():
    g = FakeGraph()
    e = _entry("EP-1", "2026-08-17T10:00:00Z")  # only session_id set
    n = project_entry_links(e, g)
    assert g.links_for("EP-1") == []
    assert n == 0  # session_id is the saga container, not a typed edge


def test_session_id_is_not_projected():
    g = FakeGraph()
    e = _entry("EP-2", "2026-08-17T10:05:00Z", prev="EP-1")
    project_entry_links(e, g)
    labels = {label for _, _, label in g.links_for("EP-2")}
    assert "s1" not in labels  # session_id never becomes an edge target/label
    assert labels == {PREV}


def test_projector_does_not_mutate_ledger_entry():
    g = FakeGraph()
    e = _entry("EP-2", "2026-08-17T10:05:00Z", prev="EP-1", references=["EP-0"])
    before = (e.links.prev, list(e.links.references))
    project_entry_links(e, g)
    assert (e.links.prev, list(e.links.references)) == before  # read-only over the ledger
