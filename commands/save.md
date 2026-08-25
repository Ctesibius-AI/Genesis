---
description: Flush the current session to Genesys long-term memory with a reason/label
allowed-tools: Bash(genesys-save-moment:*)
---

Save the current Claude Code session window into Genesys memory, labelled with the user's reason.

`/save` is **archival, not curation** (D-GCW-11): the value is the deliberate flush + the
user-supplied label, through the single ingestion path (`save_annotation` → the extraction queue).

Run exactly:

```
genesys-save-moment --note "$ARGUMENTS"
```

`genesys-save-moment` auto-detects this session's transcript from the working directory and uses
`$ARGUMENTS` as the entry's jot/label. Report the resulting entry id, or "nothing new to save".
Do not add commentary.

*(Runtime wiring — PATH + data-root env — is provisioned by the Genesys installer, BT-8.)*
