# Genesis dev sandbox

An isolated Python 3.12 container for building/running/testing Genesis **without
installing anything on the host Mac** (which only has system Python 3.9; Genesis
requires >=3.12).

## Use it

```sh
./sandbox build     # build the image (one-time, and after Dockerfile changes)
./sandbox shell     # your terminal into the sandbox, at /workspace
./sandbox test      # run the test suite inside the container
```

`./sandbox test` accepts extra pytest args, e.g. `./sandbox test -k scrubber -q`.

## What's isolated (and what isn't)

- **Python 3.12 + uv + pytest live in the image**, not on your Mac. Delete the
  image and it's gone — the host stays clean.
- **Your source stays on the host** in git. The repo is bind-mounted read/write at
  `/workspace`, so branch-only / no-push guardrails keep working through host git.
  The container just runs and tests the code.

## Lock-safety (enforced by construction, not by prompt discipline)

- **No network:** the container runs with `network_mode: none`. Nothing inside can
  reach the internet or push to any remote.
- **Only this repo is mounted:** `$HOME` and `~/.claude` are **never** mounted, so
  DR-37 capture physically cannot reach real Claude Code transcripts. Live capture
  stays a separate, owner-gated deploy step.
- Byte-compilation and pytest caches are redirected to `/tmp` inside the container,
  so the sandbox does not litter the host tree.

## Runtime

Docker runtime is **colima** (started with `colima start`). It's capped for a 16 GB
machine (~4 CPU / 6 GB). Stop it with `colima stop` when you're done; start it again
before using the sandbox.
