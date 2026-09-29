"""Command-line entry point for bounded bootstrap research."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from ontojev.ontocodex.codex_cli import CodexCliDirector, OntoCodexConfig
from ontojev.ontocodex.director import DeterministicDirector, Director
from ontojev.runtime.scheduler import Scheduler
from ontojev.runtime.supervisor import RuntimeLimits


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ontojev")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="advance bounded synthetic research")
    run.add_argument("--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev")))
    run.add_argument("--max-runs", type=int, default=1)
    run.add_argument(
        "--director",
        choices=("deterministic", "codex"),
        default=os.getenv("ONTOJEV_DIRECTOR", "deterministic"),
        help="scientific director; Codex is opt-in and requires OPENROUTER_API_KEY",
    )
    status = commands.add_parser("status", help="print durable research counts")
    status.add_argument(
        "--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev"))
    )
    return parser


def _limits() -> RuntimeLimits:
    return RuntimeLimits(
        timeout_seconds=float(os.getenv("ONTOJEV_RUN_TIMEOUT_SECONDS", "600")),
        finalization_reserve_seconds=float(os.getenv("ONTOJEV_FINALIZATION_RESERVE_SECONDS", "30")),
    )


def _director(name: str) -> Director:
    if name == "deterministic":
        return DeterministicDirector()
    executable = os.getenv("ONTOCODEX_EXECUTABLE", "codex")
    return CodexCliDirector(
        OntoCodexConfig(
            command=(executable,),
            model=os.getenv("ONTOCODEX_MODEL", "deepseek/deepseek-v4.1-flash"),
            timeout_seconds=float(os.getenv("ONTOCODEX_TIMEOUT_SECONDS", "120")),
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    director = _director(arguments.director) if arguments.command == "run" else None
    scheduler = Scheduler(arguments.root, director=director, limits=_limits())
    if arguments.command == "run":
        runs = scheduler.run(arguments.max_runs)
        print(json.dumps([run.model_dump(mode="json") for run in runs], default=str, indent=2))
    else:
        print(json.dumps(scheduler.status(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
