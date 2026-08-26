# Genesis — Mechanism Reference

*Regenerated from source (Round D, D-A). Every table below is transcribed from the module named as
its **source of truth** — not hand-written prose. If the code and this page ever disagree, the code
wins; fix this page.*

---

## The pipeline

`Capture → Extract → Knowledge graph → Recall`, single-writer, file-backed.

1. **Capture** (`capture/mirror.py`) — a transcript is mirrored into two projections (memory-grade =
   clean facts; flight-recorder = fuller tool I/O). The DR-38 scrubber runs on **both** projections
   *before the first byte hits disk*.
2. **Extract** (`extraction/`) — `/save`'d content is drained: Analyst prepares the owned span →
   Grapher feeds `add_episode` → the Supervisor screens/gates/judges → the ledger entry is marked
   done. Serial FIFO under a single-instance lock.
3. **Knowledge graph** (`graph/`) — surviving facts are bi-temporal edges (valid-time + transaction-
   time); supersession dates old facts rather than overwriting them.
4. **Recall** (`recall/`) — a tiered, allow-list-scoped, verdict-gated, honest-empty read.

---

## Ontology — the 8 named memory relations
*Source of truth: `graph/ontology.py` `EDGE_DEFINITIONS` (mirrors D-GCW-14). `recall.allowlist`
imports `ALLOWED_EDGE_TYPES` from here — the same set is the closed recall leak-guard.*

| Relation | Domain (subject) | Range (object) |
|----------|------------------|----------------|
| `WORKS_ON` | Person | Project |
| `MEMBER_OF` | Person | Organization |
| `ASSIGNED` | Person | Task |
| `BLOCKS` | Task | Task |
| `PART_OF` | Task, Artifact | Project |
| `ABOUT` | Decision | Project, Artifact, Task |
| `PRODUCED` | Agent, Person | Artifact |
| `PARTICIPATED_IN` | Agent, Person | Session |

An edge whose type is **not** one of these eight is excluded from recall by construction (fail-closed).
There is no persona/profiling relation — recall never returns a "read of the principal."

---

## Enums
*Source of truth as noted. These are the real values — not `YES` / `SKIPPED` / `PENDING` (which do not
exist as ledger states).*

**Extraction state** — `ledger/entry.py::Extracted`
| Value | Meaning |
|-------|---------|
| `no` | queued: not yet extracted |
| `in-progress` | being drained (a crash leaves it here; the doctor re-queues it → `no`) |
| `done` | extracted into the graph |

**Trust verdict** — `graph/engine.py::Verdict`
| Value | Meaning |
|-------|---------|
| `provisional` | born here; served **labelled `[unverified]`** = *not yet gated* |
| `confirmed` | the gate passed it (D-FB-3); served clean |
| `quarantined` | never served as truth |

**Recall tier** — `recall/tier.py::Tier`
| Value | Reads |
|-------|-------|
| `none` | trivial turn — no read |
| `episodic` | the touched episode's facts |
| `deep` | self-view identity + episodic + errors (self-view only, §9.1) |
| `full` | the DR-33 three-channel search |

**Empty cause** — `recall/scorer.py::EmptyCause`
| Value | Meaning |
|-------|---------|
| `absent` | all three channels genuinely empty — earned nothing |
| `pending` | matched a just-saved, not-yet-extracted entry (queue lag) — **not** absence |
| `degraded` | recall/store is DOWN (AC-R2) — down ≠ empty; never confabulate |

---

## Recall scoring — graded corroboration
*Source of truth: `recall/scorer.py` `_SCORE`. Corroboration count (how many of the three channels —
semantic, keyword, graph — hit) maps to a score+label that travels into the injected result:*

| Channels hit | Score | Label |
|--------------|-------|-------|
| 3 | 100 | `answer` |
| 2 | 70 | `corroborated-partial` |
| 1 | 30 | `weak/single-source` |
| 0 | 0 | `honest-empty` |

**Serving labels (post-D-FB-3):** quarantined is **never served**; not-yet-gated is served **labelled
`[unverified]`**; gated-and-passed (`confirmed`) is served **clean**; contested is served `[contested]`.
`[unverified]` means exactly "not yet gated" — a signal, not noise.

**Drop-visibility (AC-DROP1):** every recall result carries a cumulative `drop_count` — how many edges
recall excluded as non-allow-listed — surfaced in the MCP payload for auditability.

---

## Session-start confirmation line
*Source of truth: `hooks/confirmation.py`. Verbatim strings:*

| State | Line |
|-------|------|
| memories present | `Genesis: memory loaded — {n} recent sessions` |
| captured but unsaved | `Genesis: this session's capture is unsaved — run /save to remember it` |
| genuinely empty | `Genesis: no memories yet` |

The **unsaved** line is D-GCW-18's guarantee: when the WAL holds captured-but-unsaved content, the line
never claims "no memories."

---

## Diary briefing — drop-order under a token budget
*Source of truth: `diary/briefing.py` `_DROP_ORDER` / `_NEVER_DROP`. When the recent-days briefing
exceeds its token budget, whole sections are dropped left-to-right in this order:*

`TOP OF MIND → RECENT SESSIONS → OPEN THREADS`

Two sections are **never dropped** (`_NEVER_DROP`): **COMMITMENTS** and **OPEN QUESTIONS** — *deadlines
are never buried; clarifications are never lost.*

---

## Hook wiring (Claude Code)
*Source of truth: `hooks/wiring.py` + `install/installer.py`. The installer writes ONLY to
`<workspace>/.claude/settings.json` (project-local, never `~/.claude`).*

- **Events wired** (`GENESIS_EVENTS`): `SessionStart`, `Stop`, `SessionEnd`, `PreCompact`.
- **Hook object** (per event): `{"hooks": [{"type": "command", "command": "python3 -m genesis.hooks.cli"}]}`
  — no `timeout` field; the env (`GENESIS_DATA` / `GENESIS_DB_PATH` / `GENESIS_GROUP_ID`) lives in a
  separate `settings["env"]` block, never baked into the command string.
- **Recall MCP** (`.mcp.json`): `{"command": "python3", "args": ["-m", "genesis.recall.mcp_server"], "env": {…}}`.
- Foreign hooks (e.g. a `Stop → response_validator.py`) are preserved on install and survive uninstall.
