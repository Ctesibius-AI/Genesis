from __future__ import annotations

from genesys.workers.backend import FakeLLMBackend
from genesys.workers.verifier import VERIFIER_PROMPT, VerifierResult, verify


def test_prompt_is_verbatim_c33_anchors():
    assert "You are the Verifier" in VERIFIER_PROMPT
    assert "independent derivation" in VERIFIER_PROMPT


def test_verify_parses_uphold_with_remedy():
    b = FakeLLMBackend('{"ruling": "UPHOLD", "remedy": {"action": "amend", "target": "e1", '
                       '"content": "corrected"}, "reasoning": "off"}')
    r = verify(b, flag="S3", raw_span="raw", artifacts="arts", contract="rules")
    assert isinstance(r, VerifierResult)
    assert r.ruling == "UPHOLD" and r.remedy.action == "amend" and r.remedy.content == "corrected"
    assert b.last["model"] == "claude-opus-4-8"


def test_verify_overrule_without_remedy():
    b = FakeLLMBackend('{"ruling": "OVERRULE", "reasoning": "fine"}')
    r = verify(b, flag="S1", raw_span="r", artifacts="a", contract="c")
    assert r.ruling == "OVERRULE" and r.remedy.action == "none"
