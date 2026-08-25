---
description: Flush the current session to Genesis long-term memory with a reason/label
allowed-tools: Bash(genesis-save-moment:*)
---

Save the current Claude Code session window into Genesis memory, labelled with the user's reason.

`/save` is **archival, not curation** (D-GCW-11): the value is the deliberate flush + the
user-supplied label, through the single ingestion path (`save_annotation` → the extraction queue).

Run exactly:

```
genesis-save-moment --note "$ARGUMENTS" --session-id "$CLAUDE_CODE_SESSION_ID"
```

Passing `--session-id "$CLAUDE_CODE_SESSION_ID"` (Claude Code exports it to shell commands) selects
**this** session's transcript by exact id — never a concurrent other project's by mtime (F-06.3
workspace isolation). `$ARGUMENTS` is the entry's jot/label. Report the resulting entry id, or
"nothing new to save". Do not add commentary.

*(Runtime wiring — PATH + data-root env — is provisioned by the Genesis installer, BT-8.)*
