from __future__ import annotations

from genesis.workers.backend import FakeLLMBackend
from genesis.workers.class_auditor import (
    CLASS_AUDITOR_PROMPT, ClassAudit, MergeVerdict, class_audit, fragment_merge,
)


def test_prompt_is_verbatim_c34_anchors():
    assert "You are the Class Auditor" in CLASS_AUDITOR_PROMPT
    assert "MODE 2" in CLASS_AUDITOR_PROMPT


def test_class_audit_mode1_parses():
    b = FakeLLMBackend('{"per_artifact": [{"id": "e1", "verdict": "OK"}], '
                       '"drift_report": {"pattern": "NONE"}}')
    r = class_audit(b, sample="s")
    assert isinstance(r, ClassAudit)
    assert r.per_artifact[0]["verdict"] == "OK" and r.drift_report["pattern"] == "NONE"


def test_fragment_merge_mode2_parses():
    b = FakeLLMBackend('{"verdict": "SAME", "reason": "same disposition"}')
    r = fragment_merge(b, candidate="overly meticulous", existing="perfectionist")
    assert isinstance(r, MergeVerdict) and r.verdict == "SAME"
    assert b.last["model"].startswith("claude-sonnet")


def test_fragment_merge_defaults_boundary_on_missing_verdict():
    b = FakeLLMBackend('{"per_artifact": [], "drift_report": {}}')
    r = fragment_merge(b, candidate="test candidate", existing="test existing")
    assert isinstance(r, MergeVerdict)
    assert r.verdict == "BOUNDARY"
