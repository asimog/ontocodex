"""Deterministic fake Wide and Deep boundaries."""

from __future__ import annotations

from typing import Literal

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
        return (
            WideDecision(
                state_id=state.state_id,
                question_id="evidence-coherence",
                score=0.9,
                disposition="ADMIT",
                rationale="heterogeneous synthetic evidence is complete and compatible",
                provenance=_fake_provenance("fake-wide"),
            ),
            WideDecision(
                state_id=state.state_id,
                question_id="value-of-deeper-investigation",
                score=0.8,
                disposition="ADMIT",
                rationale="bootstrap lifecycle requires Candidate investigation",
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
