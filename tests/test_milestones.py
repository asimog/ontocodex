from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from ontojev.cli import main
from ontojev.domain.models import (
    Candidate,
    CapabilityPackageManifest,
    DossierMetadata,
    EngineeringTask,
    EvidenceState,
    Hypothesis,
    LiteratureContext,
    ResearchPortfolio,
    ResearchProgram,
    ScientificEvidence,
    ScientificScope,
    SourceRole,
    StatisticalState,
)
from ontojev.engineering.workflow import EngineeringError, EngineeringService
from ontojev.jev.typesafe import (
    ChoiceAnswer,
    SystemOneResponse,
    TypeSafeDeepEvaluator,
    TypeSafeWideEvaluator,
)
from ontojev.observatory import observe
from ontojev.runtime.scheduler import Scheduler
from ontojev.sources.ingest import SourceError, SourceService
from ontojev.storage.repository import Repository


def _initialize_observational_program(repository: Repository) -> ResearchProgram:
    program = ResearchProgram(
        name="Lung cancer research program",
        purpose="test reproducible patterns in adopted cohorts",
        cancer_scope="lung cancer",
        synthetic=False,
    )
    repository.save("program", program.program_id, program)
    portfolio = ResearchPortfolio(program_id=program.program_id)
    repository.save("portfolio", portfolio.portfolio_id, portfolio)
    return program


def _source_files(
    root: Path, role: SourceRole, rows: str, *, digest_override: str | None = None
) -> tuple[Path, Path]:
    data = root / f"{role.value.lower()}.csv"
    data.write_text("sample_id,feature,status\n" + rows, encoding="utf-8")
    digest = hashlib.sha256(data.read_bytes()).hexdigest()
    manifest = root / f"{role.value.lower()}.json"
    manifest.write_text(
        json.dumps(
            {
                "source_id": f"fixture-{role.value.lower()}",
                "title": f"Fixture {role.value.lower()} cohort",
                "source_uri": "https://example.invalid/adopted-source",
                "citation": "Fixture citation for contract testing",
                "license": "CC0-1.0",
                "release_identity": "fixture-2026-09",
                "cancer_scope": "lung cancer",
                "population": f"{role.value.lower()} cohort",
                "universe": "tested feature observations",
                "cohort_role": role.value,
                "sha256": digest_override or digest,
            }
        ),
        encoding="utf-8",
    )
    return manifest, data


def test_adopted_sources_drive_replicated_dossier_without_erasing_missingness(
    tmp_path: Path,
) -> None:
    repository = Repository(tmp_path / "state")
    program = _initialize_observational_program(repository)
    service = SourceService(repository)
    bad_manifest, primary_data = _source_files(
        tmp_path, SourceRole.PRIMARY, "p1,TP53,1\np2,TP53,missing\n", digest_override="0" * 64
    )
    with pytest.raises(SourceError, match="digest"):
        service.import_csv(bad_manifest, primary_data)

    primary_manifest, primary_data = _source_files(
        tmp_path,
        SourceRole.PRIMARY,
        "p1,TP53,1\np2,TP53,missing\np3,EGFR,0\np4,ALK,missing\n",
    )
    replication_manifest, replication_data = _source_files(
        tmp_path, SourceRole.REPLICATION, "r1,TP53,1\nr2,TP53,0\nr3,EGFR,1\n"
    )
    primary = service.import_csv(primary_manifest, primary_data)
    replication = service.import_csv(replication_manifest, replication_data)
    literature_file = tmp_path / "context.txt"
    literature_file.write_text("Operator-adopted contextual summary.", encoding="utf-8")
    service.import_literature(
        program.program_id,
        citation="Fixture literature citation",
        persistent_id="doi:fixture",
        relevance="context for interpretation only",
        path=literature_file,
    )

    Scheduler(tmp_path / "state").run(11)

    reopened = Repository(tmp_path / "state")
    evidence = reopened.list_latest("evidence", ScientificEvidence)
    assert {item.evidence_type for item in evidence} == {
        "observed.feature-prevalence-primary.v1",
        "observed.feature-prevalence-replication.v1",
    }
    replication_evidence = next(item for item in evidence if "replication" in item.evidence_type)
    assert replication_evidence.scope.population == "replication cohort"
    assert replication_evidence.scope.source_identity == "fixture-replication"
    primary_result = next(item for item in evidence if "primary" in item.evidence_type)
    payload = json.loads(reopened.artifacts.read(primary_result.result_ref))["payload"]
    tp53 = next(item for item in payload["features"] if item["feature"] == "TP53")
    assert tp53 == {
        "altered": 1,
        "feature": "TP53",
        "missing": 1,
        "observed": 1,
        "prevalence": 1.0,
    }
    alk = next(item for item in payload["features"] if item["feature"] == "ALK")
    assert alk["observed"] == 0
    assert alk["missing"] == 1
    assert alk["prevalence"] is None
    dossier = reopened.list_latest("dossier", DossierMetadata)[0]
    assert dossier.synthetic is False
    assert dossier.source_snapshot_ids == (primary.snapshot_id, replication.snapshot_id)
    assert len(dossier.hypothesis_ids) == 1
    assert len(dossier.literature_context_ids) == 1
    assert reopened.list_latest("hypothesis", Hypothesis)
    assert reopened.list_latest("literature_context", LiteratureContext)[
        0
    ].provenance.category.value == ("EXTERNAL_LITERATURE_CONTEXT")


def test_verified_engineering_promotion_is_identity_bound_and_observable(tmp_path: Path) -> None:
    repository = Repository(tmp_path)
    program = _initialize_observational_program(repository)
    Scheduler(tmp_path).step()
    service = EngineeringService(repository)
    question = Scheduler(tmp_path).current_context().active_question
    assert question is not None
    task = service.propose(
        question.question_id,
        scientific_need="independent sensitivity analysis",
        missing_capability="observed.sensitivity-analysis",
        required_method="versioned threshold sweep",
        existing_limit="prevalence method has one fixed interpretation",
    )
    package = tmp_path / "capability.zip"
    package.write_bytes(b"immutable capability package fixture")
    package_digest = hashlib.sha256(package.read_bytes()).hexdigest()
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "command": ["uv", "run", "pytest"],
                "exit_code": 0,
                "package_sha256": package_digest,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    receipt_digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
    manifest = CapabilityPackageManifest(
        capability_id="observed.sensitivity-analysis",
        version="1.0.0",
        output_contract="ontojev.sensitivity-analysis.v1",
        package_sha256=package_digest,
        verification_command=("uv", "run", "pytest"),
        verification_sha256=receipt_digest,
        limitations=("requires scientific review before code release",),
    )
    manifest_path = tmp_path / "package-manifest.json"
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")

    service.verify(task.task_id, manifest_path, package, receipt)
    with pytest.raises(EngineeringError, match="tree identity"):
        service.activate(task.task_id, verified_tree_identity="0" * 64)
    activated = service.activate(task.task_id, verified_tree_identity=package_digest)

    assert activated.status == "ACTIVATED"
    assert repository.load_latest("engineering_task", task.task_id, EngineeringTask) == activated
    snapshot = observe(repository)
    assert snapshot.counts["engineering_tasks"] == 1
    assert snapshot.counts["capability_gaps"] == 1
    assert snapshot.counts["programs"] == 1
    assert snapshot.integrity_errors == ()
    assert program.synthetic is False


def test_program_activation_selects_one_autonomous_portfolio(tmp_path: Path) -> None:
    assert main(["init", "--root", str(tmp_path), "--name", "Program A"]) == 0
    assert (
        main(
            [
                "init",
                "--root",
                str(tmp_path),
                "--name",
                "Program B",
                "--cancer-scope",
                "another explicit cancer scope",
            ]
        )
        == 0
    )
    programs = Repository(tmp_path).list_latest("program", ResearchProgram)
    first, second = programs
    assert Scheduler(tmp_path).current_context().program.program_id == first.program_id

    assert (
        main(
            [
                "program-activate",
                "--root",
                str(tmp_path),
                "--program-id",
                str(second.program_id),
            ]
        )
        == 0
    )
    context = Scheduler(tmp_path).current_context()
    assert context.program.program_id == second.program_id
    assert context.portfolio.program_id == second.program_id


class _SystemOneFixture:
    def __init__(self, choices: dict[str, str]) -> None:
        self.choices = choices
        self.states: list[dict[str, object]] = []

    def evaluate(self, state: dict[str, object], questions: dict[str, object]) -> SystemOneResponse:
        self.states.append(state)
        answers = {
            question_id: ChoiceAnswer(
                type="choice",
                choice=self.choices[question_id],
                probabilities={self.choices[question_id]: 0.9, "DEFER": 0.1},
                confidence=0.8,
            )
            for question_id in questions
        }
        return SystemOneResponse(model="jev-fixture", answers=answers)


def test_typesafe_jev_maps_bounded_choice_judgments_without_measurement() -> None:
    scope = ScientificScope(
        program_context="lung cancer",
        population="primary cohort",
        universe="tested feature observations",
        source_identity="fixture",
        release_identity="fixture-1",
    )
    state = StatisticalState(
        campaign_id=uuid4(),
        scope=scope,
        evidence_refs=(uuid4(),),
        evidence_dimensions=("observed.feature-prevalence-primary.v1",),
        current_patterns=("validated observed prevalence",),
        contradictions=(),
        uncertainty=("cohort bias",),
        missing_evidence=(),
        maturity="OBSERVATIONAL_DESCRIPTIVE",
    )
    wide_client = _SystemOneFixture({"evidence_coherence": "ADMIT", "investigation_value": "ADMIT"})
    wide = TypeSafeWideEvaluator(wide_client).evaluate(state)
    assert [item.disposition for item in wide] == ["ADMIT", "ADMIT"]
    assert all(item.provenance.category.value == "JEV_JUDGMENT" for item in wide)
    assert "payload" not in json.dumps(wide_client.states)

    candidate = Candidate(
        campaign_id=state.campaign_id,
        source_state_id=state.state_id,
        admission_decision_ids=tuple(item.decision_id for item in wide),
    )
    evidence_state = EvidenceState(
        candidate_id=candidate.candidate_id,
        revision=0,
        previous_evidence_state_id=None,
        evidence_refs=state.evidence_refs,
        findings=("descriptive pattern",),
        contradictions=(),
        unresolved_gaps=("independent replication",),
        judgment_refs=candidate.admission_decision_ids,
        maturity="OBSERVATIONAL_CANDIDATE",
    )
    deep = TypeSafeDeepEvaluator(_SystemOneFixture({"next_move": "FOLLOW_UP"})).evaluate(
        candidate, evidence_state
    )
    assert deep.next_move == "FOLLOW_UP"
    assert deep.provenance.category.value == "JEV_JUDGMENT"
