"""Read-only operational projection over durable laboratory state."""

from __future__ import annotations

from ontojev.domain.models import (
    Campaign,
    Candidate,
    CapabilityGap,
    DossierMetadata,
    EngineeringTask,
    ObservatorySnapshot,
    QuestionStatus,
    ResearchProgram,
    ResearchQuestion,
    ResearchRun,
    ScientificEvidence,
    SourceSnapshot,
)
from ontojev.storage.repository import Repository


def observe(repository: Repository) -> ObservatorySnapshot:
    questions = repository.list_latest("question", ResearchQuestion)
    campaigns = repository.list_latest("campaign", Campaign)
    runs = repository.list_latest("research_run", ResearchRun)
    errors: list[str] = []
    for reference in repository.list_artifacts():
        try:
            repository.artifacts.read(reference)
        except RuntimeError as error:
            errors.append(str(error))
    counts = {
        "programs": len(repository.list_latest("program", ResearchProgram)),
        "questions": len(questions),
        "campaigns": len(campaigns),
        "runs": len(runs),
        "sources": len(repository.list_latest("source_snapshot", SourceSnapshot)),
        "evidence": len(repository.list_latest("evidence", ScientificEvidence)),
        "candidates": len(repository.list_latest("candidate", Candidate)),
        "dossiers": len(repository.list_latest("dossier", DossierMetadata)),
        "capability_gaps": len(repository.list_latest("capability_gap", CapabilityGap)),
        "engineering_tasks": len(repository.list_latest("engineering_task", EngineeringTask)),
    }
    active_question = next(
        (item for item in questions if item.status is QuestionStatus.ACTIVE), None
    )
    active_campaign = next(
        (
            item
            for item in reversed(campaigns)
            if active_question and item.question_id == active_question.question_id
        ),
        None,
    )
    return ObservatorySnapshot(
        counts=counts,
        active_question_id=active_question.question_id if active_question else None,
        active_campaign_id=active_campaign.campaign_id if active_campaign else None,
        latest_run_status=runs[-1].status if runs else None,
        integrity_errors=tuple(errors),
    )
