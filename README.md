# Genesis

**A local-first, provider-agnostic memory engine for AI agents.**

Genesis turns a stream of agent conversations into durable, queryable memory. It
captures what was said, extracts the facts and commitments worth keeping, links them
into a **bi-temporal knowledge graph**, and gives the agent a disciplined way to
recall the right thing at the right moment — all on your own machine.

The assistant is named **Daimon** (configurable).

---

## What it does

The pipeline is four stages:

1. **Capture** — a session transcript is mirrored into a scrubbed, memory-grade
   projection. Secrets and sensitive tokens are stripped *at capture time* by a
   deterministic scrubber, so nothing dangerous ever reaches durable storage.
2. **Extract** — the captured span is drained into candidate facts, decisions, tasks,
   and commitments. Extraction workers screen, judge, and verify candidates before
   anything is committed.
3. **Knowledge graph** — surviving facts are linked into a **bi-temporal** graph:
   every edge knows both when it was *valid in the world* and when the system
   *learned* it. Supersession is first-class — new information doesn't overwrite old
   information, it dates it. You can ask what is true now, or what was believed as of
   any past moment.
4. **Recall** — a tiered retrieval service decides how hard to look based on the
   turn: trivial turns read nothing, anchored turns read the relevant episodes, and
   substantive turns run a full search. Recall is scoped to a **closed allow-list** of
   named memory relations, so it returns facts, decisions, tasks, and the like — and
   **never a read of *you***.

### Memory-only — never a read of you

Genesis stores **facts, decisions, tasks, and entities** — not a profile of the user.
There is no persona/profiling layer in this build: recall is guarded by a fail-closed
allow-list of the named memory relations, so an edge that isn't one of those is
excluded by construction rather than surfaced as a "read" of the principal.

### How memory is saved (v1)

In v1, **`/save` is the trigger that materializes memory.** Ordinary sessions are always
*captured* — the transcript is mirrored into the WAL on `Stop`/`SessionEnd`/`PreCompact`,
so nothing is lost — but that captured content stays raw until you run **`/save`** (or
`genesis-save-moment`), which extracts it into the knowledge graph. Until then the
session-start line reports *"this session's capture is unsaved — run `/save` to remember
it"* rather than claiming there are no memories. Any `/save`'d-but-not-yet-extracted
content is also drained (bounded) at the next session start.

*Automatic extraction of ordinary sessions (no `/save` needed) is a planned future change.*

---

## Privacy posture

Genesis is built to run **on your machine, for you**:

- **Local-first.** The engine's core is file I/O plus deterministic processing.
  Nothing about your memory has to leave your machine.
- **Telemetry-off.** There is no phone-home, no analytics, no usage beacon. The
  offline test suite runs with the network physically disabled.
- **Secrets scrubbed at the door.** A deterministic redaction pass removes API keys,
  tokens, and other secrets during capture, before anything is persisted. Placeholder
  fingerprints are **keyed** (HMAC) when a local key is set and **omitted** when not —
  never an unkeyed hash that could confirm a guess. Redaction tombstones are likewise
  keyed.
- **Usernames masked at capture.** Home-directory paths (`/Users/<name>`, `/home/<name>`)
  are rewritten to `~` at the capture door, so your username never reaches the store or
  the model. (Covers paths, not bare-name mentions; POSIX-only.)
- **The model never sees the flight recorder.** Only the clean memory-grade projection
  reaches the model; the fuller flight-recorder projection stays local.
- **Provider-agnostic.** LLM and graph backends are injected behind interfaces. The
  whole engine is exercisable offline with fake backends; live providers
  (Anthropic, a graph store) are optional extras you opt into.

### What recall serves, and how it's labelled

Recall is **quarantine-gated, invalidation-gated, and allow-list-scoped** — not
confirmation-gated. So: **quarantined** facts are never served; **not-yet-gated** facts
are served **labelled `[unverified]`** (meaning exactly "not yet gated"); **gated-and-passed**
facts are served clean; **contested** facts carry `[contested]`. You always see how
well-supported an answer is (a graded 100/70/30 corroboration score travels with it).

> **Reference docs:** [Mechanism reference](docs/MECHANISM.md) (ontology, enums, scoring —
> regenerated from source) · [Posture & guarantees](docs/POSTURE.md).

---

## Install

Requires **Python 3.12+**.

```sh
pip install .
# optional extras:
pip install ".[llm]"            # live Anthropic backend
pip install ".[graph]"         # graphiti + FalkorDB graph engine
pip install ".[orchestration]" # agent-SDK / langgraph orchestration
pip install ".[web]"           # console web server
pip install ".[dev]"           # pytest
```

## Quickstart

Genesis is owner-agnostic. Who the memory is *for* (the **principal**) and what the
assistant is *called* (the **assistant**, default `Daimon`) are configuration, not
code. Run the one-time setup to record them:

```sh
genesis-setup
```

```
Genesis setup — tell me who this memory is for.
(Press Enter to accept the default shown in brackets.)

Your name (the principal) [Principal]: Ada
Assistant name [Daimon]:
Saved. Principal = 'Ada', assistant = 'Daimon'.
Config written to ~/.genesis/config.json.
```

You can also set these non-interactively:

```sh
genesis-setup --principal "Ada" --assistant "Daimon"
```

Or via environment variables (which always win over the config file):

```sh
export GENESIS_PRINCIPAL="Ada"
export GENESIS_ASSISTANT="Daimon"
```

Point the engine at a data root for its owned files and ledger:

```sh
export GENESIS_DATA="$HOME/.genesis/data"
```

### Console scripts

| Command           | Purpose                                             |
|-------------------|-----------------------------------------------------|
| `genesis-setup`   | One-time identity prompt (principal + assistant).   |
| `genesis-capture` | Mirror a transcript into a scrubbed projection.     |
| `genesis-save`    | Append a durable ledger entry.                      |
| `genesis-diary`   | Compile the recent-days briefing.                   |
| `genesis-drain`   | Drain captured spans into extraction (fixtures).    |
| `genesis-worker`  | Live extraction worker (real graph/LLM — opt-in).   |
| `genesis-tasks`   | Inspect the event-sourced task store.               |
| `genesis-hook`    | Claude Code hook entry point (reads hook JSON).     |
| `genesis-backfill`| Backfill discovery over existing data.              |
| `genesis-console` | Console dashboard.                                  |
| `genesis-save-moment` | Materialize the current `/save` window into memory. |
| `genesis-install` | Wire a workspace (project-local hooks + recall MCP + `/save`). |
| `genesis-recall-mcp` | Recall MCP server (read-only, allow-list-scoped).   |

---

## Configuration

All configuration comes from the environment (12-Factor), with a small setup-written
config file for identity:

| Variable                 | Meaning                                                        |
|--------------------------|----------------------------------------------------------------|
| `GENESIS_DATA`           | Data root for owned files + the ledger. **Required** at runtime.|
| `GENESIS_PRINCIPAL`      | Who the memory is for. Overrides the config file.              |
| `GENESIS_ASSISTANT`      | Assistant name (default `Daimon`).                             |
| `GENESIS_CONFIG`         | Override the config-file location (default `~/.genesis/config.json`). |
| `GENESIS_LOCAL_HMAC_KEY` | Keyed HMAC for redaction tombstones **and** placeholder fingerprints (D-FB-6): when set, redaction fingerprints are keyed; when unset, they are omitted (never an unkeyed confirm-a-guess hash). `genesis-setup` offers to generate it (printed once, stored by you — never persisted by Genesis). On macOS the live worker reads the Anthropic key from the Keychain (account `genesis`); other platforms use the env var. Never commit or log it. |

---

## Development

A no-network Docker sandbox runs the full offline suite without installing Python on
your host:

```sh
./sandbox build   # build the image (one-time)
./sandbox test    # run the offline test suite
./sandbox shell   # drop into a shell at /workspace
```

The sandbox runs with `network_mode: none` and mounts only this repository — live
capture and live providers are separate, explicit, opt-in steps.

---

## Known limitations

- **Session-start memory line — Claude Code CLI only (VS Code extension hides it).** On session
  start Genesis shows a one-line memory-state confirmation (e.g. `Genesis: memory loaded — 3 recent
  sessions`). It is delivered via the SessionStart hook's `systemMessage` field — the correct,
  user-visible channel in the **Claude Code CLI** (rendered as `SessionStart:startup says: …`). The
  **VS Code extension currently ignores** SessionStart `systemMessage` (upstream Claude Code bug
  [#15344](https://github.com/anthropics/claude-code/issues/15344)), so the line does not appear
  there. Memory itself is unaffected — only the visibility of the confirmation line. Accepted for v1
  as a documented limitation (waiver **W-GCW-1**), not a mechanism change.
  *Fast-follow: revisit AC-CONF1 delivery when CC #15344 closes.*

---

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Ctesibius-AI.
