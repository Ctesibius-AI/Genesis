"""Relatedness scoring for semantic linking (spec §4.6).

The semantic linker is injected a `RelatednessScorer` — a symmetric [0,1] similarity over two
entry summaries. `FakeRelatednessScorer` scripts scores for offline tests; `real_scorer` is a
lazy embedder-backed stub (the model wiring lands with the embedder integration environment,
same posture as the P3.5 real graph client). Thresholds are provisional §26 defaults.
"""

from __future__ import annotations

from typing import Protocol

SAME_TOPIC_MIN = 0.75
REFERENCES_MIN = 0.45


class RelatednessScorer(Protocol):
    def related(self, a: str, b: str) -> float: ...


class FakeRelatednessScorer:
    def __init__(self, *, default: float = 0.0) -> None:
        self._default = default
        self._scores: dict[frozenset[str], float] = {}

    def set(self, a: str, b: str, score: float) -> None:
        self._scores[frozenset((a, b))] = score

    def related(self, a: str, b: str) -> float:
        return self._scores.get(frozenset((a, b)), self._default)


def real_scorer(*, model: str | None = None):
    """Return a fastembed-backed RelatednessScorer (spec §4.6, DR-05c, §8).

    Lazy-imports fastembed INSIDE this function so the offline test suite (system Python 3.9,
    no fastembed) never reaches the import. The returned scorer computes cosine similarity of
    bge-small-en-v1.5 embeddings for two summary strings and clamps the result to [0, 1].

    Raises RuntimeError if fastembed is absent; the stub RuntimeError path is preserved so the
    offline suite's existing test (that real_scorer raises without the extra) stays green.
    """
    try:
        from fastembed import TextEmbedding  # noqa: PLC0415 — lazy: absent offline
    except ImportError as exc:  # pragma: no cover - exercised only where extra is absent
        raise RuntimeError("the embedder extra (fastembed) is required for a real scorer") from exc

    _model_name = model or "BAAI/bge-small-en-v1.5"
    _embedding_model = TextEmbedding(_model_name)

    class _FastEmbedScorer:
        """cosine-similarity scorer over bge-small embeddings (spec §4.6)."""

        def related(self, a: str, b: str) -> float:  # noqa: D102
            import math  # stdlib — always present

            vecs = list(_embedding_model.embed([a, b]))
            va, vb = vecs[0], vecs[1]
            dot = sum(x * y for x, y in zip(va, vb))
            mag_a = math.sqrt(sum(x * x for x in va))
            mag_b = math.sqrt(sum(x * x for x in vb))
            if mag_a == 0.0 or mag_b == 0.0:
                return 0.0
            raw = dot / (mag_a * mag_b)
            return max(0.0, min(1.0, float(raw)))

    return _FastEmbedScorer()
