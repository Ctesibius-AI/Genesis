"""Real graphiti-core / FalkorDB backend for Genesys (spec §4.9a, F-11, DR-35).

This module is imported LAZILY — only from inside `real_client()` in factory.py.
It must NEVER be imported at factory module top-level, so the offline test suite
(system Python 3.9, no graphiti-core) continues to pass unchanged.

Key design decisions:
- FastEmbedEmbedder / NoOpCrossEncoder: identical to the proven probe_extract.py.
- FalkorDB embedded via redislite Unix socket (async driver bridged through asyncio loop).
- All async graphiti operations are driven by a persistent event loop (threading.Thread +
  loop.run_until_complete) so that the synchronous GraphitiClient Protocol is satisfied.
- Attributes are stored as flat edge properties by graphiti's save routine (SET e = data
  which includes edge.attributes merged in). On read, `properties(e)` minus the standard
  fields yields them back — so we store/retrieve custom attrs the same way.
- F-11: add_episode returns CREATED edges only; never the invalidated set.
"""

from __future__ import annotations

import asyncio
import subprocess
import threading
from datetime import datetime, timezone
from typing import Any

# -- graphiti-core and friends (only imported when this module is loaded) ----------
from graphiti_core import Graphiti
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.edges import EntityEdge
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.llm_client.anthropic_client import AnthropicClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.nodes import EpisodeType
from graphiti_core.driver.falkordb.operations.entity_edge_ops import (
    FalkorEntityEdgeOperations,
    get_entity_edge_return_query,
    entity_edge_from_record,
)
from graphiti_core.driver.falkordb_driver import GraphProvider
from graphiti_core.utils.maintenance.graph_data_operations import retrieve_episodes

from fastembed import TextEmbedding

# -- our Protocol types (no graphiti dependency) -----------------------------------
from genesys.graph.client import AddEpisodeResults, ClientEdge

# Previous-episode context window. graphiti's add_episode defaults to the **10** most-recent
# prior episodes, sent RAW to the LLM on every extraction (to resolve pronouns/references).
# But a Genesys episode is a WHOLE SESSION (DR-25) — 13KB–700KB+ — so 10 raw sessions per
# extraction balloons token cost and re-egress and risks the context limit. We cap it here
# via graphiti's own `previous_episode_uuids` knob (retrieve_episodes last_n). Customisable —
# tune this constant; cross-session reference resolution only needs the immediate recent tail.
PREVIOUS_EPISODE_WINDOW = 3


# ---------------------------------------------------------------------------
# Embedder & cross-encoder (identical to probe_extract.py)
# ---------------------------------------------------------------------------

class FastEmbedEmbedder(EmbedderClient):
    """Local bge-small-en-v1.5 embedder via fastembed (spec §4.9a)."""

    def __init__(self) -> None:
        self._model = TextEmbedding("BAAI/bge-small-en-v1.5")

    async def create(self, input_data: Any) -> Any:  # noqa: ANN401
        if isinstance(input_data, str):
            texts = [input_data]
        elif isinstance(input_data, list) and input_data and isinstance(input_data[0], str):
            texts = input_data
        else:
            texts = list(input_data)
        embeddings = list(self._model.embed(texts))
        if len(embeddings) == 1:
            return embeddings[0].tolist()
        return [e.tolist() for e in embeddings]

    async def create_batch(self, input_data_list: Any) -> Any:  # noqa: ANN401
        embeddings = list(self._model.embed(input_data_list))
        return [e.tolist() for e in embeddings]


class NoOpCrossEncoder(CrossEncoderClient):
    """Passthrough cross-encoder that ranks all passages equally (spec §4.9a)."""

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        return [(p, 1.0) for p in passages]


# ---------------------------------------------------------------------------
# ISO / datetime helpers
# ---------------------------------------------------------------------------

def _to_iso(dt: datetime | None) -> str | None:
    """Convert a datetime to an ISO-8601 string (UTC-normalised)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO-8601 string to a timezone-aware datetime."""
    # Python 3.11+ handles 'Z' natively; for 3.9 compat we keep the replace
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Edge conversion
# ---------------------------------------------------------------------------

def _entity_edge_to_client_edge(e: EntityEdge) -> ClientEdge:
    """Map a graphiti EntityEdge to our ClientEdge (spec §4.9a, F-11, DR-35).

    Attributes: graphiti stores them flat as edge properties, returning them via
    `properties(e)` minus the standard fields. We pass through the dict as-is.
    """
    return ClientEdge(
        uuid=e.uuid,
        fact=e.fact,
        episodes=list(e.episodes or []),
        valid_at=_to_iso(e.valid_at),
        invalid_at=_to_iso(e.invalid_at),
        expired_at=_to_iso(e.expired_at),
        attributes=dict(e.attributes or {}),
        type=getattr(e, "name", None),  # BT-6: the graphiti relation type, for the recall allow-list
    )


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

class GraphitiCoreClient:
    """Synchronous GraphitiClient backed by graphiti-core + embedded FalkorDB.

    Runs a private asyncio event loop on a daemon thread to bridge the async
    graphiti API into the synchronous Protocol our adapter expects (spec §4.9a).
    """

    def __init__(
        self,
        graphiti: Graphiti,
        driver: FalkorDriver,
        *,
        group_id: str = "genesys",
    ) -> None:
        self._g = graphiti
        self._driver = driver
        self._group_id = group_id
        self._edge_ops = FalkorEntityEdgeOperations()
        # Map: episode name → graphiti episode UUID (needed because graphiti stores episode
        # UUIDs in edge.episodes arrays, not the caller-supplied name strings).
        self._episode_uuid: dict[str, str] = {}
        # Persistent event loop on a daemon thread
        self._loop = asyncio.new_event_loop()
        t = threading.Thread(target=self._loop.run_forever, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Async → sync bridge
    # ------------------------------------------------------------------

    def _run(self, coro: Any) -> Any:  # noqa: ANN401
        """Submit a coroutine to our persistent loop and block until done."""
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result()

    # ------------------------------------------------------------------
    # GraphitiClient Protocol (spec §4.9a, F-11)
    # ------------------------------------------------------------------

    def add_episode(self, name: str, body: str, ref_ts: str) -> AddEpisodeResults:
        """Add an episode and return CREATED edges only (F-11, DR-35).

        Graphiti's AddEpisodeResults contains both `edges` (created) and an
        invalidated-edges signal embedded in expired_at timestamps. We return
        only the created set; the adapter reads invalidations via
        `edges_expired_in` post-commit.
        """
        ref_dt = _parse_iso(ref_ts)

        async def _add() -> AddEpisodeResults:
            # Cap the previous-episode context window (default 10 → PREVIOUS_EPISODE_WINDOW).
            # Fetch the N most-recent prior episodes ourselves and pass them explicitly, so
            # graphiti does not auto-pull its hardcoded 10 raw whole-sessions per extraction.
            prev = await retrieve_episodes(
                self._driver,
                reference_time=ref_dt,
                last_n=PREVIOUS_EPISODE_WINDOW,
                group_ids=[self._group_id],
            )
            # BT-6 / AC-G1 (D-GCW-14): feed speaker turns as EpisodeType.message and pass the
            # ontology so graphiti classifies into typed nodes + the 8 named relations (not a
            # generic Entity/RELATES_TO blob). The edge_type_map names double as the recall
            # allow-list (name once — graph.ontology is the single source).
            from genesys.graph.ontology import (
                build_edge_type_map, build_edge_types, build_entity_types)
            result = await self._g.add_episode(
                name=name,
                episode_body=body,
                reference_time=ref_dt,
                source=EpisodeType.message,
                source_description="genesys",
                group_id=self._group_id,
                previous_episode_uuids=[ep.uuid for ep in prev],
                entity_types=build_entity_types(),
                edge_types=build_edge_types(),      # the MODELS — constrain names to the 8 relations
                edge_type_map=build_edge_type_map(),
            )
            # Store name → graphiti episode UUID so edges_for_episode can look it up.
            # graphiti stores episode UUIDs (not names) in edge.episodes arrays.
            if result.episode is not None:
                self._episode_uuid[name] = result.episode.uuid
            created = [_entity_edge_to_client_edge(e) for e in (result.edges or [])]
            return AddEpisodeResults(edges=created)

        return self._run(_add())

    def edges_for_episode(self, episode_id: str) -> list[ClientEdge]:
        """Return all entity edges whose episodes list contains episode_id (spec §4.9a).

        `episode_id` is the caller-supplied episode name. Graphiti stores episode UUIDs
        (not names) in edge.episodes arrays, so we translate via the name→uuid cache that
        was populated during add_episode. If the UUID is unknown (e.g. from a prior
        session), we fall back to querying by the Episodic node's name field.
        """
        # Resolve name → graphiti episode UUID
        ep_uuid = self._episode_uuid.get(episode_id)

        return_q = get_entity_edge_return_query(GraphProvider.FALKORDB)

        if ep_uuid is not None:
            # Fast path: we know the UUID from this session
            query = (
                "MATCH (n:Entity)-[e:RELATES_TO]->(m:Entity)\n"
                "WHERE $ep_uuid IN e.episodes\n"
                "RETURN\n" + return_q
            )

            async def _fetch_by_uuid() -> list[ClientEdge]:
                records, _, _ = await self._driver.execute_query(query, ep_uuid=ep_uuid)
                return [_entity_edge_to_client_edge(entity_edge_from_record(r)) for r in records]

            return self._run(_fetch_by_uuid())
        else:
            # Fallback: look up the Episodic node by name, then use its UUID
            lookup_q = (
                "MATCH (ep:Episodic {name: $ep_name})\n"
                "MATCH (n:Entity)-[e:RELATES_TO]->(m:Entity)\n"
                "WHERE ep.uuid IN e.episodes\n"
                "RETURN\n" + return_q
            )

            async def _fetch_by_name() -> list[ClientEdge]:
                records, _, _ = await self._driver.execute_query(lookup_q, ep_name=episode_id)
                return [_entity_edge_to_client_edge(entity_edge_from_record(r)) for r in records]

            return self._run(_fetch_by_name())

    def edges_expired_in(self, start_ts: str, end_ts: str) -> list[ClientEdge]:
        """Return entity edges with expired_at in [start_ts, end_ts] (spec §8.1, DR-35)."""
        return_q = get_entity_edge_return_query(GraphProvider.FALKORDB)
        query = (
            "MATCH (n:Entity)-[e:RELATES_TO]->(m:Entity)\n"
            "WHERE e.expired_at IS NOT NULL\n"
            "  AND e.expired_at >= $start_ts\n"
            "  AND e.expired_at <= $end_ts\n"
            "RETURN\n" + return_q
        )

        async def _fetch() -> list[ClientEdge]:
            records, _, _ = await self._driver.execute_query(
                query, start_ts=start_ts, end_ts=end_ts
            )
            return [_entity_edge_to_client_edge(entity_edge_from_record(r)) for r in records]

        return self._run(_fetch())

    def get_edge(self, uuid: str) -> ClientEdge:
        """Fetch one entity edge by UUID (spec §4.9a)."""
        async def _fetch() -> ClientEdge:
            e = await self._edge_ops.get_by_uuid(self._driver, uuid)
            return _entity_edge_to_client_edge(e)

        return self._run(_fetch())

    def search_edges(self, query: str, top_n: int, method: str) -> list[ClientEdge]:
        """Single-channel graphiti hybrid search over entity edges (spec §4.7a, DR-33; design §7).

        `method` is a graphiti EdgeSearchMethod value — one channel per call, so the recall
        service sees the DR-33 channels as INDEPENDENT retrievers (semantic vs keyword) rather
        than a pre-fused hybrid: 'cosine_similarity' = semantic vector search (bge-small),
        'bm25' = keyword full-text search over edge facts. Reranking is RRF (order-only, no
        cross-encoder call — cheap and channel-local). Returns created/current entity edges as
        ClientEdges, scoped to this client's group_id; the RecallService applies verdict-aware
        filtering (quarantined dropped) and the structural GRAPH channel downstream.
        """
        from graphiti_core.search.search_config import (  # noqa: PLC0415 — lazy: absent offline
            EdgeReranker,
            EdgeSearchConfig,
            EdgeSearchMethod,
            SearchConfig,
        )
        from graphiti_core.search.search_filters import SearchFilters  # noqa: PLC0415

        from genesys.graph.ontology import ALLOWED_EDGE_TYPES

        edge_method = EdgeSearchMethod(method)
        config = SearchConfig(
            edge_config=EdgeSearchConfig(
                search_methods=[edge_method],
                reranker=EdgeReranker.rrf,  # order-only fusion; no cross-encoder LLM call
            ),
            limit=top_n,
        )
        # BT-3 / D-GCW-7 (AC-R1, red-line): scope the graph query to the CLOSED allow-list so a
        # non-memory edge (e.g. a stray `perceives`/generic edge) is never retrieved. This is the
        # primary leak-guard; the RecallService also post-filters by type (defence-in-depth).
        edge_filter = SearchFilters(edge_types=sorted(ALLOWED_EDGE_TYPES))

        async def _search() -> list[ClientEdge]:
            results = await self._g.search_(
                query=query,
                config=config,
                group_ids=[self._group_id],
                search_filter=edge_filter,
            )
            return [_entity_edge_to_client_edge(e) for e in (results.edges or [])][:top_n]

        return self._run(_search())

    def set_edge_fields(self, uuid: str, **fields: object) -> None:
        """Update native temporal/text fields on an entity edge (spec §4.9a, DR-35).

        Handles: fact, valid_at, invalid_at, expired_at. Passes through as-is;
        graphiti uses ISO strings for temporal fields in FalkorDB.
        """
        # Build SET clauses for known native fields only
        allowed = {"fact", "valid_at", "invalid_at", "expired_at"}
        set_parts = []
        params: dict[str, Any] = {"uuid": uuid}
        for k, v in fields.items():
            if k not in allowed:
                continue
            param_key = f"val_{k}"
            set_parts.append(f"e.{k} = ${param_key}")
            params[param_key] = v

        if not set_parts:
            return

        query = (
            "MATCH (n:Entity)-[e:RELATES_TO {uuid: $uuid}]->(m:Entity)\n"
            "SET " + ", ".join(set_parts)
        )

        async def _update() -> None:
            await self._driver.execute_query(query, **params)

        self._run(_update())

    def set_edge_attributes(self, uuid: str, **attrs: object) -> None:
        """Merge custom Genesys attributes into the entity edge properties (spec §4.9a).

        Graphiti stores attributes as flat edge properties (SET e = edge_data merges them
        in; properties(e) returns them). We SET each attribute key individually so we do
        a targeted merge rather than a full edge rewrite.
        """
        if not attrs:
            return

        set_parts = []
        params: dict[str, Any] = {"uuid": uuid}
        for k, v in attrs.items():
            param_key = f"attr_{k}"
            # Serialize Enum values to their string value
            if hasattr(v, "value"):
                v = v.value
            set_parts.append(f"e.{k} = ${param_key}")
            params[param_key] = v

        query = (
            "MATCH (n:Entity)-[e:RELATES_TO {uuid: $uuid}]->(m:Entity)\n"
            "SET " + ", ".join(set_parts)
        )

        async def _update() -> None:
            await self._driver.execute_query(query, **params)

        self._run(_update())

    def add_typed_edge(self, src: str, dst: str, label: str) -> None:
        """Create a typed directed relationship between two episode/entity UUIDs (spec §4.6).

        Best-effort: uses a Cypher MERGE across any node type that carries the matching
        UUID so we don't need to know the label in advance. The relationship is labelled
        with the caller-supplied `label` (e.g. SUPERSEDES, LINKS_TO).
        """
        # Sanitise label: only word chars allowed in Cypher relationship types
        import re
        safe_label = re.sub(r"\W+", "_", label).upper()
        query = (
            f"MATCH (a {{uuid: $src}}), (b {{uuid: $dst}})\n"
            f"MERGE (a)-[:{safe_label} {{uuid: $edge_uuid}}]->(b)"
        )
        import uuid as _uuid
        edge_uuid = str(_uuid.uuid4())

        async def _create() -> None:
            await self._driver.execute_query(query, src=src, dst=dst, edge_uuid=edge_uuid)

        self._run(_create())

    def close(self) -> None:
        """Shut down the embedded driver and event loop (best-effort)."""
        async def _close() -> None:
            try:
                await self._driver.close()
            except Exception:
                pass

        try:
            self._run(_close())
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)


# ---------------------------------------------------------------------------
# Factory helper (called from factory.real_client)
# ---------------------------------------------------------------------------

def _fetch_api_key(env: Any) -> str:  # noqa: ANN401
    """Return the Anthropic API key from the environment dict or macOS Keychain.

    NEVER prints the key.
    """
    if env is not None and "ANTHROPIC_API_KEY" in env:
        return env["ANTHROPIC_API_KEY"]
    result = subprocess.run(
        ["security", "find-generic-password", "-a", "genesys",
         "-s", "ANTHROPIC_API_KEY", "-w"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def build_graphiti_client(
    *,
    db_path: str | None = None,
    env: Any = None,  # noqa: ANN401
    group_id: str | None = None,
) -> GraphitiCoreClient:
    """Construct a GraphitiCoreClient with an embedded FalkorDB instance.

    Uses the redislite Unix-socket bridge (identical to probe_extract.py).
    Builds graphiti indices/constraints on first use. API calls happen only
    during `add_episode`; construction itself is free.

    Per-workspace isolation is env-pinned and fail-loud (D-GCW-2): an unset
    ``db_path``/``group_id`` resolves from ``GENESYS_DB_PATH``/``GENESYS_GROUP_ID``
    and raises rather than opening an ephemeral /tmp graph (the former mkdtemp
    fallback was a silent data-loss trap).
    """
    from redislite import Redis
    from falkordb.asyncio import FalkorDB as AsyncFalkorDB

    from genesys.config import get_db_path, get_group_id

    # Resolve the persistent per-workspace store — NEVER an ephemeral /tmp graph.
    if db_path is None:
        db_path = str(get_db_path())
    if group_id is None:
        group_id = get_group_id()

    api_key = _fetch_api_key(env)

    # Start embedded Redis (redislite) — gives us a Unix socket
    redis_inst = Redis(db_path, decode_responses=True)
    sock_path = redis_inst.socket_file

    # Connect async FalkorDB to the Unix socket
    async_falkor = AsyncFalkorDB(unix_socket_path=sock_path)

    # Build FalkorDriver
    driver = FalkorDriver(falkor_db=async_falkor, database=group_id)

    # LLM client — R9 (D-GCW-8): low temperature for deterministic extraction. R5 (D-GCW-8): the
    # tiered wrapper routes small-tier calls to Haiku (graphiti-core ignores small_model upstream).
    from genesys.graph.model_tier import STANDARD_MODEL_DEFAULT, build_tiered_anthropic_client
    cfg = LLMConfig(api_key=api_key, model=STANDARD_MODEL_DEFAULT, temperature=0.0)
    llm = build_tiered_anthropic_client(cfg)

    # Graphiti instance
    embedder = FastEmbedEmbedder()
    cross_enc = NoOpCrossEncoder()

    g = Graphiti(
        llm_client=llm,
        embedder=embedder,
        cross_encoder=cross_enc,
        graph_driver=driver,
        store_raw_episode_content=True,
    )

    # Construct client first (starts the persistent daemon loop), then build
    # indices on THAT same loop so the async FalkorDB connection is never split
    # across two event loops (which would cause "Event loop is closed" errors).
    client = GraphitiCoreClient(g, driver, group_id=group_id)
    client._run(g.build_indices_and_constraints())

    # Keep redis alive (prevent GC) by attaching to client
    client._redis_inst = redis_inst  # type: ignore[attr-defined]
    client._async_falkor = async_falkor  # type: ignore[attr-defined]

    return client
