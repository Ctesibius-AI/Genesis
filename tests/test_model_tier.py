"""BT-9 / D-GCW-8 (R5): the model-tier selection rule (pure, offline-testable).

The graphiti AnthropicClient subclass is live-only (graphiti-core absent offline); the routing
DECISION is a pure function tested here. C1 (does upstream ignore small_model) is on the live-run
checklist per the owner's ruling.
"""
from __future__ import annotations

from enum import Enum

from genesis.graph.model_tier import (
    STANDARD_MODEL_DEFAULT,
    override_signature_ok,
    resolve_model,
)


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


# --- F-12.4: the override-signature guard (offline; live-only monkeypatch stays uncovered) --- #

def test_override_signature_ok_accepts_the_pinned_shape():
    """A class whose `_generate_response` exposes the params the R5 wrapper overrides passes."""
    class _Pinned:
        def _generate_response(self, messages, response_model=None, max_tokens=None,
                               model_size=None):  # graphiti-core 0.29.x shape
            ...
    assert override_signature_ok(_Pinned) is True


def test_override_signature_ok_rejects_drifted_signature():
    """If upstream drops/renames a param the wrapper needs, the guard returns False — the caller
    then warns LOUD and falls back to the standard model, never a broken silent monkeypatch."""
    class _Drifted:
        def _generate_response(self, messages, response_model=None):  # lost max_tokens/model_size
            ...
    assert override_signature_ok(_Drifted) is False

    class _NoMethod:
        pass
    assert override_signature_ok(_NoMethod) is False
