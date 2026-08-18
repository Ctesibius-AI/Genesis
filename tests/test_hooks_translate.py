"""Tests for genesys.hooks.translate — CC transcript → Genesys event dicts.

All tests are offline (no network, no real Claude Code).
"""

from __future__ import annotations

import json

import pytest

from genesys.hooks.translate import (
    cc_transcript_to_events,
    last_assistant_text,
    last_user_text,
    provisional_summary,
)


# --------------------------------------------------------------------------- #
# Shared fixture: a realistic CC transcript (user + assistant with            #
# text + thinking + tool_use blocks, plus a tool_result user record)          #
# --------------------------------------------------------------------------- #

TOOL_USE_ID = "toolu_01AbCdEfGhIj"

CC_RECORDS: list[dict] = [
    # 1. Plain user message (content as string)
    {
        "type": "user",
        "message": {
            "role": "user",
            "content": "What files are in the src directory?",
        },
    },
    # 2. Assistant with text + thinking + tool_use blocks
    {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "thinking",
                    "thinking": "The user wants to see the directory listing. I should run ls.",
                },
                {
                    "type": "text",
                    "text": "Let me check the src directory for you.",
                },
                {
                    "type": "tool_use",
                    "id": TOOL_USE_ID,
                    "name": "Bash",
                    "input": {"command": "ls src/"},
                },
            ],
        },
    },
    # 3. Tool result (user record carrying tool_result block)
    {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": TOOL_USE_ID,
                    "content": "genesys/\nREADME.md\n",
                }
            ],
        },
    },
    # 4. Final assistant text reply
    {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "The src directory contains genesys/ and README.md.",
                }
            ],
        },
    },
]


# --------------------------------------------------------------------------- #
# cc_transcript_to_events                                                       #
# --------------------------------------------------------------------------- #

def test_user_message_maps_to_user_event():
    events = cc_transcript_to_events(CC_RECORDS)
    user_evs = [e for e in events if e["type"] == "user"]
    assert len(user_evs) == 1
    assert user_evs[0]["text"] == "What files are in the src directory?"
    assert user_evs[0]["author"] == "principal"


def test_assistant_text_block_maps_to_assistant_text_event():
    events = cc_transcript_to_events(CC_RECORDS)
    text_evs = [e for e in events if e["type"] == "assistant_text"]
    texts = [e["text"] for e in text_evs]
    assert "Let me check the src directory for you." in texts
    assert "The src directory contains genesys/ and README.md." in texts


def test_thinking_block_maps_to_assistant_thinking_event():
    events = cc_transcript_to_events(CC_RECORDS)
    thinking_evs = [e for e in events if e["type"] == "assistant_thinking"]
    assert len(thinking_evs) == 1
    assert "I should run ls" in thinking_evs[0]["text"]
    assert thinking_evs[0]["author"] == "daimon"


def test_tool_use_block_maps_with_paired_tool_response():
    events = cc_transcript_to_events(CC_RECORDS)
    tool_evs = [e for e in events if e["type"] == "tool_use"]
    assert len(tool_evs) == 1
    ev = tool_evs[0]
    assert ev["tool_name"] == "Bash"
    # tool_input is JSON-serialized
    assert json.loads(ev["tool_input"]) == {"command": "ls src/"}
    assert ev["author"] == "daimon"
    # tool_response is the paired result
    assert "genesys/" in ev["tool_response"]


def test_tool_result_record_is_not_emitted_as_standalone_event():
    """Pure tool_result user records must not produce a 'user' event."""
    events = cc_transcript_to_events(CC_RECORDS)
    user_evs = [e for e in events if e["type"] == "user"]
    # Only one user event (the first user message), not the tool_result record
    assert len(user_evs) == 1


def test_event_order_preserves_document_order():
    events = cc_transcript_to_events(CC_RECORDS)
    types = [e["type"] for e in events]
    # Expected: user, assistant_thinking, assistant_text, tool_use, assistant_text
    assert types[0] == "user"
    assert "assistant_thinking" in types
    # thinking comes before the first assistant_text from the same assistant turn
    t_idx = types.index("assistant_thinking")
    first_text_idx = next(i for i, t in enumerate(types) if t == "assistant_text")
    assert t_idx < first_text_idx


def test_unknown_record_type_is_skipped():
    records = [
        {"type": "system", "message": {"content": "You are helpful."}},
        *CC_RECORDS,
    ]
    events_with = cc_transcript_to_events(records)
    events_without = cc_transcript_to_events(CC_RECORDS)
    assert len(events_with) == len(events_without)


def test_empty_records_returns_empty_events():
    assert cc_transcript_to_events([]) == []


def test_malformed_record_is_skipped():
    records = [
        None,  # not a dict
        {"no_type_key": True},
        *CC_RECORDS,
    ]
    # Should not crash, should process the valid ones
    events = cc_transcript_to_events(records)  # type: ignore[arg-type]
    assert any(e["type"] == "user" for e in events)


def test_user_with_text_block_content():
    """User messages with list-of-text-blocks content (not plain string)."""
    records = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Hello from list block"}],
            },
        }
    ]
    events = cc_transcript_to_events(records)
    assert len(events) == 1
    assert events[0]["type"] == "user"
    assert events[0]["text"] == "Hello from list block"


def test_assistant_plain_string_content():
    """Defensive: assistant content as a plain string (unusual but possible)."""
    records = [
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": "Just a plain string reply.",
            },
        }
    ]
    events = cc_transcript_to_events(records)
    assert len(events) == 1
    assert events[0]["type"] == "assistant_text"
    assert events[0]["text"] == "Just a plain string reply."


def test_tool_use_without_matching_result_has_empty_tool_response():
    records = [
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_no_result",
                        "name": "Read",
                        "input": {"file_path": "/tmp/x"},
                    }
                ],
            },
        }
    ]
    events = cc_transcript_to_events(records)
    assert len(events) == 1
    ev = events[0]
    assert ev["type"] == "tool_use"
    assert ev["tool_response"] == ""


# --------------------------------------------------------------------------- #
# Helper functions                                                              #
# --------------------------------------------------------------------------- #

def test_last_assistant_text_returns_last():
    events = cc_transcript_to_events(CC_RECORDS)
    result = last_assistant_text(events)
    # The last assistant_text is from the final assistant turn
    assert result == "The src directory contains genesys/ and README.md."


def test_last_user_text_returns_last():
    events = cc_transcript_to_events(CC_RECORDS)
    result = last_user_text(events)
    assert result == "What files are in the src directory?"


def test_last_assistant_text_empty_when_none():
    events = [{"type": "user", "text": "hi", "author": "principal"}]
    assert last_assistant_text(events) == ""


def test_last_user_text_empty_when_none():
    events = [{"type": "assistant_text", "text": "hi", "author": "daimon"}]
    assert last_user_text(events) == ""


# --------------------------------------------------------------------------- #
# provisional_summary (F-GENESYS-03 ruling)                                    #
# --------------------------------------------------------------------------- #

def test_provisional_summary_returns_last_assistant_text():
    events = cc_transcript_to_events(CC_RECORDS)
    summary = provisional_summary(events)
    assert summary == "The src directory contains genesys/ and README.md."


def test_provisional_summary_falls_back_to_user_when_no_assistant():
    events = [
        {"type": "user", "text": "A user message.", "author": "principal"},
    ]
    summary = provisional_summary(events)
    assert summary == "A user message."


def test_provisional_summary_returns_empty_string_when_no_events():
    assert provisional_summary([]) == ""
