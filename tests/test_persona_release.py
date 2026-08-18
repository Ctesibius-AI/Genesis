from __future__ import annotations

from genesys.persona.release import ReleaseContext, closed, covers, is_open


def test_default_is_closed():
    c = closed()
    assert c.open is False and c.open_anchors == [] and c.scope == "topic"
    assert is_open(c) is False


def test_none_context_is_closed():
    assert is_open(None) is False
    assert covers(None, "Trait:rigor") is False


def test_open_covers_only_its_anchors():
    c = ReleaseContext(open=True, open_anchors=["Trait:rigor"], scope="topic",
                       opened_by="turn-9", confirmed_at="t")
    assert is_open(c) is True
    assert covers(c, "Trait:rigor") is True
    assert covers(c, "Trait:other") is False


def test_closed_context_covers_nothing_even_with_anchors():
    c = ReleaseContext(open=False, open_anchors=["Trait:rigor"])
    assert covers(c, "Trait:rigor") is False  # open flag is authoritative
