from pathlib import Path

import pytest

from ontojev.capabilities.registry import CapabilityError, bootstrap_registry
from ontojev.domain.models import (
    Campaign,
    CapabilityResult,
    Completeness,
    Provenance,
    ProvenanceCategory,
    ScientificEvidence,
    ScientificScope,
)
from ontojev.storage.repository import ArtifactStore


def _campaign() -> Campaign:
    from uuid import uuid4

    return Campaign(
        question_id=uuid4(),
        scope=ScientificScope(
            program_context="synthetic",
            population="population",
            universe="universe",
            source_identity="source",
            release_identity="release",
        ),
    )


def _evidence(
    campaign: Campaign, capability_id: str, evidence_type: str, tmp_path: Path
) -> ScientificEvidence:
    store = ArtifactStore(tmp_path)
    reference = store.publish_bytes(b"{}", media_type="application/json", suffix=".json")
    return ScientificEvidence(
        evidence_type=evidence_type,
        capability_id=capability_id,
        method_version="1.0.0",
        campaign_id=campaign.campaign_id,
        scope=campaign.scope,
        result_ref=reference,
        completeness=Completeness.COMPLETE,
        uncertainty=(),
        provenance=Provenance(
            category=ProvenanceCategory.DETERMINISTICALLY_DERIVED,
            producer_id=capability_id,
            producer_version="1.0.0",
        ),
        limitations=("synthetic",),
    )


def test_registry_derives_prerequisite_order_and_rejects_stale_offer(tmp_path: Path) -> None:
    registry = bootstrap_registry(include_third=True)
    campaign = _campaign()
    first = registry.offers(campaign, (), phase="CAMPAIGN")
    assert [item.capability_id for item in first] == ["bootstrap.scalar-pattern"]

    scalar = _evidence(
        campaign, "bootstrap.scalar-pattern", "bootstrap.scalar-pattern.v1", tmp_path
    )
    second = registry.offers(campaign, (scalar,), phase="CAMPAIGN")
    assert [item.capability_id for item in second] == ["bootstrap.pairwise-relation"]

    stale = second[0].model_copy(update={"offer_digest": "0" * 64})
    with pytest.raises(CapabilityError, match="stale, mutated, or ineligible"):
        registry.validate_offer(stale, campaign, (scalar,), phase="CAMPAIGN")


def test_third_schema_extends_registry_without_core_contract_changes(tmp_path: Path) -> None:
    registry = bootstrap_registry(include_third=True)
    campaign = _campaign()
    scalar = _evidence(
        campaign, "bootstrap.scalar-pattern", "bootstrap.scalar-pattern.v1", tmp_path
    )
    pair = _evidence(
        campaign, "bootstrap.pairwise-relation", "bootstrap.pairwise-relation.v1", tmp_path
    )
    offers = registry.offers(campaign, (scalar, pair), phase="CAMPAIGN")
    assert [item.capability_id for item in offers] == ["bootstrap.categorical-profile"]
    capability = registry.validate_offer(offers[0], campaign, (scalar, pair), phase="CAMPAIGN")
    result = registry.execute(capability, offers[0])
    assert registry.validate_result(result).model_dump() == {
        "categories": ("x", "y", "z"),
        "weights": (0.2, 0.3, 0.5),
    }

    unknown = CapabilityResult(
        capability_id="unknown",
        capability_version="1",
        output_contract="unknown.result.v1",
        payload={},
        completeness=Completeness.COMPLETE,
    )
    with pytest.raises(CapabilityError, match="unregistered result contract"):
        registry.validate_result(unknown)
