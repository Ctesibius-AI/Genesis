"""BT-3 / gate G-α — AC-R1 (red-line) + AC-DROP1: the CLOSED allow-list is the leak-guard.

AC-R1 literalism: the test MUST plant BOTH a `perceives` edge AND an unclassified edge and assert
NEITHER returns — while a genuinely typed memory edge does. This proves the fail-closed allow-list
on the offline post-fetch path (and the search path); the live SearchFilters query path is the
primary guard (graphiti absent offline, `pragma: no cover`). AC-DROP1: every exclusion is counted.
"""
from __future__ import annotations

from genesis.graph.engine import FakeGraph, GraphEdge, Verdict
from genesis.linking.relatedness import FakeRelatednessScorer
from genesis.recall.allowlist import ALLOWED_EDGE_TYPES, filter_allowed, is_allowed
from genesis.recall.search_backend import FakeRecallSearch
from genesis.recall.service import RecallService
from genesis.recall.tier import Tier


def _edge(eid, fact, *, type, class_=None):
    return GraphEdge(edge_id=eid, fact=fact, episodes=["EP-1"], verdict=Verdict.CONFIRMED,
                     class_=class_, type=type)


def _svc(engine, *, search=None):
    return RecallService(engine, FakeRelatednessScorer(default=0.5), search=search)


# --- the allow-list itself (pure) ---

def test_allowlist_is_the_8_minted_relations():
    assert ALLOWED_EDGE_TYPES == {"WORKS_ON", "MEMBER_OF", "ASSIGNED", "BLOCKS",
                                  "PART_OF", "ABOUT", "PRODUCED", "PARTICIPATED_IN"}
    assert "RELATES_TO" not in ALLOWED_EDGE_TYPES  # no generic catch-all
    assert "DECIDED_BY" not in ALLOWED_EDGE_TYPES   # deferred to fast-follow


def test_filter_allowed_drops_untyped_and_generic_and_perceives():
    edges = [
        _edge("ok", "alpha works on beta", type="WORKS_ON"),
        _edge("gen", "generic edge", type="RELATES_TO"),
        _edge("per", "a read of the principal", type="perceives", class_="perceives"),
        _edge("none", "untyped junk", type=None),
    ]
    kept, dropped = filter_allowed(edges)
    assert [e.edge_id for e in kept] == ["ok"]
    assert dropped == 3
    assert is_allowed(edges[0]) and not is_allowed(edges[1])


# --- AC-R1 on the recall read paths (red-line) ---

def test_ac_r1_expand_excludes_perceives_and_unclassified():
    g = FakeGraph()
    g.seed(_edge("ok", "alpha works on beta", type="WORKS_ON"))
    g.seed(_edge("per", "a read of the principal", type="perceives", class_="perceives"))
    g.seed(_edge("gen", "generic contaminant", type="RELATES_TO"))
    svc = _svc(g)
    r = svc.expand("EP-1", Tier.EPISODIC)
    assert [re.edge.edge_id for re in r.edges] == ["ok"]   # ONLY the typed memory edge
    assert svc.drop_count == 2                             # perceives + unclassified excluded (AC-DROP1)


def test_ac_r1_search_excludes_perceives_and_unclassified():
    g = FakeGraph()
    ok = _edge("ok", "alpha works on beta", type="WORKS_ON")
    per = _edge("per", "a read of the principal", type="perceives", class_="perceives")
    gen = _edge("gen", "generic contaminant", type="RELATES_TO")
    for e in (ok, per, gen):
        g.seed(e)
    search = FakeRecallSearch()
    search.set_semantic("q", [ok, per, gen])
    search.set_keyword("q", [ok, per, gen])
    svc = _svc(g, search=search)
    r = svc.search("q", Tier.FULL, top_n=5)
    assert [re.edge.edge_id for re in r.edges] == ["ok"]
    assert svc.drop_count >= 2  # both channels feed the guard; perceives + generic never served


def test_ac_drop1_exclusion_is_counted():
    g = FakeGraph()
    g.seed(_edge("gen", "off-ontology edge", type="RELATES_TO"))
    svc = _svc(g)
    assert svc.drop_count == 0
    svc.expand("EP-1", Tier.EPISODIC)
    assert svc.drop_count == 1  # the exclusion is observable, not silent
