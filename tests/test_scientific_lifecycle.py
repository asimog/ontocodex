from pathlib import Path
from uuid import uuid4

import pytest

from ontojev.candidates.lifecycle import (
    AdmissionPolicy,
    CandidateLifecycleError,
    Stage8,
    initial_evidence_state,
    revise_evidence_state,
)
from ontojev.domain.models import (
    Campaign,
    Completeness,
    Provenance,
    ProvenanceCategory,
    ScientificEvidence,
    ScientificScope,
    StatisticalState,
    WideDecision,
)
from ontojev.jev.evaluators import DeepEvaluator, WideEvaluator
from ontojev.science.composition import Composer, CompositionError
from ontojev.storage.repository import ArtifactStore


def _scope() -> ScientificScope:
    return ScientificScope(
        program_context="synthetic",
        population="population",
        universe="universe",
        source_identity="source",
        release_identity="release",
    )


def _evidence(
    campaign: Campaign, evidence_type: str, tmp_path: Path, *, complete: bool = True
) -> ScientificEvidence:
    reference = ArtifactStore(tmp_path).publish_bytes(
        b"{}", media_type="application/json", suffix=".json"
    )
    return ScientificEvidence(
        evidence_type=evidence_type,
        capability_id=f"fixture.{evidence_type}",
        method_version="1",
        campaign_id=campaign.campaign_id,
        scope=campaign.scope,
        result_ref=reference,
        completeness=Completeness.COMPLETE if complete else Completeness.PARTIAL,
        uncertainty=(),
        provenance=Provenance(
            category=ProvenanceCategory.DETERMINISTICALLY_DERIVED,
            producer_id="fixture",
            producer_version="1",
        ),
        limitations=(),
    )


def test_composition_rejects_partial_and_incompatible_evidence(tmp_path: Path) -> None:
    campaign = Campaign(question_id=uuid4(), scope=_scope())
    composer = Composer()
    with pytest.raises(CompositionError, match="partial evidence"):
        composer.compose(campaign, (_evidence(campaign, "a", tmp_path, complete=False),))

    other = Campaign(question_id=uuid4(), scope=_scope())
    with pytest.raises(CompositionError, match="another Campaign"):
        composer.compose(campaign, (_evidence(other, "b", tmp_path),))


def test_python_admission_and_stage8_require_complete_revision_lineage(tmp_path: Path) -> None:
    campaign = Campaign(question_id=uuid4(), scope=_scope())
    evidence = (_evidence(campaign, "a", tmp_path), _evidence(campaign, "b", tmp_path))
    state = Composer().compose(campaign, evidence)
    wide = WideEvaluator().evaluate(state)
    candidate = AdmissionPolicy().admit(state, wide)
    assert candidate is not None
    initial = initial_evidence_state(candidate, state)
    deep_follow_up = DeepEvaluator().evaluate(candidate, initial)
    follow_up = _evidence(campaign, "follow-up", tmp_path)
    revised = revise_evidence_state(initial, follow_up, deep_follow_up)
    deep_final = DeepEvaluator().evaluate(candidate, revised)
    final = Stage8().finalize(candidate, (initial, revised), deep_final)
    assert final.disposition == "COMPUTATIONAL_CASE_COMPLETE"

    broken = revised.model_copy(update={"previous_evidence_state_id": uuid4()})
    with pytest.raises(CandidateLifecycleError, match="lineage is broken"):
        Stage8().finalize(candidate, (initial, broken), deep_final)


def test_wide_judgment_alone_never_manufactures_candidate() -> None:
    decision = WideDecision(
        state_id=uuid4(),
        question_id="fixture",
        score=0.5,
        disposition="DEFER",
        rationale="insufficient",
        provenance=Provenance(
            category=ProvenanceCategory.JEV_JUDGMENT,
            producer_id="fixture",
            producer_version="1",
        ),
    )
    assert (
        AdmissionPolicy().admit(
            state=StatisticalState(
                campaign_id=uuid4(),
                scope=_scope(),
                evidence_refs=(uuid4(),),
                evidence_dimensions=("a",),
                current_patterns=(),
                contradictions=(),
                uncertainty=(),
                missing_evidence=(),
                maturity="fixture",
            ),
            decisions=(decision,),
        )
        is None
    )
