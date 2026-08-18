from __future__ import annotations

from genesys.workers.backend import FakeLLMBackend
from genesys.workers.judge import JUDGE_PROMPT, JudgeResult, invalidation_judge


def test_prompt_is_verbatim_c32_anchors():
    assert "You are the Invalidation Judge" in JUDGE_PROMPT
    assert "Bias to REVERT under uncertainty" in JUDGE_PROMPT


def test_judge_parses_revert_and_passes_class():
    b = FakeLLMBackend('{"recommendation": "REVERT", "independent_occurrences": 1, '
                       '"stated_update": false, "ask_window": false, "reasoning": "one instance", '
                       '"occurrence_analysis": [{"episode": "EP-0", "counts_because": "distinct"}]}')
    r = invalidation_judge(b, closed_fact="old", new_evidence="new", fact_class="C3")
    assert isinstance(r, JudgeResult)
    assert r.recommendation == "REVERT" and r.independent_occurrences == 1
    assert r.occurrence_analysis == [{"episode": "EP-0", "counts_because": "distinct"}]
    assert "C3" in b.last["user"]
    assert b.last["model"] == "claude-sonnet-4-6"
