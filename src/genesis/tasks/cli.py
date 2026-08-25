"""`genesis-tasks` CLI — emit task events and read the ranked department (spec §4.10).

Fixtures-only: no live hooks, no wall-clock (time via --now). Read-model is rebuildable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from genesis.tasks.department import tasks_department
from genesis.tasks.emit import (
    record_cancelled,
    record_created,
    record_done,
    record_due_moved,
)


def _fmt(view) -> str:
    s = view.state
    return f"{view.urgency:.2f}  {view.effective_status:<9}  {s.task_id}  {s.due or '-':<12}  {s.title}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="genesis-tasks")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--data-root", default=".")
    c.add_argument("--title", required=True)
    c.add_argument("--kind", default="task")
    c.add_argument("--due")
    c.add_argument("--recipient")
    c.add_argument("--project")
    c.add_argument("--episode", required=True)
    c.add_argument("--now", required=True)

    for name in ("move", "done", "cancel"):
        q = sub.add_parser(name)
        q.add_argument("--data-root", default=".")
        q.add_argument("--task-id", required=True)
        q.add_argument("--episode", required=True)
        q.add_argument("--now", required=True)
        if name == "move":
            q.add_argument("--due", required=True)

    li = sub.add_parser("list")
    li.add_argument("--data-root", default=".")
    li.add_argument("--now", required=True)
    li.add_argument("--all", action="store_true")

    args = p.parse_args(argv)
    root = Path(args.data_root)

    if args.cmd == "create":
        tid = record_created(root, ts=args.now, source_episode=args.episode, title=args.title,
                             kind=args.kind, due=args.due, recipient=args.recipient,
                             project_ref=args.project)
        print(tid)
    elif args.cmd == "move":
        record_due_moved(root, ts=args.now, task_id=args.task_id, due=args.due,
                         source_episode=args.episode)
    elif args.cmd == "done":
        record_done(root, ts=args.now, task_id=args.task_id, source_episode=args.episode)
    elif args.cmd == "cancel":
        record_cancelled(root, ts=args.now, task_id=args.task_id, source_episode=args.episode)
    elif args.cmd == "list":
        for v in tasks_department(root, now=args.now, include_terminal=args.all):
            print(_fmt(v))
    return 0
