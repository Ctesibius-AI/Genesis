# tests/test_persona_reconcile.py
from __future__ import annotations

from genesys.journal.journal import read_journal
from genesys.persona.alignment import Alignment
from genesys.persona.discussion import fold_requests
from genesys.persona.reconcile import (
    check_backlog,
    notice_if_divergent,
    raise_pending,
    request_discussion,
)
from genesys.persona.window import DiscussionWindow, WindowRule


def test_notice_only_on_divergence():
    assert notice_if_divergent(Alignment("Trait:rigor", "divergent", 2)) is not None
    assert notice_if_divergent(Alignment("Trait:rigor", "aligned", 0)) is None


def test_request_discussion_enqueues(tmp_path):
    rid = request_discussion(tmp_path, ts="2026-08-17T10:00:00Z", anchor="Trait:rigor")
    assert fold_requests(tmp_path)[rid].state == "queued"


def test_raise_pending_serves_in_window(tmp_path):
    request_discussion(tmp_path, ts="2026-08-17T10:00:00Z", anchor="Trait:rigor")
    win = DiscussionWindow(rules=[WindowRule(days=["Mon"], from_="21:00", to="23:00")])
    opener, served = raise_pending(tmp_path, win, now="2026-08-17T21:30:00Z")
    assert opener is not None and "Trait:rigor" in opener and len(served) == 1
    assert fold_requests(tmp_path)[served[0].request_id].state == "served"


def test_raise_pending_silent_outside_window(tmp_path):
    request_discussion(tmp_path, ts="2026-08-17T10:00:00Z", anchor="Trait:rigor")
    win = DiscussionWindow(rules=[WindowRule(days=["Mon"], from_="21:00", to="23:00")])
    opener, served = raise_pending(tmp_path, win, now="2026-08-17T10:05:00Z")
    assert opener is None and served == []


def test_check_backlog_journals(tmp_path):
    request_discussion(tmp_path, ts="2026-08-01T10:00:00Z", anchor="Trait:rigor")
    reqs = fold_requests(tmp_path)
    assert check_backlog(tmp_path, reqs, now="2026-09-01T10:00:00Z", max_open=5, max_age_days=30) is True
    assert any(e.action == "backlog-breach" for e in read_journal(tmp_path))


def test_backlog_breach_maps_to_persona_view():
    from genesys.console.model import ACTION_TO_VIEW
    assert ACTION_TO_VIEW["backlog-breach"] == "persona"
