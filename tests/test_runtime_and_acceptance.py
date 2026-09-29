from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from ontojev.capabilities.registry import CapabilityRegistry, ResultContract, bootstrap_registry
from ontojev.domain.models import (
    Campaign,
    Capability,
    CapabilityOffer,
    OntoCodexInvocation,
    QuestionStatus,
    ResearchQuestion,
    ResearchRun,
    ScientificEvidence,
)
from ontojev.runtime.scheduler import Scheduler
from ontojev.runtime.supervisor import RuntimeLimits
from ontojev.storage.repository import ArtifactIntegrityError, Repository


class SlowCapability:
    result_model: type[ResultContract] = ResultContract
    definition = Capability(
        capability_id="fixture.slow",
        version="1",
        scientific_purpose="exercise the public timeout boundary",
        evidence_type_produced="fixture.slow.v1",
        supported_phase="CAMPAIGN",
        supported_scope="fixture",
        prerequisites=(),
        input_contract="fixture",
        output_contract="fixture.empty.v1",
        expected_cost=1,
        expected_runtime_seconds=5,
        completeness_semantics="fixture",
        limitations=(),
    )

    def execute(self, offer: CapabilityOffer) -> ResultContract:
        time.sleep(5)
        return ResultContract()


def test_scheduler_persists_timeout_and_rederives_eligible_work(tmp_path: Path) -> None:
    registry = CapabilityRegistry()
    registry.register(SlowCapability())
    scheduler = Scheduler(tmp_path, registry=registry, limits=RuntimeLimits(0.4, 0.2))
    scheduler.run(2)
    first_timeout = scheduler.step()
    second_timeout = Scheduler(tmp_path, registry=registry, limits=RuntimeLimits(0.4, 0.2)).step()
    assert first_timeout.status.value == "TIMED_OUT"
    assert second_timeout.status.value == "TIMED_OUT"
    assert first_timeout.run_id != second_timeout.run_id


def _run_process(root: Path, count: int) -> None:
    subprocess.run(
        [sys.executable, "-m", "ontojev", "run", "--root", str(root), "--max-runs", str(count)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_two_restart_evidence_neutral_lifecycle_reaches_next_question(tmp_path: Path) -> None:
    _run_process(tmp_path, 4)
    _run_process(tmp_path, 4)
    _run_process(tmp_path, 5)

    scheduler = Scheduler(tmp_path)
    status = scheduler.status()
    assert status == {
        "programs": 1,
        "questions": 2,
        "campaigns": 1,
        "runs": 13,
        "evidence": 4,
        "candidates": 1,
        "dossiers": 1,
        "ontocodex_invocations": 13,
    }
    repository = Repository(tmp_path)
    questions = repository.list_latest("question", ResearchQuestion)
    assert [item.status for item in questions] == [QuestionStatus.ANSWERED, QuestionStatus.ACTIVE]
    campaign = repository.list_latest("campaign", Campaign)[0]
    evidence_types = {
        item.evidence_type
        for item in repository.list_latest("evidence", ScientificEvidence)
        if item.campaign_id == campaign.campaign_id
    }
    assert evidence_types == {
        "bootstrap.scalar-pattern.v1",
        "bootstrap.pairwise-relation.v1",
        "bootstrap.categorical-profile.v1",
        "bootstrap.follow-up.v1",
    }
    runs = repository.list_latest("research_run", ResearchRun)
    invocations = repository.list_latest("ontocodex_invocation", OntoCodexInvocation)
    assert all(run.ontocodex_invocation_id is not None for run in runs)
    assert {item.provider for item in invocations} == {"deterministic"}


def test_corrupt_evidence_blocks_scientific_composition(tmp_path: Path) -> None:
    scheduler = Scheduler(tmp_path, registry=bootstrap_registry(include_third=False))
    scheduler.run(4)
    repository = Repository(tmp_path)
    evidence = repository.list_latest("evidence", ScientificEvidence)[0]
    (tmp_path / evidence.result_ref.relative_path).write_bytes(b"corrupt")

    with pytest.raises(ArtifactIntegrityError, match="corrupt artifact"):
        scheduler.step()
