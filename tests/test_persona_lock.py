from __future__ import annotations

from genesys.persona.department import PerceptionDepartment
from genesys.persona.lock import can_voice, for_task_read, visible_perceived
from genesys.persona.release import ReleaseContext, closed


def _dept():
    d = PerceptionDepartment()
    d.add_observation(anchor="Trait:rigor", episode="EP-1", valid_at="t")
    d.add_observation(anchor="Trait:candor", episode="EP-2", valid_at="t")
    return d


def test_locked_returns_nothing():
    d = _dept()
    assert visible_perceived(d, None) == []       # fail-closed on None
    assert visible_perceived(d, closed()) == []   # closed context


def test_open_returns_only_covered_anchors():
    d = _dept()
    ctx = ReleaseContext(open=True, open_anchors=["Trait:rigor"], confirmed_at="t")
    got = visible_perceived(d, ctx)
    assert [e.to for e in got] == ["Trait:rigor"]  # candor not in open_anchors → excluded


def test_general_scope_multiple_anchors():
    d = _dept()
    ctx = ReleaseContext(open=True, open_anchors=["Trait:rigor", "Trait:candor"], scope="general")
    assert {e.to for e in visible_perceived(d, ctx)} == {"Trait:rigor", "Trait:candor"}


def test_task_read_never_returns_perceived_even_when_open():
    d = _dept()
    ctx = ReleaseContext(open=True, open_anchors=["Trait:rigor", "Trait:candor"])
    assert for_task_read(d, ctx) == []   # R-M: task use never consults her opinion of him


def test_can_voice_requires_coverage():
    ctx = ReleaseContext(open=True, open_anchors=["Trait:rigor"])
    assert can_voice(ctx, "Trait:rigor") is True
    assert can_voice(ctx, "Trait:candor") is False
    assert can_voice(None, "Trait:rigor") is False
