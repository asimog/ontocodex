"""Restricted deterministic director used to prove the bootstrap lifecycle."""

from __future__ import annotations

from dataclasses import dataclass

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
    RequestWideDecision,
    ResearchPortfolio,
    ResearchProgram,
    ResearchQuestion,
    ScientificEvidence,
    StartCampaignDecision,
    StatisticalState,
)


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


class Director:
    """A deterministic stand-in for restricted scientific OntoCodex."""

    def decide(self, context: DirectorContext) -> OntoCodexDecision:
        question = context.active_question
        if question is None:
            number = len(context.portfolio.question_ids) + 1
            return CreateQuestionDecision(question=f"Synthetic research question {number}")
        if context.campaign is None:
            return StartCampaignDecision(question_id=question.question_id)
        if context.statistical_state is None:
            if context.campaign_offers:
                return ExecuteCapabilityDecision(offer=context.campaign_offers[0])
            return ComposeEvidenceDecision(
                campaign_id=context.campaign.campaign_id,
                evidence_refs=tuple(item.evidence_id for item in context.evidence),
            )
        if context.candidate is None:
            return RequestWideDecision(state_id=context.statistical_state.state_id)
        if context.evidence_state is None or context.deep_decision is None:
            return InvestigateCandidateDecision(candidate_id=context.candidate.candidate_id)
        if context.deep_decision.next_move == "FOLLOW_UP":
            if not context.follow_up_offers:
                raise RuntimeError("Deep requested follow-up but no eligible offer exists")
            return ExecuteFollowUpDecision(
                candidate_id=context.candidate.candidate_id,
                offer=context.follow_up_offers[0],
            )
        if context.dossier is None:
            return FinalizeCandidateDecision(candidate_id=context.candidate.candidate_id)
        return CompleteQuestionDecision(question_id=question.question_id)
