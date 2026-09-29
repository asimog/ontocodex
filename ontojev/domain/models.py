"""Immutable, evidence-neutral contracts for the OntoJev bootstrap."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def new_id() -> UUID:
    return uuid4()


def utc_now() -> datetime:
    return datetime.now(UTC)


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: int = 1


class ProvenanceCategory(StrEnum):
    OBSERVED = "OBSERVED"
    DETERMINISTICALLY_DERIVED = "DETERMINISTICALLY_DERIVED"
    JEV_JUDGMENT = "JEV_JUDGMENT"
    ONTOCODEX_SCIENTIFIC_JUDGMENT = "ONTOCODEX_SCIENTIFIC_JUDGMENT"
    EXTERNAL_LITERATURE_CONTEXT = "EXTERNAL_LITERATURE_CONTEXT"


class Completeness(StrEnum):
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"


class RunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    INTERRUPTED = "INTERRUPTED"


class QuestionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ANSWERED = "ANSWERED"
    DEFERRED = "DEFERRED"
    EXHAUSTED = "EXHAUSTED"


class SourceRole(StrEnum):
    PRIMARY = "PRIMARY"
    REPLICATION = "REPLICATION"


class ArtifactRef(Contract):
    artifact_id: UUID = Field(default_factory=new_id)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str
    relative_path: str


class ScientificScope(Contract):
    scope_id: UUID = Field(default_factory=new_id)
    program_context: str
    population: str
    universe: str
    source_identity: str
    release_identity: str

    @property
    def compatibility_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.program_context,
            self.population,
            self.universe,
            self.source_identity,
            self.release_identity,
        )


class Provenance(Contract):
    category: ProvenanceCategory
    producer_id: str
    producer_version: str
    created_at: datetime = Field(default_factory=utc_now)
    input_refs: tuple[UUID, ...] = ()

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value


class ResearchProgram(Contract):
    program_id: UUID = Field(default_factory=new_id)
    name: str
    purpose: str
    active: bool = True
    cancer_scope: str = "cancer-general"
    synthetic: bool = True
    source_snapshot_ids: tuple[UUID, ...] = ()


class ResearchPortfolio(Contract):
    portfolio_id: UUID = Field(default_factory=new_id)
    program_id: UUID
    question_ids: tuple[UUID, ...] = ()
    revision: int = 0


class ResearchQuestion(Contract):
    question_id: UUID = Field(default_factory=new_id)
    portfolio_id: UUID
    question: str
    status: QuestionStatus = QuestionStatus.ACTIVE


class Campaign(Contract):
    campaign_id: UUID = Field(default_factory=new_id)
    question_id: UUID
    scope: ScientificScope
    source_snapshot_ids: tuple[UUID, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)


class SourceManifest(Contract):
    source_id: str
    title: str
    source_uri: str
    citation: str
    license: str
    release_identity: str
    cancer_scope: str
    population: str
    universe: str
    cohort_role: SourceRole
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_columns: tuple[str, ...] = ("sample_id", "feature", "status")

    @model_validator(mode="after")
    def require_attribution_and_contract_columns(self) -> SourceManifest:
        attributed = (
            self.source_id,
            self.title,
            self.source_uri,
            self.citation,
            self.license,
            self.release_identity,
            self.cancer_scope,
            self.population,
            self.universe,
        )
        if any(not value.strip() for value in attributed):
            raise ValueError("source attribution and scope fields must be non-empty")
        required = {"sample_id", "feature", "status"}
        if not required.issubset(self.required_columns):
            raise ValueError("source contract must retain sample_id, feature, and status")
        return self


class SourceSnapshot(Contract):
    snapshot_id: UUID = Field(default_factory=new_id)
    manifest: SourceManifest
    data_ref: ArtifactRef
    row_count: int = Field(gt=0)
    observed_rows: int = Field(ge=0)
    missing_rows: int = Field(ge=0)
    imported_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def account_for_every_row(self) -> SourceSnapshot:
        if self.observed_rows + self.missing_rows != self.row_count:
            raise ValueError("observed and missing counts must account for every row")
        return self


class LiteratureContext(Contract):
    literature_id: UUID = Field(default_factory=new_id)
    program_id: UUID
    citation: str
    persistent_id: str
    relevance: str
    artifact_ref: ArtifactRef
    provenance: Provenance


class ResearchRun(Contract):
    run_id: UUID = Field(default_factory=new_id)
    campaign_id: UUID | None = None
    decision_kind: str
    ontocodex_invocation_id: UUID | None = None
    status: RunStatus = RunStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    outcome_ref: UUID | None = None
    error: str | None = None


class OntoCodexInvocation(Contract):
    invocation_id: UUID = Field(default_factory=new_id)
    director_version: str
    codex_cli_version: str | None
    provider: str
    model: str
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_projection_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision_kind: str
    created_at: datetime = Field(default_factory=utc_now)


class Capability(Contract):
    capability_id: str
    version: str
    scientific_purpose: str
    evidence_type_produced: str
    supported_phase: Literal["CAMPAIGN", "CANDIDATE"]
    supported_scope: str
    prerequisites: tuple[str, ...]
    input_contract: str
    output_contract: str
    expected_cost: int = Field(ge=0)
    expected_runtime_seconds: float = Field(gt=0)
    completeness_semantics: str
    limitations: tuple[str, ...]


class CapabilityOffer(Contract):
    offer_id: UUID = Field(default_factory=new_id)
    capability_id: str
    capability_version: str
    campaign_id: UUID
    scope_id: UUID
    phase: Literal["CAMPAIGN", "CANDIDATE"]
    input_refs: tuple[UUID, ...]
    offer_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CapabilityResult(Contract):
    result_id: UUID = Field(default_factory=new_id)
    capability_id: str
    capability_version: str
    output_contract: str
    payload: dict[str, Any]
    completeness: Completeness
    limitations: tuple[str, ...] = ()


class ScientificEvidence(Contract):
    evidence_id: UUID = Field(default_factory=new_id)
    evidence_type: str
    capability_id: str
    method_version: str
    campaign_id: UUID
    scope: ScientificScope
    result_ref: ArtifactRef
    completeness: Completeness
    uncertainty: tuple[str, ...]
    provenance: Provenance
    limitations: tuple[str, ...]


class StatisticalState(Contract):
    state_id: UUID = Field(default_factory=new_id)
    campaign_id: UUID
    scope: ScientificScope
    evidence_refs: tuple[UUID, ...]
    evidence_dimensions: tuple[str, ...]
    current_patterns: tuple[str, ...]
    contradictions: tuple[str, ...]
    uncertainty: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    maturity: str
    previous_state_id: UUID | None = None


class WideDecision(Contract):
    decision_id: UUID = Field(default_factory=new_id)
    state_id: UUID
    question_id: str
    score: float = Field(ge=0, le=1)
    disposition: Literal["ADMIT", "DEFER", "REJECT", "ABSTAIN"]
    rationale: str
    provenance: Provenance


class Candidate(Contract):
    candidate_id: UUID = Field(default_factory=new_id)
    campaign_id: UUID
    source_state_id: UUID
    admission_decision_ids: tuple[UUID, ...]
    admitted_at: datetime = Field(default_factory=utc_now)


class EvidenceState(Contract):
    evidence_state_id: UUID = Field(default_factory=new_id)
    candidate_id: UUID
    revision: int
    previous_evidence_state_id: UUID | None
    evidence_refs: tuple[UUID, ...]
    findings: tuple[str, ...]
    contradictions: tuple[str, ...]
    unresolved_gaps: tuple[str, ...]
    judgment_refs: tuple[UUID, ...]
    maturity: str


class DeepDecision(Contract):
    decision_id: UUID = Field(default_factory=new_id)
    evidence_state_id: UUID
    next_move: Literal["FOLLOW_UP", "HYPOTHESIS", "REPLICATE", "FINALIZE", "DEFER"]
    rationale: str
    provenance: Provenance


class JevDecision(Contract):
    decision_id: UUID = Field(default_factory=new_id)
    role: Literal["RESEARCH_CONTROL", "SCIENTIFIC_EVALUATION"]
    contract_id: str
    contract_version: str
    outcome: str
    provenance: Provenance


class Hypothesis(Contract):
    hypothesis_id: UUID = Field(default_factory=new_id)
    candidate_id: UUID
    triggering_evidence: tuple[UUID, ...]
    statement: str
    alternatives: tuple[str, ...]
    discriminating_observation: str
    required_evidence: tuple[str, ...]
    executable_test: str | None
    strengthening_outcome: str
    weakening_outcome: str


class FinalCandidateResult(Contract):
    result_id: UUID = Field(default_factory=new_id)
    candidate_id: UUID
    final_evidence_state_id: UUID
    disposition: Literal["COMPUTATIONAL_CASE_COMPLETE", "DEFERRED", "EXHAUSTED"]
    stopping_rationale: str
    limitations: tuple[str, ...]


class DossierMetadata(Contract):
    dossier_id: UUID = Field(default_factory=new_id)
    program_id: UUID
    portfolio_id: UUID
    question_id: UUID
    campaign_id: UUID
    candidate_id: UUID
    final_result_id: UUID
    run_ids: tuple[UUID, ...]
    evidence_refs: tuple[UUID, ...]
    statistical_state_ids: tuple[UUID, ...]
    evidence_state_ids: tuple[UUID, ...]
    judgment_refs: tuple[UUID, ...]
    uncertainty: tuple[str, ...]
    limitations: tuple[str, ...]
    stopping_rationale: str
    software_identity: str
    configuration_identity: str
    source_snapshot_ids: tuple[UUID, ...] = ()
    literature_context_ids: tuple[UUID, ...] = ()
    hypothesis_ids: tuple[UUID, ...] = ()
    synthetic: bool = True


class CapabilityGap(Contract):
    gap_id: UUID = Field(default_factory=new_id)
    question_id: UUID
    scientific_need: str
    missing_capability: str
    required_evidence_or_method: str
    existing_capability_limit: str


class EngineeringTask(Contract):
    task_id: UUID = Field(default_factory=new_id)
    gap_id: UUID
    status: Literal["PROPOSED", "VERIFIED", "ACTIVATED", "REJECTED"] = "PROPOSED"
    verified_tree_identity: str | None = None
    package_ref: ArtifactRef | None = None
    verification_ref: ArtifactRef | None = None


class CapabilityPackageManifest(Contract):
    capability_id: str
    version: str
    output_contract: str
    package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_command: tuple[str, ...]
    verification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def require_verification_command(self) -> CapabilityPackageManifest:
        if not self.verification_command or any(not item for item in self.verification_command):
            raise ValueError("verification command must be explicit")
        return self


class ObservatorySnapshot(Contract):
    generated_at: datetime = Field(default_factory=utc_now)
    counts: dict[str, int]
    active_question_id: UUID | None
    active_campaign_id: UUID | None
    latest_run_status: RunStatus | None
    integrity_errors: tuple[str, ...]


class CreateQuestionDecision(Contract):
    kind: Literal["CREATE_QUESTION"] = "CREATE_QUESTION"
    question: str


class StartCampaignDecision(Contract):
    kind: Literal["START_CAMPAIGN"] = "START_CAMPAIGN"
    question_id: UUID


class ExecuteCapabilityDecision(Contract):
    kind: Literal["EXECUTE_CAPABILITY"] = "EXECUTE_CAPABILITY"
    offer: CapabilityOffer


class ComposeEvidenceDecision(Contract):
    kind: Literal["COMPOSE_EVIDENCE"] = "COMPOSE_EVIDENCE"
    campaign_id: UUID
    evidence_refs: tuple[UUID, ...]


class RequestWideDecision(Contract):
    kind: Literal["REQUEST_WIDE"] = "REQUEST_WIDE"
    state_id: UUID


class InvestigateCandidateDecision(Contract):
    kind: Literal["INVESTIGATE_CANDIDATE"] = "INVESTIGATE_CANDIDATE"
    candidate_id: UUID


class ExecuteFollowUpDecision(Contract):
    kind: Literal["EXECUTE_FOLLOW_UP"] = "EXECUTE_FOLLOW_UP"
    candidate_id: UUID
    offer: CapabilityOffer


class FinalizeCandidateDecision(Contract):
    kind: Literal["FINALIZE_CANDIDATE"] = "FINALIZE_CANDIDATE"
    candidate_id: UUID


class CompleteQuestionDecision(Contract):
    kind: Literal["COMPLETE_QUESTION"] = "COMPLETE_QUESTION"
    question_id: UUID


type OntoCodexDecision = Annotated[
    CreateQuestionDecision
    | StartCampaignDecision
    | ExecuteCapabilityDecision
    | ComposeEvidenceDecision
    | RequestWideDecision
    | InvestigateCandidateDecision
    | ExecuteFollowUpDecision
    | FinalizeCandidateDecision
    | CompleteQuestionDecision,
    Field(discriminator="kind"),
]
