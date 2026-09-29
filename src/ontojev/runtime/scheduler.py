"""The single autonomous scheduler for the synthetic bootstrap lifecycle."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal
from uuid import UUID

from ontojev import __version__
from ontojev.candidates.lifecycle import (
    AdmissionPolicy,
    Stage8,
    initial_evidence_state,
    revise_evidence_state,
)
from ontojev.capabilities.registry import CapabilityRegistry, bootstrap_registry
from ontojev.domain.models import (
    Campaign,
    Candidate,
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
    Provenance,
    ProvenanceCategory,
    QuestionStatus,
    RequestWideDecision,
    ResearchPortfolio,
    ResearchProgram,
    ResearchQuestion,
    ResearchRun,
    RunStatus,
    ScientificEvidence,
    ScientificScope,
    StartCampaignDecision,
    StatisticalState,
    WideDecision,
    utc_now,
)
from ontojev.dossier.renderer import DossierRenderer
from ontojev.jev.evaluators import DeepEvaluator, WideEvaluator
from ontojev.ontocodex.director import Director, DirectorContext
from ontojev.runtime.supervisor import BoundedExecutor, CapabilityTimeout, RuntimeLimits
from ontojev.science.composition import Composer
from ontojev.storage.repository import Repository


class DecisionValidationError(RuntimeError):
    pass


class Scheduler:
    def __init__(
        self,
        root: Path,
        *,
        registry: CapabilityRegistry | None = None,
        director: Director | None = None,
        limits: RuntimeLimits | None = None,
    ) -> None:
        self.repository = Repository(root)
        self.registry = registry or bootstrap_registry()
        self.director = director or Director()
        self.limits = limits or RuntimeLimits()
        self.executor = BoundedExecutor(self.limits)
        self.composer = Composer()
        self.wide = WideEvaluator()
        self.deep = DeepEvaluator()
        self.admission = AdmissionPolicy()
        self.stage8 = Stage8()
        self.renderer = DossierRenderer()

    def initialize(self) -> tuple[ResearchProgram, ResearchPortfolio]:
        programs = self.repository.list_latest("program", ResearchProgram)
        portfolios = self.repository.list_latest("portfolio", ResearchPortfolio)
        if programs or portfolios:
            if len(programs) != 1 or len(portfolios) != 1:
                raise DecisionValidationError(
                    "bootstrap requires exactly one Program and Portfolio"
                )
            return programs[0], portfolios[0]
        program = ResearchProgram(
            name="Cancer-general synthetic bootstrap",
            purpose="prove evidence-neutral autonomous research architecture",
        )
        portfolio = ResearchPortfolio(program_id=program.program_id)
        self.repository.save("program", program.program_id, program)
        self.repository.save("portfolio", portfolio.portfolio_id, portfolio)
        return program, portfolio

    def recover(self) -> int:
        return self.repository.recover_running_runs()

    def _context(self) -> DirectorContext:
        program, portfolio = self.initialize()
        questions = tuple(
            item
            for item in self.repository.list_latest("question", ResearchQuestion)
            if item.portfolio_id == portfolio.portfolio_id and item.status is QuestionStatus.ACTIVE
        )
        question = questions[0] if questions else None
        campaigns = self.repository.list_latest("campaign", Campaign)
        campaign = next(
            (item for item in campaigns if question and item.question_id == question.question_id),
            None,
        )
        all_evidence = self.repository.list_latest("evidence", ScientificEvidence)
        evidence = tuple(
            item for item in all_evidence if campaign and item.campaign_id == campaign.campaign_id
        )
        states = tuple(
            item
            for item in self.repository.list_latest("statistical_state", StatisticalState)
            if campaign and item.campaign_id == campaign.campaign_id
        )
        state = states[-1] if states else None
        candidates = tuple(
            item
            for item in self.repository.list_latest("candidate", Candidate)
            if state and item.source_state_id == state.state_id
        )
        candidate = candidates[-1] if candidates else None
        evidence_states = tuple(
            sorted(
                (
                    item
                    for item in self.repository.list_latest("evidence_state", EvidenceState)
                    if candidate and item.candidate_id == candidate.candidate_id
                ),
                key=lambda item: item.revision,
            )
        )
        evidence_state = evidence_states[-1] if evidence_states else None
        deep_decisions = self.repository.list_latest("deep_decision", DeepDecision)
        deep_decision = next(
            (
                item
                for item in reversed(deep_decisions)
                if evidence_state and item.evidence_state_id == evidence_state.evidence_state_id
            ),
            None,
        )
        dossiers = self.repository.list_latest("dossier", DossierMetadata)
        dossier = next(
            (
                item
                for item in dossiers
                if candidate and item.candidate_id == candidate.candidate_id
            ),
            None,
        )
        campaign_offers = (
            self.registry.offers(campaign, evidence, phase="CAMPAIGN")
            if campaign and state is None
            else ()
        )
        follow_up_offers = (
            self.registry.offers(
                campaign,
                evidence,
                phase="CANDIDATE",
                input_refs=(str(evidence_state.evidence_state_id),),
            )
            if campaign and candidate and evidence_state and deep_decision
            else ()
        )
        return DirectorContext(
            program=program,
            portfolio=portfolio,
            active_question=question,
            campaign=campaign,
            evidence=evidence,
            statistical_state=state,
            candidate=candidate,
            evidence_state=evidence_state,
            deep_decision=deep_decision,
            dossier=dossier,
            campaign_offers=campaign_offers,
            follow_up_offers=follow_up_offers,
        )

    def step(self) -> ResearchRun:
        self.recover()
        context = self._context()
        decision = self.director.decide(context)
        run = ResearchRun(
            campaign_id=context.campaign.campaign_id if context.campaign else None,
            decision_kind=decision.kind,
            status=RunStatus.RUNNING,
            started_at=utc_now(),
        )
        self.repository.save("research_run", run.run_id, run)
        try:
            outcome_id = self._apply(decision, context)
        except CapabilityTimeout as error:
            terminal = run.model_copy(
                update={
                    "status": RunStatus.TIMED_OUT,
                    "finished_at": utc_now(),
                    "error": str(error),
                }
            )
            self.repository.save("research_run", run.run_id, terminal)
            return terminal
        except Exception as error:
            terminal = run.model_copy(
                update={"status": RunStatus.FAILED, "finished_at": utc_now(), "error": str(error)}
            )
            self.repository.save("research_run", run.run_id, terminal)
            raise
        terminal = run.model_copy(
            update={
                "status": RunStatus.SUCCEEDED,
                "finished_at": utc_now(),
                "outcome_ref": outcome_id,
            }
        )
        self.repository.save("research_run", run.run_id, terminal)
        return terminal

    def run(self, max_runs: int) -> tuple[ResearchRun, ...]:
        if max_runs < 1:
            raise ValueError("max_runs must be positive")
        return tuple(self.step() for _ in range(max_runs))

    def _apply(self, decision: object, context: DirectorContext) -> UUID:
        if isinstance(decision, CreateQuestionDecision):
            question = ResearchQuestion(
                portfolio_id=context.portfolio.portfolio_id, question=decision.question
            )
            self.repository.save("question", question.question_id, question)
            portfolio = context.portfolio.model_copy(
                update={
                    "question_ids": (*context.portfolio.question_ids, question.question_id),
                    "revision": context.portfolio.revision + 1,
                }
            )
            self.repository.save("portfolio", portfolio.portfolio_id, portfolio)
            return question.question_id
        if isinstance(decision, StartCampaignDecision):
            if (
                not context.active_question
                or decision.question_id != context.active_question.question_id
            ):
                raise DecisionValidationError("Campaign decision targets a non-active question")
            campaign = Campaign(
                question_id=decision.question_id,
                scope=ScientificScope(
                    program_context="cancer-general synthetic bootstrap",
                    population="synthetic population",
                    universe="synthetic entities",
                    source_identity="deterministic bootstrap source",
                    release_identity="bootstrap-1",
                ),
            )
            self.repository.save("campaign", campaign.campaign_id, campaign)
            return campaign.campaign_id
        if isinstance(decision, ExecuteCapabilityDecision):
            return self._execute_capability(decision.offer, context, phase="CAMPAIGN")
        if isinstance(decision, ComposeEvidenceDecision):
            if not context.campaign or decision.campaign_id != context.campaign.campaign_id:
                raise DecisionValidationError("composition targets another Campaign")
            if decision.evidence_refs != tuple(item.evidence_id for item in context.evidence):
                raise DecisionValidationError("composition evidence projection is stale")
            for evidence in context.evidence:
                self.repository.artifacts.read(evidence.result_ref)
            state = self.composer.compose(context.campaign, context.evidence)
            self.repository.save("statistical_state", state.state_id, state)
            return state.state_id
        if isinstance(decision, RequestWideDecision):
            if (
                not context.statistical_state
                or decision.state_id != context.statistical_state.state_id
            ):
                raise DecisionValidationError("Wide decision targets a stale state")
            decisions = self.wide.evaluate(context.statistical_state)
            for item in decisions:
                self.repository.save("wide_decision", item.decision_id, item)
            candidate = self.admission.admit(context.statistical_state, decisions)
            if candidate is None:
                raise DecisionValidationError("bootstrap Wide policy did not admit a Candidate")
            self.repository.save("candidate", candidate.candidate_id, candidate)
            evidence_state = initial_evidence_state(candidate, context.statistical_state)
            self.repository.save("evidence_state", evidence_state.evidence_state_id, evidence_state)
            return candidate.candidate_id
        if isinstance(decision, InvestigateCandidateDecision):
            if not context.candidate or decision.candidate_id != context.candidate.candidate_id:
                raise DecisionValidationError("investigation targets a stale Candidate")
            if context.evidence_state is None:
                raise DecisionValidationError("Candidate has no EvidenceState")
            deep = self.deep.evaluate(context.candidate, context.evidence_state)
            self.repository.save("deep_decision", deep.decision_id, deep)
            return deep.decision_id
        if isinstance(decision, ExecuteFollowUpDecision):
            return self._execute_capability(
                decision.offer, context, phase="CANDIDATE", candidate_id=decision.candidate_id
            )
        if isinstance(decision, FinalizeCandidateDecision):
            return self._finalize(decision, context)
        if isinstance(decision, CompleteQuestionDecision):
            if (
                not context.active_question
                or decision.question_id != context.active_question.question_id
            ):
                raise DecisionValidationError("completion targets a stale question")
            answered = context.active_question.model_copy(
                update={"status": QuestionStatus.ANSWERED}
            )
            self.repository.save("question", answered.question_id, answered)
            return answered.question_id
        raise DecisionValidationError(f"unsupported decision {type(decision).__name__}")

    def _execute_capability(
        self,
        offer: object,
        context: DirectorContext,
        *,
        phase: Literal["CAMPAIGN", "CANDIDATE"],
        candidate_id: UUID | None = None,
    ) -> UUID:
        from ontojev.domain.models import CapabilityOffer

        if not isinstance(offer, CapabilityOffer) or context.campaign is None:
            raise DecisionValidationError("capability execution lacks a valid offer or Campaign")
        extra_refs = (
            (str(context.evidence_state.evidence_state_id),)
            if phase == "CANDIDATE" and context.evidence_state
            else ()
        )
        capability = self.registry.validate_offer(
            offer, context.campaign, context.evidence, phase=phase, input_refs=extra_refs
        )
        result = self.executor.execute(capability, offer)
        self.registry.validate_result(result)
        result_ref = self.repository.artifacts.publish_model(result)
        self.repository.register_artifact(result_ref)
        definition = capability.definition
        evidence = ScientificEvidence(
            evidence_type=definition.evidence_type_produced,
            capability_id=definition.capability_id,
            method_version=definition.version,
            campaign_id=context.campaign.campaign_id,
            scope=context.campaign.scope,
            result_ref=result_ref,
            completeness=result.completeness,
            uncertainty=("deterministic synthetic output",),
            provenance=Provenance(
                category=ProvenanceCategory.DETERMINISTICALLY_DERIVED,
                producer_id=definition.capability_id,
                producer_version=definition.version,
                input_refs=offer.input_refs,
            ),
            limitations=result.limitations,
        )
        self.repository.save("capability_result", result.result_id, result)
        self.repository.save("evidence", evidence.evidence_id, evidence)
        if phase == "CANDIDATE":
            if (
                context.candidate is None
                or candidate_id != context.candidate.candidate_id
                or context.evidence_state is None
                or context.deep_decision is None
            ):
                raise DecisionValidationError("follow-up targets stale Candidate state")
            revised = revise_evidence_state(context.evidence_state, evidence, context.deep_decision)
            self.repository.save(
                "evidence_state",
                revised.evidence_state_id,
                revised,
                parent_id=context.evidence_state.evidence_state_id,
            )
        return evidence.evidence_id

    def _finalize(self, decision: FinalizeCandidateDecision, context: DirectorContext) -> UUID:
        if (
            context.candidate is None
            or decision.candidate_id != context.candidate.candidate_id
            or context.deep_decision is None
            or context.active_question is None
            or context.campaign is None
        ):
            raise DecisionValidationError("Stage 8 context is incomplete or stale")
        history = tuple(
            item
            for item in self.repository.list_latest("evidence_state", EvidenceState)
            if item.candidate_id == context.candidate.candidate_id
        )
        final = self.stage8.finalize(context.candidate, history, context.deep_decision)
        self.repository.save("final_result", final.result_id, final)
        states = tuple(
            item
            for item in self.repository.list_latest("statistical_state", StatisticalState)
            if item.campaign_id == context.campaign.campaign_id
        )
        wide = tuple(
            item
            for item in self.repository.list_latest("wide_decision", WideDecision)
            if states and item.state_id == states[-1].state_id
        )
        runs = tuple(
            item
            for item in self.repository.list_latest("research_run", ResearchRun)
            if item.campaign_id == context.campaign.campaign_id
        )
        configuration = hashlib.sha256(
            f"{self.limits.timeout_seconds}:{self.limits.finalization_reserve_seconds}".encode()
        ).hexdigest()
        dossier = DossierMetadata(
            program_id=context.program.program_id,
            portfolio_id=context.portfolio.portfolio_id,
            question_id=context.active_question.question_id,
            campaign_id=context.campaign.campaign_id,
            candidate_id=context.candidate.candidate_id,
            final_result_id=final.result_id,
            run_ids=tuple(item.run_id for item in runs),
            evidence_refs=tuple(item.evidence_id for item in context.evidence),
            statistical_state_ids=tuple(item.state_id for item in states),
            evidence_state_ids=tuple(item.evidence_state_id for item in history),
            judgment_refs=tuple(item.decision_id for item in wide)
            + (context.deep_decision.decision_id,),
            uncertainty=("synthetic bootstrap evidence has no biological interpretation",),
            limitations=final.limitations,
            stopping_rationale=final.stopping_rationale,
            software_identity=f"ontojev-{__version__}",
            configuration_identity=configuration,
        )
        json_ref = self.repository.artifacts.publish_bytes(
            self.renderer.render_json(dossier), media_type="application/json", suffix=".json"
        )
        markdown_ref = self.repository.artifacts.publish_bytes(
            self.renderer.render_markdown(dossier), media_type="text/markdown", suffix=".md"
        )
        self.repository.register_artifact(json_ref)
        self.repository.register_artifact(markdown_ref)
        self.repository.save("dossier", dossier.dossier_id, dossier)
        return dossier.dossier_id

    def status(self) -> dict[str, int]:
        return {
            "programs": len(self.repository.list_latest("program", ResearchProgram)),
            "questions": len(self.repository.list_latest("question", ResearchQuestion)),
            "campaigns": len(self.repository.list_latest("campaign", Campaign)),
            "runs": len(self.repository.list_latest("research_run", ResearchRun)),
            "evidence": len(self.repository.list_latest("evidence", ScientificEvidence)),
            "candidates": len(self.repository.list_latest("candidate", Candidate)),
            "dossiers": len(self.repository.list_latest("dossier", DossierMetadata)),
        }
