"""A single empty/malformed LLM reply must never crash the drain — every worker
falls back to its conservative default instead of raising (regression for the live
Verifier JSONDecodeError that wedged the first backfill extraction)."""

from __future__ import annotations

import pytest

from genesis.workers.backend import FakeLLMBackend, safe_json_object
from genesis.workers.class_auditor import class_audit, fragment_merge
from genesis.workers.judge import invalidation_judge
from genesis.workers.screen import screen
from genesis.workers.verifier import verify

BAD_REPLIES = ["", "   ", "not json at all", "```json\n\n```", "[1, 2, 3]"]


@pytest.mark.parametrize("raw", BAD_REPLIES)
def test_safe_json_object_returns_empty_dict(raw):
    assert safe_json_object(raw) == {}


def test_safe_json_object_parses_good_and_fenced():
    assert safe_json_object('{"a": 1}') == {"a": 1}
    assert safe_json_object('```json\n{"ruling": "UPHOLD"}\n```') == {"ruling": "UPHOLD"}


@pytest.mark.parametrize("raw", BAD_REPLIES)
def test_verify_fails_closed_to_overrule(raw):
    r = verify(FakeLLMBackend(raw), flag="S1", raw_span="r", artifacts="a", contract="c")
    assert r.ruling == "OVERRULE" and r.remedy.action == "none"


@pytest.mark.parametrize("raw", BAD_REPLIES)
def test_screen_fails_closed_to_flag(raw):
    # D-FB-3(a): unparseable/garbage Screen output is now a SUSPICION → FLAG (never a quiet PASS);
    # the Verifier adjudicates. Previously this defaulted to PASS — fail-OPEN mislabelled fail-closed.
    r = screen(FakeLLMBackend(raw), jot="j", manifest="m")
    assert r.verdict == "FLAG"


@pytest.mark.parametrize("raw", BAD_REPLIES)
def test_judge_fails_closed_to_revert(raw):
    r = invalidation_judge(FakeLLMBackend(raw), closed_fact="f", new_evidence="e", fact_class="C1")
    assert r.recommendation == "REVERT"


@pytest.mark.parametrize("raw", BAD_REPLIES)
def test_class_audit_and_merge_fail_closed(raw):
    a = class_audit(FakeLLMBackend(raw), sample="s")
    assert a.per_artifact == [] and a.drift_report == {}
    m = fragment_merge(FakeLLMBackend(raw), candidate="c", existing="e")
    assert m.verdict == "BOUNDARY"
