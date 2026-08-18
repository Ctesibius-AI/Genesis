"""Topics-only reconciliation/discussion templates (spec §10.2, §8.6 item 1, Fence 7).

PT-7 (reconciliation notice) and PT-8 (opener) name TOPICS/anchors only — never Daimon's view;
the opinion is voiced only after the §8.6 key + confirmation. PT-8 is the one sanctioned opener
(the KEY-1 exception): she may raise it, and the principal's affirmation is a valid key path.
"""

from __future__ import annotations


def pt7_reconciliation_notice(anchor: str) -> str:
    return (f"On {anchor}, what you've said and what I've observed don't line up — "
            "want to talk about it?")


def pt8_opener(topics: list[str]) -> str:
    if not topics:
        raise ValueError("no opener without topics (Fence 7: she never invites the question)")
    listed = topics[0] if len(topics) == 1 else ", ".join(topics[:-1]) + f" and {topics[-1]}"
    return f"we have some discussion requests pending — you wanted to talk about {listed}?"


def is_opener_exception(*, opener_was_raised: bool, principal_affirms: bool) -> bool:
    return opener_was_raised and principal_affirms
