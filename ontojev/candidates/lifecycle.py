"""Python-owned Candidate admission, revision, and Stage 8 policy."""

from __future__ import annotations

from collections.abc import Iterable

from ontojev.domain.models import (
    Candidate,
    DeepDecision,
    EvidenceState,
    FinalCandidateResult,
    ScientificEvidence,
    StatisticalState,
    WideDecision,
)


class CandidateLifecycleError(RuntimeError):
    pass


class AdmissionPolicy:
    def admit(self, state: StatisticalState, decisions: Iterable[WideDecision]) -> Candidate | None:
        evaluated = tuple(decisions)
        if not evaluated or any(item.disposition != "ADMIT" for item in evaluated):
            return None
        return Candidate(
            campaign_id=state.campaign_id,
            source_state_id=state.state_id,
            admission_decision_ids=tuple(item.decision_id for item in evaluated),
        )


def initial_evidence_state(candidate: Candidate, state: StatisticalState) -> EvidenceState:
    return EvidenceState(
        candidate_id=candidate.candidate_id,
        revision=0,
        previous_evidence_state_id=None,
        evidence_refs=state.evidence_refs,
        findings=("admitted from compatible synthetic StatisticalState",),
        contradictions=state.contradictions,
        unresolved_gaps=("robustness",),
        judgment_refs=candidate.admission_decision_ids,
        maturity="SYNTHETIC_CANDIDATE",
    )


def revise_evidence_state(
    previous: EvidenceState, evidence: ScientificEvidence, deep: DeepDecision
) -> EvidenceState:
    if deep.evidence_state_id != previous.evidence_state_id or deep.next_move != "FOLLOW_UP":
        raise CandidateLifecycleError("follow-up is not authorized by the current Deep decision")
    return EvidenceState(
        candidate_id=previous.candidate_id,
        revision=previous.revision + 1,
        previous_evidence_state_id=previous.evidence_state_id,
        evidence_refs=(*previous.evidence_refs, evidence.evidence_id),
        findings=(*previous.findings, "synthetic follow-up resolved the robustness gap"),
        contradictions=previous.contradictions,
        unresolved_gaps=(),
        judgment_refs=(*previous.judgment_refs, deep.decision_id),
        maturity="SYNTHETIC_FOLLOW_UP_COMPLETE",
    )


class Stage8:
    def finalize(
        self,
        candidate: Candidate,
        history: Iterable[EvidenceState],
        deep_decision: DeepDecision,
    ) -> FinalCandidateResult:
        revisions = tuple(sorted(history, key=lambda item: item.revision))
        if not revisions or revisions[0].revision != 0:
            raise CandidateLifecycleError("EvidenceState history must begin at revision zero")
        for index, revision in enumerate(revisions):
            if revision.candidate_id != candidate.candidate_id or revision.revision != index:
                raise CandidateLifecycleError("EvidenceState history is incomplete or inconsistent")
            expected_parent = None if index == 0 else revisions[index - 1].evidence_state_id
            if revision.previous_evidence_state_id != expected_parent:
                raise CandidateLifecycleError("EvidenceState lineage is broken")
        final = revisions[-1]
        if final.unresolved_gaps or deep_decision.evidence_state_id != final.evidence_state_id:
            raise CandidateLifecycleError("Candidate is not ready for Stage 8")
        if deep_decision.next_move != "FINALIZE":
            raise CandidateLifecycleError("Deep has not selected finalization")
        return FinalCandidateResult(
            candidate_id=candidate.candidate_id,
            final_evidence_state_id=final.evidence_state_id,
            disposition="COMPUTATIONAL_CASE_COMPLETE",
            stopping_rationale="deterministic bootstrap lifecycle completed",
            limitations=("synthetic evidence only", "not a therapeutic validation"),
        )
