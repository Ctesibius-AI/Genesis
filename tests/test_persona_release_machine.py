from __future__ import annotations

from genesys.journal.journal import read_journal
from genesys.persona.department import PerceptionDepartment
from genesys.persona.release_machine import (
    close_release,
    general_anchors,
    open_release,
    topic_anchors,
)


def test_topic_anchors_is_asked_plus_neighbours_deduped():
    assert topic_anchors("Trait:rigor", ["Trait:candor", "Trait:rigor"]) == ["Trait:rigor", "Trait:candor"]


def test_general_anchors_top_n_by_strength():
    d = PerceptionDepartment()
    for ep in ("EP-1", "EP-2", "EP-3"):
        d.add_observation(anchor="Trait:strong", episode=ep, valid_at="t")
    d.add_observation(anchor="Trait:weak", episode="EP-1", valid_at="t")
    assert general_anchors(d, top_n=1) == ["Trait:strong"]


def test_open_release_topic_scope_journals_and_opens(tmp_path):
    d = PerceptionDepartment()
    ctx = open_release(tmp_path, d, asked_anchor="Trait:rigor", scope="topic",
                       ts="2026-08-17T10:00:00Z", opened_by="turn-9",
                       neighbours=["Trait:candor"])
    assert ctx.open is True and ctx.open_anchors == ["Trait:rigor", "Trait:candor"]
    assert ctx.confirmed_at == "2026-08-17T10:00:00Z" and ctx.scope == "topic"
    actions = [e.action for e in read_journal(tmp_path)]
    assert actions == ["opinion-ask", "opinion-confirm", "opinion-release"]


def test_close_release_journals_and_clears(tmp_path):
    d = PerceptionDepartment()
    ctx = open_release(tmp_path, d, asked_anchor="Trait:rigor", scope="topic",
                       ts="2026-08-17T10:00:00Z", opened_by="turn-9")
    closed_ctx = close_release(tmp_path, ctx, reason="idle", ts="2026-08-17T10:20:00Z")
    assert closed_ctx.open is False and closed_ctx.open_anchors == []
    closes = [e for e in read_journal(tmp_path) if e.action == "opinion-close"]
    assert len(closes) == 1 and closes[0].reason == "idle"


def test_close_on_already_closed_is_noop(tmp_path):
    from genesys.persona.release import closed
    close_release(tmp_path, closed(), reason="idle", ts="t")
    assert [e for e in read_journal(tmp_path) if e.action == "opinion-close"] == []
