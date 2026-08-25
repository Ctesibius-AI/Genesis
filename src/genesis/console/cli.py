"""QA console CLI (spec §14). `dump` = stdlib JSON projection (fixtures/offline). `serve` = the
lazy FastAPI localhost server (D-QA-7; live path, owner-gated).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from genesis.console.server import model_to_dict


def _cmd_dump(args: argparse.Namespace) -> int:
    print(json.dumps(model_to_dict(Path(args.data)), ensure_ascii=False, indent=2))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:  # pragma: no cover — needs fastapi/uvicorn
    import uvicorn  # noqa: PLC0415 — lazy

    from genesis.console.server import create_app

    uvicorn.run(create_app(Path(args.data)), host="127.0.0.1", port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genesis-console",
        description="QA console: dump the read-only model (stdlib) or serve localhost (lazy FastAPI).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_d = sub.add_parser("dump")
    p_d.add_argument("--data", required=True)
    p_d.set_defaults(func=_cmd_dump)
    p_s = sub.add_parser("serve")
    p_s.add_argument("--data", required=True)
    p_s.add_argument("--port", type=int, default=8770)
    p_s.set_defaults(func=_cmd_serve)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
