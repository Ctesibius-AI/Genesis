"""Translate Claude Code .jsonl transcript records into Genesys capture event dicts.

Spec references:
  - F-GENESYS-03 (provisional summary ruling): the live save-ritual heuristic is
    undesigned. PROVISIONAL: summary = last visible assistant_text in the transcript,
    falling back to last user message, falling back to "". This is a documented
    provisional choice pending F-GENESYS-03 design.
  - §4.2a / DR-37 (capture-mirror event types): maps CC records to the types that
    mirror_events() understands.

Claude Code transcript format assumptions (validate against a real transcript):
  - Top-level records are JSON lines with a "type" field: "user" or "assistant".
  - "user" records: message.content is either a plain string or a list of blocks.
    Regular user messages have role="user" with a plain string or text blocks.
    Tool results arrive as user records with content=[{"type":"tool_result",...}].
  - "assistant" records: message.content is a list of blocks with types "text",
    "thinking", "tool_use".
  - tool_use blocks have: {"type":"tool_use","name":<str>,"input":<dict>,"id":<str>}.
  - tool_result blocks (in user messages) have: {"type":"tool_result",
    "tool_use_id":<str>,"content":<str or list>}.
  - Unknown shapes are silently skipped (never crash).
"""

from __future__ import annotations

import json
from typing import Any


def _extract_text_from_content(content: str | list[Any]) -> str:
    """Extract plain text from a content value that may be a string or list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p)
    return ""


def _tool_result_map(records: list[dict]) -> dict[str, str]:
    """Build a map from tool_use_id -> tool result content for pairing.

    Scans all records for user messages that carry tool_result blocks.
    """
    result: dict[str, str] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if rec.get("type") != "user":
            continue
        msg = rec.get("message", {})
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_result":
                continue
            tool_use_id = block.get("tool_use_id", "")
            raw = block.get("content", "")
            if isinstance(raw, list):
                # content may be a list of text blocks
                raw = "\n".join(
                    b.get("text", "") for b in raw
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            if tool_use_id:
                result[tool_use_id] = str(raw) if raw is not None else ""
    return result


def cc_transcript_to_events(records: list[dict]) -> list[dict]:
    """Map Claude Code transcript .jsonl records to Genesys capture event dicts.

    Genesys event dict keys (matching TranscriptEvent.from_dict expectations):
      type, text, author, tool_name, tool_input, tool_response

    Mapping rules (spec §4.2a / DR-37):
      - user text message       → {type:"user", text, author:"principal"}
      - assistant text block    → {type:"assistant_text", text, author:"daimon"}
      - assistant thinking block → {type:"assistant_thinking", text, author:"daimon"}
      - assistant tool_use block → {type:"tool_use", tool_name, tool_input:<json str>,
                                    tool_response:<str>, author:"daimon"}
      - tool_result user records → consumed for pairing, not emitted as their own events
      - task_created/task_completed record → forwarded verbatim (DR-37 first-class task
                                    events, §4.2a); mirror_events turns them into task.*
                                    projection entries
      - system/meta records      → skipped
      - unknown shapes           → skipped, never crash
    """
    tool_responses = _tool_result_map(records)
    events: list[dict] = []

    for rec in records:
        if not isinstance(rec, dict):
            continue

        rtype = rec.get("type", "")

        if rtype == "user":
            msg = rec.get("message", {})
            if not isinstance(msg, dict):
                continue
            content = msg.get("content", "")

            # Skip pure tool-result records (already consumed via _tool_result_map)
            if isinstance(content, list) and content:
                # Check if ALL blocks are tool_result (then this is purely a tool response)
                if all(
                    isinstance(b, dict) and b.get("type") == "tool_result"
                    for b in content
                    if isinstance(b, dict)
                ):
                    continue

            # Extract user text
            text = _extract_text_from_content(content)
            if text.strip():
                events.append({
                    "type": "user",
                    "text": text,
                    "author": "principal",
                })

        elif rtype in ("task_created", "task_completed"):
            # First-class task-lifecycle records (DR-37, §4.2a). Forwarded verbatim in the
            # documented Genesys intake shape (see tests/fixtures/sample_transcript.json);
            # mirror_events turns them into task.* projection entries. This is NOT a guess at
            # a Claude Code transcript schema — it forwards records already in Genesys shape.
            # How a live CC transcript surfaces TaskCreated/TaskCompleted is a separate,
            # owner-gated concern (Step 0 transcript-schema validation).
            events.append({
                "type": rtype,
                "task_id": rec.get("task_id"),
                "text": rec.get("text", ""),
            })

        elif rtype == "assistant":
            msg = rec.get("message", {})
            if not isinstance(msg, dict):
                continue
            content = msg.get("content", [])
            if isinstance(content, str):
                # Plain-string assistant content (unusual but defensive)
                if content.strip():
                    events.append({
                        "type": "assistant_text",
                        "text": content,
                        "author": "daimon",
                    })
                continue
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")

                if btype == "text":
                    text = block.get("text", "")
                    if text.strip():
                        events.append({
                            "type": "assistant_text",
                            "text": text,
                            "author": "daimon",
                        })

                elif btype == "thinking":
                    thinking = block.get("thinking", "")
                    if thinking.strip():
                        events.append({
                            "type": "assistant_thinking",
                            "text": thinking,
                            "author": "daimon",
                        })

                elif btype == "tool_use":
                    tool_id = block.get("id", "")
                    tool_name = block.get("name", "")
                    tool_input = block.get("input", {})
                    tool_response = tool_responses.get(tool_id, "")
                    events.append({
                        "type": "tool_use",
                        "tool_name": tool_name,
                        "tool_input": json.dumps(tool_input, ensure_ascii=False),
                        "tool_response": tool_response,
                        "author": "daimon",
                    })
                # else: unknown block type — skip silently

        # else: unknown top-level record type — skip silently

    return events


def last_assistant_text(events: list[dict]) -> str:
    """Return the text of the last assistant_text event, or "" if none.

    Spec: provisional jot fallback #1 (F-GENESYS-03).
    """
    for ev in reversed(events):
        if isinstance(ev, dict) and ev.get("type") == "assistant_text":
            return ev.get("text", "")
    return ""


def last_user_text(events: list[dict]) -> str:
    """Return the text of the last user event, or "" if none.

    Spec: provisional jot fallback #2 (F-GENESYS-03).
    """
    for ev in reversed(events):
        if isinstance(ev, dict) and ev.get("type") == "user":
            return ev.get("text", "")
    return ""


def provisional_summary(events: list[dict]) -> str:
    """Return a provisional summary for the capture save ritual.

    RULING (F-GENESYS-03, pending design): provisional summary = last visible
    assistant_text in the transcript, falling back to last user message,
    falling back to "". This is a documented provisional choice pending the
    F-GENESYS-03 save-ritual heuristic design.
    """
    text = last_assistant_text(events)
    if text:
        return text
    text = last_user_text(events)
    return text
