# Genesys

**A local-first, provider-agnostic memory engine for AI agents.**

Genesys turns a stream of agent conversations into durable, queryable memory. It
captures what was said, extracts the facts and commitments worth keeping, links them
into a **bi-temporal knowledge graph**, and gives the agent a disciplined way to
recall the right thing at the right moment — all on your own machine.

The assistant persona at the center of the engine is named **Daimon**.

---

## What it does

The pipeline is four stages:

1. **Capture** — a session transcript is mirrored into a scrubbed, memory-grade
   projection. Secrets and sensitive tokens are stripped *at capture time* by a
   deterministic scrubber, so nothing dangerous ever reaches durable storage.
2. **Extract** — the captured span is drained into candidate facts, traits, values,
   tasks, and commitments. Extraction workers screen, judge, and verify candidates
   before anything is committed.
3. **Knowledge graph** — surviving facts are linked into a **bi-temporal** graph:
   every edge knows both when it was *valid in the world* and when the system
   *learned* it. Supersession is first-class — new information doesn't overwrite old
   information, it dates it. You can ask what is true now, or what was believed as of
   any past moment.
4. **Recall** — a tiered retrieval service decides how hard to look based on the
   turn: trivial turns read nothing, anchored turns read the relevant episodes, and
   substantive turns run a full search. A read-fence keeps the agent's *perceptions*
   of the principal separate from durable fact.

### The two-record persona model

Genesys keeps two deliberately separate identity records:

- **The self-view (about the assistant)** — Daimon's own compiled identity: how she
  thinks, what she never does, her shared language with the principal. This record is
  blind to her opinions of the principal.
- **The perceived-view (about the principal)** — Daimon's inferred read of the
  principal, held on `perceives` edges. These are **permanently provisional**: no
  amount of evidence promotes a perception into a confirmed fact, and they never leak
  into the assistant's own identity or into the principal's constitution.

This separation is enforced structurally, not by convention — the perceived-view is
fenced out of both compilers by construction.

---

## Privacy posture

Genesys is built to run **on your machine, for you**:

- **Local-first.** The engine's core is file I/O plus deterministic processing.
  Nothing about your memory has to leave your machine.
- **Telemetry-off.** There is no phone-home, no analytics, no usage beacon. The
  offline test suite runs with the network physically disabled.
- **Secrets scrubbed at the door.** A deterministic redaction pass removes API keys,
  tokens, and other secrets during capture, before anything is persisted. Redaction
  tombstones are keyed (HMAC) so they prove *what was there* without becoming a
  lookup oracle.
- **Provider-agnostic.** LLM and graph backends are injected behind interfaces. The
  whole engine is exercisable offline with fake backends; live providers
  (Anthropic, a graph store) are optional extras you opt into.

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

Genesys is owner-agnostic. Who the memory is *for* (the **principal**) and what the
assistant is *called* (the **assistant**, default `Daimon`) are configuration, not
code. Run the one-time setup to record them:

```sh
genesys-setup
```

```
Genesys setup — tell me who this memory is for.
(Press Enter to accept the default shown in brackets.)

Your name (the principal) [Principal]: Ada
Assistant name [Daimon]:
Saved. Principal = 'Ada', assistant = 'Daimon'.
Config written to ~/.genesys/config.json.
```

You can also set these non-interactively:

```sh
genesys-setup --principal "Ada" --assistant "Daimon"
```

Or via environment variables (which always win over the config file):

```sh
export GENESYS_PRINCIPAL="Ada"
export GENESYS_ASSISTANT="Daimon"
```

Point the engine at a data root for its owned files and ledger:

```sh
export GENESYS_DATA="$HOME/.genesys/data"
```

### Console scripts

| Command           | Purpose                                             |
|-------------------|-----------------------------------------------------|
| `genesys-setup`   | One-time identity prompt (principal + assistant).   |
| `genesys-capture` | Mirror a transcript into a scrubbed projection.     |
| `genesys-save`    | Append a durable ledger entry.                      |
| `genesys-diary`   | Compile the recent-days briefing.                   |
| `genesys-drain`   | Drain captured spans into extraction (fixtures).    |
| `genesys-worker`  | Live extraction worker (real graph/LLM — opt-in).   |
| `genesys-tasks`   | Inspect the event-sourced task store.               |
| `genesys-hook`    | Claude Code hook entry point (reads hook JSON).     |
| `genesys-backfill`| Backfill discovery over existing data.              |
| `genesys-console` | Console dashboard.                                  |

---

## Configuration

All configuration comes from the environment (12-Factor), with a small setup-written
config file for identity:

| Variable                 | Meaning                                                        |
|--------------------------|----------------------------------------------------------------|
| `GENESYS_DATA`           | Data root for owned files + the ledger. **Required** at runtime.|
| `GENESYS_PRINCIPAL`      | Who the memory is for. Overrides the config file.              |
| `GENESYS_ASSISTANT`      | Assistant persona name (default `Daimon`).                     |
| `GENESYS_CONFIG`         | Override the config-file location (default `~/.genesys/config.json`). |
| `GENESYS_LOCAL_HMAC_KEY` | Keyed HMAC for redaction tombstones. Never commit or log it.   |

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

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Ctesibius-AI.
