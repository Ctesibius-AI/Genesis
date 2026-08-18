from __future__ import annotations

from genesys.diary.briefing import Briefing, enforce_budget, estimate_tokens, parse_briefing


def test_estimate_tokens_is_chars_over_four_rounded_up():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_parse_then_render_round_trips_known_sections():
    text = "## TOP OF MIND\n- a\n\n## COMMITMENTS\n- due friday"
    b = parse_briefing(text)
    assert set(b.sections) == {"TOP OF MIND", "COMMITMENTS"}
    assert "## TOP OF MIND" in b.render() and "## COMMITMENTS" in b.render()


def test_overflow_drops_top_of_mind_first_never_commitments():
    b = Briefing(sections={
        "TOP OF MIND": "x" * 400,
        "COMMITMENTS": "due friday",
        "OPEN QUESTIONS": "which holds?",
    })
    trimmed = enforce_budget(b, cap_tokens=20)  # ~80 chars
    assert "TOP OF MIND" not in trimmed.sections          # dropped first
    assert "COMMITMENTS" in trimmed.sections              # never dropped
    assert "OPEN QUESTIONS" in trimmed.sections           # never dropped


def test_commitments_and_questions_survive_even_if_over_budget():
    b = Briefing(sections={"COMMITMENTS": "c" * 1000, "OPEN QUESTIONS": "q" * 1000})
    trimmed = enforce_budget(b, cap_tokens=1)
    assert set(trimmed.sections) == {"COMMITMENTS", "OPEN QUESTIONS"}  # nothing droppable left
