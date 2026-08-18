from __future__ import annotations

from genesys.persona.discussion import (
    backlog_breach,
    close,
    enqueue,
    fold_requests,
    serve,
)


def test_enqueue_scrubs_seed_reason_and_projects_queued(tmp_path):
    rid = enqueue(tmp_path, ts="2026-08-17T10:00:00Z", anchor="Trait:rigor",
                  seed_reason="he disagreed, token sk-ABC123DEF456GHI789JKL0")
    reqs = fold_requests(tmp_path)
    assert reqs[rid].state == "queued" and reqs[rid].anchor == "Trait:rigor"
    assert "sk-ABC123DEF456GHI789JKL0" not in (reqs[rid].seed_reason or "")


def test_lifecycle_queued_served_closed(tmp_path):
    rid = enqueue(tmp_path, ts="2026-08-17T10:00:00Z", anchor="Trait:rigor")
    serve(tmp_path, ts="2026-08-17T21:00:00Z", request_id=rid, anchor="Trait:rigor")
    assert fold_requests(tmp_path)[rid].state == "served"
    close(tmp_path, ts="2026-08-17T21:10:00Z", request_id=rid, anchor="Trait:rigor",
          reason="discussed")
    r = fold_requests(tmp_path)[rid]
    assert r.state == "closed" and r.closed_reason == "discussed"


def test_backlog_breach_on_count_and_age(tmp_path):
    for i in range(3):
        enqueue(tmp_path, ts="2026-08-01T10:00:00Z", anchor=f"Trait:{i}")
    reqs = fold_requests(tmp_path)
    assert backlog_breach(reqs, now="2026-08-17T10:00:00Z", max_open=5, max_age_days=10) is True  # old
    assert backlog_breach(reqs, now="2026-08-01T11:00:00Z", max_open=2, max_age_days=30) is True  # count
    assert backlog_breach(reqs, now="2026-08-01T11:00:00Z", max_open=5, max_age_days=30) is False
