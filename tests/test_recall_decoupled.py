"""BT-4 / AC-P2 (red-line, gate G-β): recall is DECOUPLED from persona.

Replace-then-remove / decouple-before-delete (CRIT-1): the recall read path serves reads with NO
`persona` import and NO `ReleaseContext` — the allow-list (not the fence) is the guard. This proof
must be GREEN before `recall/fence.py` and the persona profiler are removed.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import genesys.recall.daemon as daemon_mod
import genesys.recall.service as service_mod
import genesys.recall.tool as tool_mod
from genesys.graph.engine import FakeGraph, GraphEdge, Verdict
from genesys.linking.relatedness import FakeRelatednessScorer
from genesys.recall.service import RecallService
from genesys.recall.tier import Tier

_READ_PATH = [service_mod, daemon_mod, tool_mod]


def _imports_of(mod) -> set[str]:
    src = Path(mod.__file__).read_text(encoding="utf-8")
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_recall_read_path_has_no_persona_import():
    for mod in _READ_PATH:
        offenders = {n for n in _imports_of(mod) if "persona" in n}
        assert offenders == set(), f"{mod.__name__} still imports persona: {offenders}"


def test_recall_modules_expose_no_releasecontext():
    for mod in _READ_PATH:
        assert not hasattr(mod, "ReleaseContext"), f"{mod.__name__} still binds ReleaseContext"


def test_fence_module_is_gone():
    with __import_should_fail():
        importlib.import_module("genesys.recall.fence")


class __import_should_fail:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        assert exc_type is ModuleNotFoundError, "recall.fence should have been deleted (BT-4)"
        return True  # swallow the expected ModuleNotFoundError


def test_recall_still_serves_after_decouple():
    g = FakeGraph()
    g.seed(GraphEdge("ok", "alpha works on beta", ["EP-1"], verdict=Verdict.CONFIRMED, type="WORKS_ON"))
    svc = RecallService(g, FakeRelatednessScorer(default=0.5))  # no PerceptionDepartment arg
    r = svc.expand("EP-1", Tier.EPISODIC)
    assert [re.edge.edge_id for re in r.edges] == ["ok"]  # decoupled recall still serves
