"""Deterministic fake Wide and Deep boundaries."""

from __future__ import annotations

from typing import Literal, Protocol

from ontojev.domain.models import (
    Candidate,
    DeepDecision,
    EvidenceState,
    Provenance,
    ProvenanceCategory,
    StatisticalState,
    WideDecision,
)


def _fake_provenance(producer: str) -> Provenance:
    return Provenance(
        category=ProvenanceCategory.JEV_JUDGMENT,
        producer_id=producer,
        producer_version="bootstrap-1",
    )


class WideEvaluatorProtocol(Protocol):
    def evaluate(self, state: StatisticalState) -> tuple[WideDecision, ...]: ...


class DeepEvaluatorProtocol(Protocol):
    def evaluate(self, candidate: Candidate, evidence_state: EvidenceState) -> DeepDecision: ...


class WideEvaluator:
    def evaluate(self, state: StatisticalState) -> tuple[WideDecision, ...]:
        if not state.evidence_refs:
            return (
                WideDecision(
                    state_id=state.state_id,
                    question_id="evidence-coherence",
                    score=0,
                    disposition="ABSTAIN",
                    rationale="no evidence references",
                    provenance=_fake_provenance("fake-wide"),
                ),
            )
        synthetic = state.maturity == "SYNTHETIC_BOOTSTRAP"
        return (
            WideDecision(
                state_id=state.state_id,
                question_id="evidence-coherence",
                score=0.9,
                disposition="ADMIT",
                rationale=(
                    "heterogeneous synthetic evidence is complete and compatible"
                    if synthetic
                    else "adopted descriptive evidence is complete and scope-compatible"
                ),
                provenance=_fake_provenance("fake-wide"),
            ),
            WideDecision(
                state_id=state.state_id,
                question_id="value-of-deeper-investigation",
                score=0.8,
                disposition="ADMIT",
                rationale=(
                    "bootstrap lifecycle requires Candidate investigation"
                    if synthetic
                    else "independent replication can test the descriptive pattern"
                ),
                provenance=_fake_provenance("fake-wide"),
            ),
        )


class DeepEvaluator:
    def evaluate(self, candidate: Candidate, evidence_state: EvidenceState) -> DeepDecision:
        move: Literal["FOLLOW_UP", "FINALIZE"] = (
            "FOLLOW_UP" if evidence_state.revision == 0 else "FINALIZE"
        )
        return DeepDecision(
            evidence_state_id=evidence_state.evidence_state_id,
            next_move=move,
            rationale=(
                f"synthetic Candidate {candidate.candidate_id} revision {evidence_state.revision}"
            ),
            provenance=_fake_provenance("fake-deep"),
        )
