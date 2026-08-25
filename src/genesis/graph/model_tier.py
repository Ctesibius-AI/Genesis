"""R5 model-tier routing (D-GCW-8): route graphiti's small-tier LLM calls to Haiku.

graphiti-core's AnthropicClient ignores `config.small_model` (R6 — `anthropic_client.py:293`,
design §0b) ⚠ NOT re-verified offline; confirm at the live run (C1, live-run checklist). This
Genesis-side wrapper honours `model_size` so extraction's cheap sub-calls use Haiku, the primary
v1 cost lever. When the 1-line upstream R6 PR lands + graphiti-core is bumped, delete this wrapper.

The model-SELECTION rule is a pure function (offline-tested). The graphiti subclass is built lazily
so this module imports offline (the subclass needs graphiti-core, absent in the offline sandbox).
"""

from __future__ import annotations

# Tunable (P-2): the small tier routes to a current Haiku snapshot; the standard tier stays Sonnet.
SMALL_MODEL_DEFAULT = "claude-haiku-4-5"
STANDARD_MODEL_DEFAULT = "claude-sonnet-4-6"


def resolve_model(model_size, *, standard: str, small: str) -> str:
    """Return the model id for a call's tier: small tier → `small`, everything else → `standard`.

    graphiti passes `model_size` as an enum or str ("small"/"medium"). Fail-safe: anything that is
    not explicitly "small" uses the standard model (never silently downgrade a standard call).
    """
    size = getattr(model_size, "value", model_size)
    return small if str(size).strip().lower() == "small" else standard


# The params the R5 wrapper's _generate_response override depends on. If graphiti-core's base
# signature drifts (e.g. a 0.30+ bump), the override is unsafe — F-12.4 guard.
_EXPECTED_OVERRIDE_PARAMS = frozenset({"messages", "response_model", "max_tokens", "model_size"})


def override_signature_ok(anthropic_client_cls) -> bool:
    """True iff the base `_generate_response` exposes the params the R5 wrapper overrides (F-12.4).

    Offline-testable (pass any class). Used to fail LOUD-then-fall-back rather than run a broken
    monkeypatch when the pinned graphiti-core signature changes.
    """
    import inspect
    try:
        params = set(inspect.signature(anthropic_client_cls._generate_response).parameters)
    except (ValueError, TypeError, AttributeError):
        return False
    return _EXPECTED_OVERRIDE_PARAMS <= params


def build_tiered_anthropic_client(config, *, small_model: str = SMALL_MODEL_DEFAULT):  # pragma: no cover - live only
    """Build a graphiti AnthropicClient subclass that honours `model_size` (R5).

    Lazy import: graphiti-core is absent in the offline sandbox. ⚠ The exact `_generate_response`
    signature of graphiti-core v0.29.3 is confirmed at the live run (C1); if upstream already
    honours `small_model`, this wrapper is unnecessary — `request clarification` and drop it.
    """
    import warnings

    from graphiti_core.llm_client.anthropic_client import AnthropicClient
    from graphiti_core.llm_client.config import ModelSize

    standard_model = getattr(config, "model", None) or STANDARD_MODEL_DEFAULT

    # F-12.4: if graphiti-core's _generate_response signature has drifted (e.g. a >=0.30 bump), the
    # R5 override would be unsafe. Warn LOUDLY and fall back to the plain client (standard model) —
    # honoring "never silently downgrade a tier": extraction runs on Sonnet, no broken monkeypatch.
    if not override_signature_ok(AnthropicClient):
        warnings.warn(
            "graphiti-core AnthropicClient._generate_response signature no longer matches the R5 "
            "Haiku wrapper; the small-tier routing is DISABLED and extraction runs on the standard "
            "model. Pin graphiti-core<0.30 or update graph/model_tier.py (F-12.4).",
            RuntimeWarning, stacklevel=2)
        return AnthropicClient(config=config)

    class _TieredAnthropicClient(AnthropicClient):
        # Signature matches graphiti-core v0.29.3 AnthropicClient._generate_response exactly
        # (live-verified 2026-08-26). The base uses `model=self.model` for the request and never
        # reads config.small_model (C1 confirmed), so swapping self.model for the small tier routes
        # the call to Haiku (R5).
        async def _generate_response(self, messages, response_model=None, max_tokens=None,
                                     model_size: ModelSize = ModelSize.medium):
            chosen = resolve_model(model_size, standard=standard_model, small=small_model)
            prior = self.model
            self.model = chosen
            try:
                return await super()._generate_response(
                    messages, response_model=response_model, max_tokens=max_tokens,
                    model_size=model_size)
            finally:
                self.model = prior

    return _TieredAnthropicClient(config=config)
