"""Real scientific director through upstream Codex CLI and OpenRouter."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from ontojev.domain.models import OntoCodexDecision, OntoCodexInvocation
from ontojev.ontocodex.director import DirectorContext, project_context, validate_decision
from ontojev.storage.repository import canonical_json

DECISION_ADAPTER: TypeAdapter[OntoCodexDecision] = TypeAdapter(OntoCodexDecision)


class OntoCodexError(RuntimeError):
    pass


@dataclass(frozen=True)
class OntoCodexConfig:
    command: tuple[str, ...] = ("codex",)
    provider: str = "openrouter"
    provider_name: str = "OpenRouter"
    base_url: str = "https://openrouter.ai/api/v1"
    api_key_environment: str = "OPENROUTER_API_KEY"
    model: str = "deepseek/deepseek-v4.1-flash"
    timeout_seconds: float = 120
    max_projection_bytes: int = 65_536

    def __post_init__(self) -> None:
        if not self.command or not all(self.command):
            raise ValueError("Codex command must not be empty")
        if self.timeout_seconds <= 0 or self.max_projection_bytes <= 0:
            raise ValueError("OntoCodex limits must be positive")


def _safe_environment(config: OntoCodexConfig, codex_home: Path) -> dict[str, str]:
    key = os.getenv(config.api_key_environment)
    if not key:
        raise OntoCodexError(f"missing required environment variable {config.api_key_environment}")
    allowed_names = (
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "HOME",
        "USERPROFILE",
        "TEMP",
        "TMP",
    )
    environment = {name: os.environ[name] for name in allowed_names if name in os.environ}
    environment[config.api_key_environment] = key
    environment["CODEX_HOME"] = str(codex_home)
    environment["NO_COLOR"] = "1"
    return environment


def _configuration_text(config: OntoCodexConfig) -> str:
    value = json.dumps
    return "\n".join(
        (
            f"model = {value(config.model)}",
            f"model_provider = {value(config.provider)}",
            'approval_policy = "never"',
            'sandbox_mode = "read-only"',
            'web_search = "disabled"',
            "",
            f"[model_providers.{config.provider}]",
            f"name = {value(config.provider_name)}",
            f"base_url = {value(config.base_url)}",
            f"env_key = {value(config.api_key_environment)}",
            'wire_api = "responses"',
            "",
        )
    )


def _prompt(projection: dict[str, object]) -> str:
    return "\n".join(
        (
            "You are OntoCodex, the scientific director of a bounded computational laboratory.",
            "Return exactly one JSON object matching the supplied output schema.",
            "Choose only actions and exact CapabilityOffers present in the projection.",
            "Do not invent identifiers, measurements, evidence, capabilities, or executable code.",
            "A Campaign is scope, not a scheduler. Python validates and executes your choice.",
            "If no question exists, create a concise cancer-general synthetic research question.",
            "The projection contains summaries and references, never raw scientific payloads.",
            "",
            "CURRENT_SCIENTIFIC_CONTEXT",
            json.dumps(projection, sort_keys=True, separators=(",", ":")),
        )
    )


class CodexCliDirector:
    director_version = "codex-cli-director-v1"

    def __init__(self, config: OntoCodexConfig | None = None) -> None:
        self.config = config or OntoCodexConfig()
        self._last_invocation: OntoCodexInvocation | None = None

    @property
    def last_invocation(self) -> OntoCodexInvocation:
        if self._last_invocation is None:
            raise RuntimeError("director has not produced a decision")
        return self._last_invocation

    def decide(self, context: DirectorContext) -> OntoCodexDecision:
        projection = project_context(context)
        projection_bytes = canonical_json(projection)
        if len(projection_bytes) > self.config.max_projection_bytes:
            raise OntoCodexError(
                f"director projection exceeds {self.config.max_projection_bytes} bytes"
            )
        with tempfile.TemporaryDirectory(prefix="ontojev-ontocodex-") as temporary:
            workspace = Path(temporary)
            codex_home = workspace / "codex-home"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text(
                _configuration_text(self.config), encoding="utf-8"
            )
            schema_path = workspace / "research-decision.schema.json"
            schema_path.write_text(
                json.dumps(DECISION_ADAPTER.json_schema(), sort_keys=True), encoding="utf-8"
            )
            output_path = workspace / "research-decision.json"
            environment = _safe_environment(self.config, codex_home)
            cli_version = self._cli_version(environment, workspace)
            command = (
                *self.config.command,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--strict-config",
                "--sandbox",
                "read-only",
                "--color",
                "never",
                "--model",
                self.config.model,
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-",
            )
            try:
                completed = subprocess.run(
                    command,
                    cwd=workspace,
                    env=environment,
                    input=_prompt(projection),
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_seconds,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise OntoCodexError(f"Codex CLI invocation failed: {error}") from error
            if completed.returncode != 0:
                detail = completed.stderr.strip()[-500:]
                raise OntoCodexError(
                    f"Codex CLI exited with {completed.returncode}: {detail or 'no diagnostic'}"
                )
            if not output_path.is_file():
                raise OntoCodexError("Codex CLI produced no final decision file")
            raw_output = output_path.read_bytes()
        try:
            decision = DECISION_ADAPTER.validate_json(raw_output)
        except ValidationError as error:
            raise OntoCodexError("Codex CLI returned an invalid ResearchDecision") from error
        validate_decision(decision, context)
        safe_configuration = {
            "director_version": self.director_version,
            "provider": self.config.provider,
            "base_url": self.config.base_url,
            "model": self.config.model,
            "wire_api": "responses",
        }
        self._last_invocation = OntoCodexInvocation(
            director_version=self.director_version,
            codex_cli_version=cli_version,
            provider=self.config.provider,
            model=self.config.model,
            configuration_hash=hashlib.sha256(canonical_json(safe_configuration)).hexdigest(),
            input_projection_hash=hashlib.sha256(projection_bytes).hexdigest(),
            output_hash=hashlib.sha256(
                canonical_json(decision.model_dump(mode="json"))
            ).hexdigest(),
            decision_kind=decision.kind,
        )
        return decision

    def _cli_version(self, environment: dict[str, str], workspace: Path) -> str:
        try:
            completed = subprocess.run(
                (*self.config.command, "--version"),
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OntoCodexError(f"could not identify Codex CLI: {error}") from error
        if completed.returncode != 0 or not completed.stdout.strip():
            raise OntoCodexError("could not identify Codex CLI version")
        return completed.stdout.strip()
