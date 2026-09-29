from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ontojev.domain.models import CreateQuestionDecision
from ontojev.ontocodex.codex_cli import CodexCliDirector, OntoCodexConfig, OntoCodexError
from ontojev.ontocodex.director import InvalidResearchDecision, project_context
from ontojev.runtime.scheduler import Scheduler


def _fake_codex(path: Path, decision: dict[str, object]) -> tuple[str, ...]:
    encoded = json.dumps(decision)
    path.write_text(
        "\n".join(
            (
                "import json",
                "import os",
                "import pathlib",
                "import sys",
                "if '--version' in sys.argv:",
                "    print('codex-cli 9.9.9-fixture')",
                "    raise SystemExit(0)",
                "prompt = sys.stdin.read()",
                "assert 'CURRENT_SCIENTIFIC_CONTEXT' in prompt",
                "assert os.environ['OPENROUTER_API_KEY'] not in prompt",
                "schema = pathlib.Path(sys.argv[sys.argv.index('--output-schema') + 1])",
                "assert json.loads(schema.read_text(encoding='utf-8'))['oneOf']",
                "output = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])",
                f"output.write_text({encoded!r}, encoding='utf-8')",
            )
        ),
        encoding="utf-8",
    )
    return (sys.executable, str(path))


def test_codex_cli_returns_schema_validated_decision_and_safe_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-secret-never-persist")
    context = Scheduler(tmp_path / "state").current_context()
    command = _fake_codex(
        tmp_path / "fake_codex.py",
        {"kind": "CREATE_QUESTION", "question": "Investigate a synthetic cancer-general gap"},
    )
    director = CodexCliDirector(OntoCodexConfig(command=command))

    decision = director.decide(context)

    assert isinstance(decision, CreateQuestionDecision)
    receipt = director.last_invocation
    assert receipt.codex_cli_version == "codex-cli 9.9.9-fixture"
    assert receipt.provider == "openrouter"
    assert receipt.model == "deepseek/deepseek-v4.1-flash"
    assert "fixture-secret-never-persist" not in receipt.model_dump_json()


def test_codex_cli_requires_credentials_and_python_rejects_stale_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = Scheduler(tmp_path / "missing-key").current_context()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(OntoCodexError, match="OPENROUTER_API_KEY"):
        CodexCliDirector(OntoCodexConfig(command=(sys.executable,))).decide(context)

    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-secret")
    state_root = tmp_path / "stale"
    scheduler = Scheduler(state_root)
    scheduler.step()
    stale_context = scheduler.current_context()
    command = _fake_codex(
        tmp_path / "stale_codex.py",
        {"kind": "CREATE_QUESTION", "question": "A duplicate active question"},
    )
    with pytest.raises(InvalidResearchDecision, match="not valid"):
        CodexCliDirector(OntoCodexConfig(command=command)).decide(stale_context)


def test_director_projection_excludes_raw_results_and_reports_omissions(tmp_path: Path) -> None:
    scheduler = Scheduler(tmp_path)
    scheduler.run(3)
    projection = project_context(scheduler.current_context(), item_limit=1)
    encoded = json.dumps(projection, sort_keys=True)

    assert '"payload"' not in encoded
    assert '"relative_path"' not in encoded
    assert projection["omissions"] == {
        "evidence": 0,
        "capability_offers": 0,
        "follow_up_offers": 0,
    }
    evidence = projection["evidence"]
    assert isinstance(evidence, list)
    assert evidence[0]["result_artifact_id"]
