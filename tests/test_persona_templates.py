from __future__ import annotations

import pytest

from genesys.persona.templates import (
    is_opener_exception,
    pt7_reconciliation_notice,
    pt8_opener,
)


def test_pt7_names_anchor_only():
    msg = pt7_reconciliation_notice("Trait:rigor")
    assert "Trait:rigor" in msg


def test_pt8_lists_topics_only():
    msg = pt8_opener(["Trait:rigor", "Value:honesty"])
    assert "Trait:rigor" in msg and "Value:honesty" in msg
    assert msg.endswith("?")


def test_pt8_requires_topics():
    with pytest.raises(ValueError):
        pt8_opener([])


def test_opener_exception_only_when_raised_and_affirmed():
    assert is_opener_exception(opener_was_raised=True, principal_affirms=True) is True
    assert is_opener_exception(opener_was_raised=True, principal_affirms=False) is False
    assert is_opener_exception(opener_was_raised=False, principal_affirms=True) is False
