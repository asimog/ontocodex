"""Command-line entry point for bounded bootstrap research."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from ontojev.domain.models import ResearchPortfolio, ResearchProgram
from ontojev.engineering.workflow import EngineeringService
from ontojev.jev.typesafe import (
    HttpSystemOneClient,
    TypeSafeConfig,
    TypeSafeDeepEvaluator,
    TypeSafeWideEvaluator,
)
from ontojev.observatory import observe
from ontojev.ontocodex.codex_cli import CodexCliDirector, OntoCodexConfig
from ontojev.ontocodex.director import DeterministicDirector, Director
from ontojev.runtime.scheduler import Scheduler
from ontojev.runtime.supervisor import RuntimeLimits
from ontojev.sources.ingest import SourceService
from ontojev.storage.repository import Repository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ontojev")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="advance one bounded research program")
    run.add_argument("--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev")))
    run.add_argument("--max-runs", type=int, default=1)
    run.add_argument(
        "--director",
        choices=("deterministic", "codex"),
        default=os.getenv("ONTOJEV_DIRECTOR", "deterministic"),
        help="scientific director; Codex is opt-in and requires OPENROUTER_API_KEY",
    )
    run.add_argument(
        "--jev",
        choices=("deterministic", "typesafe"),
        default=os.getenv("ONTOJEV_JEV", "deterministic"),
        help="judgment adapter; TypeSafe is opt-in and requires TYPESAFE_API_KEY",
    )
    status = commands.add_parser("status", help="print durable research counts")
    status.add_argument(
        "--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev"))
    )
    initialize = commands.add_parser("init", help="initialize an observational ResearchProgram")
    initialize.add_argument(
        "--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev"))
    )
    initialize.add_argument("--name", default="Lung cancer research program")
    initialize.add_argument(
        "--purpose", default="evaluate reproducible computational patterns in adopted cohorts"
    )
    initialize.add_argument("--cancer-scope", default="lung cancer")
    initialize.add_argument(
        "--activate", action="store_true", help="make this program active when others exist"
    )
    activate_program = commands.add_parser("program-activate", help="select the active program")
    activate_program.add_argument(
        "--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev"))
    )
    activate_program.add_argument("--program-id", type=UUID, required=True)
    source = commands.add_parser("source-import", help="preflight and adopt a digest-pinned CSV")
    source.add_argument(
        "--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev"))
    )
    source.add_argument("--manifest", type=Path, required=True)
    source.add_argument("--data", type=Path, required=True)
    literature = commands.add_parser(
        "literature-import", help="adopt literature as context, never measurement"
    )
    literature.add_argument(
        "--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev"))
    )
    literature.add_argument("--citation", required=True)
    literature.add_argument("--persistent-id", required=True)
    literature.add_argument("--relevance", required=True)
    literature.add_argument("--file", type=Path, required=True)
    observatory = commands.add_parser("observe", help="print a read-only integrity projection")
    observatory.add_argument(
        "--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev"))
    )
    gap = commands.add_parser("gap-propose", help="record a capability gap and engineering task")
    gap.add_argument("--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev")))
    gap.add_argument("--question-id", type=UUID, required=True)
    gap.add_argument("--scientific-need", required=True)
    gap.add_argument("--missing-capability", required=True)
    gap.add_argument("--required-method", required=True)
    gap.add_argument("--existing-limit", required=True)
    verify = commands.add_parser("engineering-verify", help="adopt external verification proof")
    verify.add_argument(
        "--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev"))
    )
    verify.add_argument("--task-id", type=UUID, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--package", type=Path, required=True)
    verify.add_argument("--receipt", type=Path, required=True)
    activate = commands.add_parser(
        "engineering-activate", help="activate a verified package record"
    )
    activate.add_argument(
        "--root", type=Path, default=Path(os.getenv("ONTOJEV_DATA_ROOT", ".ontojev"))
    )
    activate.add_argument("--task-id", type=UUID, required=True)
    activate.add_argument("--tree", required=True)
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
    if arguments.command == "init":
        repository = Repository(arguments.root)
        existing = repository.list_latest("program", ResearchProgram)
        activate = not existing or arguments.activate
        if activate:
            for item in existing:
                if item.active:
                    repository.save(
                        "program", item.program_id, item.model_copy(update={"active": False})
                    )
        program = ResearchProgram(
            name=arguments.name,
            purpose=arguments.purpose,
            cancer_scope=arguments.cancer_scope,
            synthetic=False,
            active=activate,
        )
        portfolio = ResearchPortfolio(program_id=program.program_id)
        repository.save("program", program.program_id, program)
        repository.save("portfolio", portfolio.portfolio_id, portfolio)
        print(program.model_dump_json(indent=2))
        return 0
    if arguments.command == "program-activate":
        repository = Repository(arguments.root)
        programs = repository.list_latest("program", ResearchProgram)
        target = next((item for item in programs if item.program_id == arguments.program_id), None)
        if target is None:
            raise RuntimeError("ResearchProgram does not exist")
        for item in programs:
            desired = item.program_id == target.program_id
            if item.active != desired:
                repository.save(
                    "program", item.program_id, item.model_copy(update={"active": desired})
                )
        print(target.model_copy(update={"active": True}).model_dump_json(indent=2))
        return 0
    if arguments.command == "source-import":
        snapshot = SourceService(Repository(arguments.root)).import_csv(
            arguments.manifest, arguments.data
        )
        print(snapshot.model_dump_json(indent=2))
        return 0
    if arguments.command == "literature-import":
        repository = Repository(arguments.root)
        programs = tuple(
            item for item in repository.list_latest("program", ResearchProgram) if item.active
        )
        if len(programs) != 1:
            raise RuntimeError("literature import requires exactly one active ResearchProgram")
        context = SourceService(repository).import_literature(
            programs[0].program_id,
            citation=arguments.citation,
            persistent_id=arguments.persistent_id,
            relevance=arguments.relevance,
            path=arguments.file,
        )
        print(context.model_dump_json(indent=2))
        return 0
    if arguments.command == "observe":
        print(observe(Repository(arguments.root)).model_dump_json(indent=2))
        return 0
    if arguments.command == "gap-propose":
        task = EngineeringService(Repository(arguments.root)).propose(
            arguments.question_id,
            scientific_need=arguments.scientific_need,
            missing_capability=arguments.missing_capability,
            required_method=arguments.required_method,
            existing_limit=arguments.existing_limit,
        )
        print(task.model_dump_json(indent=2))
        return 0
    if arguments.command == "engineering-verify":
        task = EngineeringService(Repository(arguments.root)).verify(
            arguments.task_id, arguments.manifest, arguments.package, arguments.receipt
        )
        print(task.model_dump_json(indent=2))
        return 0
    if arguments.command == "engineering-activate":
        task = EngineeringService(Repository(arguments.root)).activate(
            arguments.task_id, verified_tree_identity=arguments.tree
        )
        print(task.model_dump_json(indent=2))
        return 0
    director = _director(arguments.director) if arguments.command == "run" else None
    wide = deep = None
    if arguments.command == "run" and arguments.jev == "typesafe":
        api_key = os.getenv("TYPESAFE_API_KEY", "")
        if not api_key:
            raise RuntimeError("TYPESAFE_API_KEY is required when --jev typesafe")
        client = HttpSystemOneClient(
            TypeSafeConfig(
                api_key=api_key,
                model=os.getenv("TYPESAFE_MODEL", "jev-latest"),
                endpoint=os.getenv("TYPESAFE_ENDPOINT", "https://api.typesafe.ai/v1/systemone"),
                timeout_seconds=float(os.getenv("TYPESAFE_TIMEOUT_SECONDS", "30")),
            )
        )
        wide = TypeSafeWideEvaluator(client)
        deep = TypeSafeDeepEvaluator(client)
    scheduler = Scheduler(
        arguments.root,
        director=director,
        wide_evaluator=wide,
        deep_evaluator=deep,
        limits=_limits(),
    )
    if arguments.command == "run":
        runs = scheduler.run(arguments.max_runs)
        print(json.dumps([run.model_dump(mode="json") for run in runs], default=str, indent=2))
    else:
        print(json.dumps(scheduler.status(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
