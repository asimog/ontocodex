"""Restricted OntoCodex context, decision validation, and offline director."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from ontojev.domain.models import (
    Campaign,
    Candidate,
    CapabilityOffer,
    CompleteQuestionDecision,
    ComposeEvidenceDecision,
    CreateQuestionDecision,
    DeepDecision,
    DossierMetadata,
    EvidenceState,
    ExecuteCapabilityDecision,
    ExecuteFollowUpDecision,
    FinalizeCandidateDecision,
    InvestigateCandidateDecision,
    OntoCodexDecision,
    OntoCodexInvocation,
    RequestWideDecision,
    ResearchPortfolio,
    ResearchProgram,
    ResearchQuestion,
    ScientificEvidence,
    StartCampaignDecision,
    StatisticalState,
)
from ontojev.storage.repository import canonical_json


class InvalidResearchDecision(RuntimeError):
    pass


@dataclass(frozen=True)
class DirectorContext:
    program: ResearchProgram
    portfolio: ResearchPortfolio
    active_question: ResearchQuestion | None
    campaign: Campaign | None
    evidence: tuple[ScientificEvidence, ...]
    statistical_state: StatisticalState | None
    candidate: Candidate | None
    evidence_state: EvidenceState | None
    deep_decision: DeepDecision | None
    dossier: DossierMetadata | None
    campaign_offers: tuple[CapabilityOffer, ...]
    follow_up_offers: tuple[CapabilityOffer, ...]


class Director(Protocol):
    @property
    def last_invocation(self) -> OntoCodexInvocation: ...

    def decide(self, context: DirectorContext) -> OntoCodexDecision: ...


def project_context(context: DirectorContext, *, item_limit: int = 25) -> dict[str, object]:
    """Build a bounded projection without result payloads or filesystem state."""

    evidence = context.evidence[-item_limit:]
    campaign_offers = context.campaign_offers[:item_limit]
    follow_up_offers = context.follow_up_offers[:item_limit]
    return {
        "contract": "ontojev.director-context.v1",
        "program": {
            "program_id": str(context.program.program_id),
            "name": context.program.name,
            "purpose": context.program.purpose,
        },
        "portfolio": {
            "portfolio_id": str(context.portfolio.portfolio_id),
            "revision": context.portfolio.revision,
            "question_count": len(context.portfolio.question_ids),
        },
        "active_question": (
            context.active_question.model_dump(mode="json") if context.active_question else None
        ),
        "campaign": context.campaign.model_dump(mode="json") if context.campaign else None,
        "evidence": [
            {
                "evidence_id": str(item.evidence_id),
                "evidence_type": item.evidence_type,
                "capability_id": item.capability_id,
                "method_version": item.method_version,
                "completeness": item.completeness.value,
                "uncertainty": item.uncertainty,
                "limitations": item.limitations,
                "result_artifact_id": str(item.result_ref.artifact_id),
            }
            for item in evidence
        ],
        "statistical_state": (
            context.statistical_state.model_dump(mode="json") if context.statistical_state else None
        ),
        "candidate": context.candidate.model_dump(mode="json") if context.candidate else None,
        "evidence_state": (
            context.evidence_state.model_dump(mode="json") if context.evidence_state else None
        ),
        "deep_decision": (
            context.deep_decision.model_dump(mode="json") if context.deep_decision else None
        ),
        "dossier": context.dossier.model_dump(mode="json") if context.dossier else None,
        "capability_offers": [item.model_dump(mode="json") for item in campaign_offers],
        "follow_up_offers": [item.model_dump(mode="json") for item in follow_up_offers],
        "omissions": {
            "evidence": max(0, len(context.evidence) - len(evidence)),
            "capability_offers": max(0, len(context.campaign_offers) - len(campaign_offers)),
            "follow_up_offers": max(0, len(context.follow_up_offers) - len(follow_up_offers)),
        },
    }


def projection_hash(context: DirectorContext) -> str:
    return hashlib.sha256(canonical_json(project_context(context))).hexdigest()


def validate_decision(decision: OntoCodexDecision, context: DirectorContext) -> None:
    question = context.active_question
    campaign = context.campaign
    state = context.statistical_state
    candidate = context.candidate
    if isinstance(decision, CreateQuestionDecision):
        valid = question is None and bool(decision.question.strip())
    elif isinstance(decision, StartCampaignDecision):
        valid = (
            question is not None
            and campaign is None
            and decision.question_id == question.question_id
        )
    elif isinstance(decision, ExecuteCapabilityDecision):
        valid = state is None and decision.offer in context.campaign_offers
    elif isinstance(decision, ComposeEvidenceDecision):
        valid = (
            campaign is not None
            and state is None
            and not context.campaign_offers
            and decision.campaign_id == campaign.campaign_id
            and decision.evidence_refs == tuple(item.evidence_id for item in context.evidence)
        )
    elif isinstance(decision, RequestWideDecision):
        valid = state is not None and candidate is None and decision.state_id == state.state_id
    elif isinstance(decision, InvestigateCandidateDecision):
        valid = (
            candidate is not None
            and context.evidence_state is not None
            and context.deep_decision is None
            and decision.candidate_id == candidate.candidate_id
        )
    elif isinstance(decision, ExecuteFollowUpDecision):
        valid = (
            candidate is not None
            and context.deep_decision is not None
            and context.deep_decision.next_move == "FOLLOW_UP"
            and decision.candidate_id == candidate.candidate_id
            and decision.offer in context.follow_up_offers
        )
    elif isinstance(decision, FinalizeCandidateDecision):
        valid = (
            candidate is not None
            and context.deep_decision is not None
            and context.deep_decision.next_move == "FINALIZE"
            and context.dossier is None
            and decision.candidate_id == candidate.candidate_id
        )
    elif isinstance(decision, CompleteQuestionDecision):
        valid = (
            question is not None
            and context.dossier is not None
            and decision.question_id == question.question_id
        )
    else:
        valid = False
    if not valid:
        raise InvalidResearchDecision(
            f"{decision.kind} is not valid for the current durable research state"
        )


class DeterministicDirector:
    """Offline director proving the same interface used by real OntoCodex."""

    def __init__(self) -> None:
        self._last_invocation: OntoCodexInvocation | None = None

    @property
    def last_invocation(self) -> OntoCodexInvocation:
        if self._last_invocation is None:
            raise RuntimeError("director has not produced a decision")
        return self._last_invocation

    def decide(self, context: DirectorContext) -> OntoCodexDecision:
        question = context.active_question
        if question is None:
            decision: OntoCodexDecision = CreateQuestionDecision(
                question=f"Synthetic research question {len(context.portfolio.question_ids) + 1}"
            )
        elif context.campaign is None:
            decision = StartCampaignDecision(question_id=question.question_id)
        elif context.statistical_state is None:
            if context.campaign_offers:
                decision = ExecuteCapabilityDecision(offer=context.campaign_offers[0])
            else:
                decision = ComposeEvidenceDecision(
                    campaign_id=context.campaign.campaign_id,
                    evidence_refs=tuple(item.evidence_id for item in context.evidence),
                )
        elif context.candidate is None:
            decision = RequestWideDecision(state_id=context.statistical_state.state_id)
        elif context.evidence_state is None or context.deep_decision is None:
            decision = InvestigateCandidateDecision(candidate_id=context.candidate.candidate_id)
        elif context.deep_decision.next_move == "FOLLOW_UP":
            if not context.follow_up_offers:
                raise RuntimeError("Deep requested follow-up but no eligible offer exists")
            decision = ExecuteFollowUpDecision(
                candidate_id=context.candidate.candidate_id,
                offer=context.follow_up_offers[0],
            )
        elif context.dossier is None:
            decision = FinalizeCandidateDecision(candidate_id=context.candidate.candidate_id)
        else:
            decision = CompleteQuestionDecision(question_id=question.question_id)
        validate_decision(decision, context)
        output = canonical_json(decision.model_dump(mode="json"))
        self._last_invocation = OntoCodexInvocation(
            director_version="deterministic-bootstrap-v1",
            codex_cli_version=None,
            provider="deterministic",
            model="deterministic-bootstrap",
            configuration_hash=hashlib.sha256(b"deterministic-bootstrap-v1").hexdigest(),
            input_projection_hash=projection_hash(context),
            output_hash=hashlib.sha256(output).hexdigest(),
            decision_kind=decision.kind,
        )
        return decision
