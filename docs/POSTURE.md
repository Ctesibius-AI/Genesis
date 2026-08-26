# Genesis — Posture & Guarantees

*Hand-written (Round D, D-C): these are the design-posture statements a source-generator cannot write.
They describe ratified decisions and the honest current state — not aspirations. The owner attestation
below is the owner's own ratified words.*

---

## Who holds the pen (F-13.2)

> **The machine holds the pen; the model holds the judgment; the journal watches both.**

Every change to memory is *executed* by deterministic code, *decided* by the model within fixed rails,
and *recorded* in an append-only journal. No LLM writes to the graph directly.

| Operation | Model's role (judgment) | Machine's role (the pen) | Journal |
|-----------|-------------------------|--------------------------|---------|
| **create** | extracts candidate facts from the owned span | `add_episode` commits typed edges, born `provisional` | `verdict` (provisional) |
| **amend** | the Verifier proposes corrected text on a flagged fact | code applies it via `write_fact` (fenced: never rewrites a persona anchor) | `gate-resolve after=amended`, **with the before-text** |
| **retire** | the Supervisor rules a fact superseded/invalidated | code sets `superseded_by` / dates the edge; recall drops it | `verdict` / supersession entry |

Promotion to `confirmed` and quarantine are likewise machine-executed on the model's gate ruling
(D-FB-3), each journaled.

---

## Persona layer — the definitive statement (F-28.1)

A persona/profiling layer **existed** in an earlier design, was **removed** (D-GCW-6 / BT-4b), and recall
is now decoupled from it behind **six guards** (no `persona` import in recall; a closed allow-list;
quarantine-drop; invalidation-drop; self-view-only DEEP tier; no `ReleaseContext`). Genesis stores
**facts, decisions, tasks, entities** — never a profile of the user, and recall returns none. A gated,
opt-in persona **could** return only as a roadmap module behind explicit consent; it is not in this build.

> **Owner attestation:** _I attest as the project owner: the persona profiler was removed from Genesis
> before its open-source publication (D-GCW-6 / BT-4b), no maintained variant of Genesis retains it, and
> it exists only in private development history. Any future persona capability would ship as a separate,
> explicitly opt-in module — never as dormant code in this build._

---

## Described-but-not-live

Honest about what is documented but not yet running (updated for reality — the **recall daemon is LIVE
since v1.2**, so it has left this list):

- Automatic task capture (task-lifecycle feeds).
- Commitments / open-questions feeds.
- Capture timestamps (currently stubbed — F-03.5, a Pythia-plan dependency).
- The orchestration layer (agent-SDK / langgraph) — an opt-in extra, not the core path.

The Haiku small-tier wrapper is **live**, now ceiling-pinned (`graphiti-core<0.30`) and signature-guarded
(D-FB-6-adjacent F-12.4): on upstream signature drift it warns loudly and falls back to the standard
model — never a silent downgrade.

---

## Retention (D-FB-7)

- The WAL flight-recorder is **permanent by design** — it is the durable capture of record.
- `genesis-prune` is **backlog, owner-invoked only** — never automatic. When built it prunes
  flight-recorder content older than an owner-named date and **never** touches the ledger, graph, or
  journal.

---

## How memory is saved (D-GCW-18) — the /save call-to-action

`/save` is the **sole materialization path** in v1. Ordinary sessions are always *captured* (mirrored to
the WAL on `Stop`/`SessionEnd`/`PreCompact`, so nothing is lost) but stay unmaterialized until you run
`/save`. The honest framing:

> **Captured, safe, waiting for YOUR `/save` — nothing processes it automatically.**

The session-start line says so (`…this session's capture is unsaved — run /save…`), never "no memories."
Automatic extraction of ordinary sessions is a planned future change.

---

## Never-drop

Deadlines are never buried; clarifications are never lost. Commitments and open questions are first-class
— the system's job is to surface them at the right moment, not to let them decay into an unread log.

---

## Project-local wiring guarantee (AC-ISO2)

Genesis hooks are written **only** to `<workspace>/.claude/settings.json` — never `~/.claude`, never
another project. Installing in one workspace touches nothing global and nothing in a sibling workspace.
This is a red-line guarantee, not a default: it is enforced and tested, and it is the feature that lets
you trust Genesis in one project without it reaching into the rest of your machine.

---

## Operator notes

- **Platform floor:** Apple-Silicon macOS 15+ is the native, "Mac-easy" path — *Mac-easy, not Mac-only*.
  A Docker path exists for other platforms (manual). Windows path-masking is **out of scope** (POSIX-only).
- **Keys:** the live worker reads `ANTHROPIC_API_KEY` from the macOS **Keychain** (account `genesis`);
  other platforms use the **env-var** fallback. The redaction key `GENESIS_LOCAL_HMAC_KEY` is offered at
  `genesis-setup` (D-FB-4) — printed once, stored by you, never persisted by Genesis.
- **Console:** localhost, no-auth (D-QA-7); read-only except for comments (D-QA-4).
- **Env canon:** `GENESIS_DATA` is the sole data-root variable; the legacy `GENESIS_DATA_ROOT` is
  accepted for **one release** with a deprecation warning, then removed (D-FB-2).
- **Masking scope:** home-path masking rewrites `/Users/<name>` and `/home/<name>` to `~` (D-FB-5). It
  covers **paths**, not a bare-name mention in prose.

---

## Privacy positives

- **The model never sees the flight-recorder.** Only the clean memory-grade projection reaches the model.
- **Scrub before the model.** Secrets are stripped at the capture door, before anything is persisted or
  sent to a provider. Redaction fingerprints are **keyed** (HMAC) when a key is set and **omitted** when
  not — never an unkeyed confirm-a-guess oracle (D-FB-6).
- **Graded corroboration travels.** Recall's honesty labels (`[unverified]`, `[contested]`, the
  30/70/100 corroboration score) reach the caller — you always know how well-supported an answer is.
- **The save reason is findable.** What you `/save`d is findable in the diary; recall finds what was said.

---

## Installer notes

- Hooks **pin `sys.executable`** (F-27.5) so the wired command runs under the same interpreter that
  installed Genesis — no PATH ambiguity.
- Every live door (worker, drain, save fast-path, recall MCP) resolves its store via **canonical config**
  (`GENESIS_DB_PATH`, fail-loud; `GENESIS_DATA`) — one path law, no local defaults (graph-harness T1).
- First run offers to generate the redaction key (D-FB-4); capture works without one (fingerprints are
  simply omitted until a key is set).
