"""BT-9 / D-GCW-8 (R5): the model-tier selection rule (pure, offline-testable).

The graphiti AnthropicClient subclass is live-only (graphiti-core absent offline); the routing
DECISION is a pure function tested here. C1 (does upstream ignore small_model) is on the live-run
checklist per the owner's ruling.
"""
from __future__ import annotations

from enum import Enum

from genesys.graph.model_tier import STANDARD_MODEL_DEFAULT, resolve_model


class _Size(str, Enum):
    small = "small"
    medium = "medium"


def test_small_tier_routes_to_haiku():
    assert resolve_model("small", standard="sonnet", small="haiku") == "haiku"
    assert resolve_model(_Size.small, standard="sonnet", small="haiku") == "haiku"


def test_non_small_stays_standard():
    for size in ("medium", "large", _Size.medium, None, ""):
        assert resolve_model(size, standard="sonnet", small="haiku") == "sonnet"


def test_defaults_are_pinned_ids():
    assert STANDARD_MODEL_DEFAULT.startswith("claude-")
