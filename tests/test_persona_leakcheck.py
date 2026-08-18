from __future__ import annotations

import pytest

from genesys.persona.leakcheck import (
    assert_no_unkeyed_leak,
    release_journaled_before,
    unkeyed_leak,
)
from genesys.persona.release import ReleaseContext


def test_unkeyed_leak_detects_uncovered_served_anchor():
    ctx = ReleaseContext(open=True, open_anchors=["Trait:rigor"])
    assert unkeyed_leak(["Trait:rigor"], ctx) == []               # covered → no leak
    assert unkeyed_leak(["Trait:rigor", "Trait:candor"], ctx) == ["Trait:candor"]
    assert unkeyed_leak(["Trait:rigor"], None) == ["Trait:rigor"]  # no context → leak


def test_assert_no_unkeyed_leak_raises():
    with pytest.raises(AssertionError):
        assert_no_unkeyed_leak(["Trait:x"], None)
    assert_no_unkeyed_leak([], None)  # nothing served → fine


def test_release_journaled_before(tmp_path):
    from genesys.persona.release_machine import open_release
    from genesys.persona.department import PerceptionDepartment
    assert release_journaled_before(tmp_path, ts="2026-08-17T10:00:00Z") is False
    open_release(tmp_path, PerceptionDepartment(), asked_anchor="Trait:rigor", scope="topic",
                 ts="2026-08-17T09:00:00Z", opened_by="turn-1")
    assert release_journaled_before(tmp_path, ts="2026-08-17T10:00:00Z") is True


def test_routing_default_delegates_to_locked_filter():
    from genesys.persona.department import PerceptionDepartment
    from genesys.persona.routing import visible_perceived_default_locked
    d = PerceptionDepartment()
    d.add_observation(anchor="Trait:rigor", episode="EP-1", valid_at="t")
    assert visible_perceived_default_locked(d) == []  # still fail-closed via the canonical filter
