"""DR-37 capture-mirror logic (spec v1.5 §4.2a).

Turns a stream of transcript events into the two owned projections:

  | Projection      | Contents                                                      | Consumer   |
  |-----------------|---------------------------------------------------------------|------------|
  | Flight recorder | full: user msgs + Daimon visible replies + THINKING blocks +  | QA / dev   |
  |                 | actions/tool I/O + task events                                |            |
  | Memory-grade    | clean: dialogue + actions + STATED intent + task events       | extraction |

Rules honored from §4.2a / DR-37:
  - Excludes Anthropic system prompts + harness plumbing (git snapshots, token counts,
    injected CLAUDE.md). Only content authored by the principal or Daimon is kept.
  - Thinking blocks go to the flight recorder ONLY (kept for QA/dev inspection, never
    treated as truth). They are excluded from the memory-grade projection.
  - Stated intent = tool `description` + Daimon's visible narration — NOT thinking.
  - PostToolUse -> action-log entry (tool_name + tool_input + tool_response) with intent.
  - TaskCreated / TaskCompleted -> first-class task-lifecycle events (both projections).

⚠ The DR-38 scrubber runs on BOTH projections BEFORE the first byte hits disk (§4.2b.1).
This module applies the scrubber to every event it emits; the CLI is what would write to
disk, and it only ever sees already-scrubbed content.

This is *logic only*: no live hook, no reading of a real transcript. Input is a list of
already-parsed events (from fixtures). See ``genesis.capture.cli``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, List, Optional

from genesis.scrub.scrubber import ScrubMatch, path_is_sensitive, scrub_text


# --------------------------------------------------------------------------- #
# Input event model                                                            #
# --------------------------------------------------------------------------- #

# Event "type" values Genesis recognizes. These map onto the harness transcript /
# hook surface described in §4.2a. Anything not authored by the principal or Daimon is excluded.
class EventType(str, Enum):
    USER = "user"  # the principal's prompt (visible dialogue)
    ASSISTANT_TEXT = "assistant_text"  # Daimon's visible reply
    ASSISTANT_THINKING = "assistant_thinking"  # Daimon's thinking block (flight only)
    TOOL_USE = "tool_use"  # PostToolUse: tool_name + tool_input + tool_response
    TASK_CREATED = "task_created"  # TaskCreated
    TASK_COMPLETED = "task_completed"  # TaskCompleted

    # --- Harness plumbing / Anthropic system content: EXCLUDED (§4.2a) ---
    SYSTEM_PROMPT = "system_prompt"  # Anthropic system prompt — excluded
    HARNESS = "harness"  # git snapshots, token counts, injected CLAUDE.md — excluded


# The set of event types that are harness plumbing / system content and must never land
# in either projection (§4.2a "Excluded").
HARNESS_EXCLUDED_TYPES = frozenset(
    {EventType.SYSTEM_PROMPT, EventType.HARNESS}
)


@dataclass(frozen=True)
class TranscriptEvent:
    """One parsed transcript/hook event (already extracted from the harness `.jsonl`).

    Not every field is set for every type:
      - USER / ASSISTANT_TEXT / ASSISTANT_THINKING: ``text`` carries the content.
      - TOOL_USE: ``tool_name``, ``tool_input``, ``tool_response`` set; ``text`` holds
        Daimon's visible narration (stated intent), ``description`` the tool description.
      - TASK_*: ``text`` holds a task label; ``task_id`` correlates create/complete.
    """

    type: EventType
    text: Optional[str] = None
    author: Optional[str] = None  # "principal" | "daimon" (informational)
    tool_name: Optional[str] = None
    tool_input: Optional[str] = None
    tool_response: Optional[str] = None
    description: Optional[str] = None  # tool description -> part of stated intent
    task_id: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "TranscriptEvent":
        return cls(
            type=EventType(d["type"]),
            text=d.get("text"),
            author=d.get("author"),
            tool_name=d.get("tool_name"),
            tool_input=d.get("tool_input"),
            tool_response=d.get("tool_response"),
            description=d.get("description"),
            task_id=d.get("task_id"),
        )


# --------------------------------------------------------------------------- #
# Output projection model                                                      #
# --------------------------------------------------------------------------- #

class ProjectionKind(str, Enum):
    FLIGHT_RECORDER = "flight_recorder"
    MEMORY_GRADE = "memory_grade"


@dataclass
class ProjectionEntry:
    """One emitted, already-scrubbed entry in a projection."""

    kind: str  # e.g. "dialogue.user", "thinking", "action", "task.created"
    content: str  # scrubbed
    meta: dict = field(default_factory=dict)


@dataclass
class Projection:
    kind: ProjectionKind
    entries: List[ProjectionEntry] = field(default_factory=list)


@dataclass
class CaptureResult:
    flight_recorder: Projection
    memory_grade: Projection
    scrub_matches: List[ScrubMatch] = field(default_factory=list)

    @property
    def redacted_anything(self) -> bool:
        return bool(self.scrub_matches)


# --------------------------------------------------------------------------- #
# Core logic                                                                   #
# --------------------------------------------------------------------------- #

def _scrub(text: Optional[str], sink: List[ScrubMatch]) -> str:
    """Scrub text (DR-38) before it can be written; accumulate matches."""
    if not text:
        return ""
    res = scrub_text(text)
    sink.extend(res.matches)
    return res.text


def _stated_intent(ev: TranscriptEvent) -> str:
    """Stated intent for a tool action = tool description + visible narration.

    Explicitly NOT thinking (§4.2a: intent comes from the tool `description` + Daimon's
    visible narration — *not* thinking).
    """
    parts = [p for p in (ev.description, ev.text) if p]
    return " — ".join(parts)


def mirror_events(events: Iterable[TranscriptEvent | dict]) -> CaptureResult:
    """Produce the two DR-37 projections from a sequence of transcript events.

    Applies the DR-38 scrubber to every emitted piece of content BEFORE it is placed in
    a projection (both projections). Excludes Anthropic system prompts + harness plumbing.
    Thinking goes to the flight recorder only.
    """
    flight = Projection(ProjectionKind.FLIGHT_RECORDER)
    memory = Projection(ProjectionKind.MEMORY_GRADE)
    matches: List[ScrubMatch] = []

    for raw in events:
        ev = raw if isinstance(raw, TranscriptEvent) else TranscriptEvent.from_dict(raw)

        # --- Exclusions (§4.2a): system prompts + harness plumbing never land. ---
        if ev.type in HARNESS_EXCLUDED_TYPES:
            continue

        if ev.type == EventType.USER:
            content = _scrub(ev.text, matches)
            entry = ProjectionEntry("dialogue.user", content, {"author": "principal"})
            flight.entries.append(entry)
            memory.entries.append(entry)

        elif ev.type == EventType.ASSISTANT_TEXT:
            content = _scrub(ev.text, matches)
            entry = ProjectionEntry("dialogue.assistant", content, {"author": "daimon"})
            flight.entries.append(entry)
            memory.entries.append(entry)

        elif ev.type == EventType.ASSISTANT_THINKING:
            # Flight recorder ONLY — never in memory-grade (kept for QA/dev, not truth).
            content = _scrub(ev.text, matches)
            flight.entries.append(
                ProjectionEntry("thinking", content, {"author": "daimon", "truth": False})
            )

        elif ev.type == EventType.TOOL_USE:
            intent = _scrub(_stated_intent(ev), matches)
            tool_input = _scrub(ev.tool_input, matches)
            tool_response = _scrub(ev.tool_response, matches)
            sensitive = path_is_sensitive(ev.tool_input or "")

            meta = {
                "tool_name": ev.tool_name,
                "stated_intent": intent,
                "sensitive_surface": sensitive,
            }
            # Flight recorder keeps full tool I/O (higher toxicity, QA/dev value).
            flight.entries.append(
                ProjectionEntry(
                    "action",
                    tool_response,
                    {**meta, "tool_input": tool_input},
                )
            )
            # Memory-grade keeps the action + stated intent, not raw tool I/O dumps.
            memory.entries.append(
                ProjectionEntry("action", intent, meta)
            )

        elif ev.type == EventType.TASK_CREATED:
            content = _scrub(ev.text, matches)
            entry = ProjectionEntry(
                "task.created", content, {"task_id": ev.task_id}
            )
            flight.entries.append(entry)
            memory.entries.append(entry)

        elif ev.type == EventType.TASK_COMPLETED:
            content = _scrub(ev.text, matches)
            entry = ProjectionEntry(
                "task.completed", content, {"task_id": ev.task_id}
            )
            flight.entries.append(entry)
            memory.entries.append(entry)

        else:  # pragma: no cover - defensive; EventType is exhaustive above
            raise ValueError(f"unhandled event type: {ev.type!r}")

    return CaptureResult(
        flight_recorder=flight,
        memory_grade=memory,
        scrub_matches=matches,
    )


# --------------------------------------------------------------------------- #
# Projection text helpers (shared by adapter and wal.courier)                  #
# --------------------------------------------------------------------------- #

def memory_grade_text_from_result(capture_result: CaptureResult) -> str:
    """Join the memory-grade projection text (clean, scrubbed).

    Moved here from hooks.adapter to break the adapter↔courier circular import.
    """
    entries = capture_result.memory_grade.entries
    if not entries:
        return ""
    return "\n".join(e.content for e in entries if e.content)


def flight_span_from_result(capture_result: CaptureResult) -> str:
    """Join the flight-recorder projection text (full incl. thinking).

    Moved here from wal.courier to keep both span helpers co-located.
    """
    entries = capture_result.flight_recorder.entries
    return "\n".join(e.content for e in entries if e.content)
