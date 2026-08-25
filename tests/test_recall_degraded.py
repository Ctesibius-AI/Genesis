"""BT-5 / AC-R2: down != empty. Recall down surfaces EmptyCause.DEGRADED, never ABSENT.

Never the same signal for both, never a bare []. The confirmation-line string ("unavailable") must
be reachable only from the real DEGRADED down-branch (AC-CONF1 literalism; the line itself is BT-8).
"""
from __future__ import annotations

from genesis.graph.engine import FakeGraph
from genesis.linking.relatedness import FakeRelatednessScorer
from genesis.recall.daemon import RecallDaemon
from genesis.recall.scorer import EmptyCause
from genesis.recall.search_backend import FakeRecallSearch
from genesis.recall.service import RecallService
from genesis.recall.tier import Tier
from genesis.recall.tool import format_for_injection


def _daemon(search):
    return RecallDaemon(RecallService(FakeGraph(), FakeRelatednessScorer(default=0.5), search=search))


def test_recall_down_is_degraded_not_absent():
    class _Boom(FakeRecallSearch):
        def semantic(self, query, top_n):
            raise RuntimeError("graph backend down")
    r = _daemon(_Boom()).serve_search("q", Tier.FULL)
    assert r.is_empty()
    assert r.verdict.cause is EmptyCause.DEGRADED  # down-path, not ABSENT


def test_healthy_empty_is_absent_not_degraded():
    r = _daemon(FakeRecallSearch()).serve_search("nothing here", Tier.FULL)
    assert r.is_empty()
    assert r.verdict.cause is EmptyCause.ABSENT  # earned-empty, distinguishable from down


def test_format_surfaces_degraded_distinctly():
    class _Boom(FakeRecallSearch):
        def semantic(self, query, top_n):
            raise RuntimeError("down")
    down = format_for_injection(_daemon(_Boom()).serve_search("q", Tier.FULL))
    absent = format_for_injection(_daemon(FakeRecallSearch()).serve_search("q", Tier.FULL))
    assert "unavailable" in down.lower()
    assert "unavailable" not in absent.lower()  # "unavailable" only from the real down-path
