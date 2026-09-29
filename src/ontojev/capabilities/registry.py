"""Typed capability registry and deterministic bootstrap capabilities."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ontojev.domain.models import (
    Campaign,
    Capability,
    CapabilityOffer,
    CapabilityResult,
    Completeness,
    ScientificEvidence,
)
from ontojev.storage.repository import canonical_json


class CapabilityError(RuntimeError):
    pass


class ResultContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ScalarPatternResult(ResultContract):
    label: str
    magnitude: float
    units: str


class PairwiseRelationResult(ResultContract):
    left: str
    right: str
    relation: str
    strength: float = Field(ge=0, le=1)


class CategoricalProfileResult(ResultContract):
    categories: tuple[str, ...]
    weights: tuple[float, ...]

    @model_validator(mode="after")
    def matching_lengths(self) -> CategoricalProfileResult:
        if not self.categories or len(self.categories) != len(self.weights):
            raise ValueError("categories and weights must be non-empty and aligned")
        return self


class FollowUpResult(ResultContract):
    observation: str
    resolved_gap: str


class ExecutableCapability(Protocol):
    definition: Capability
    result_model: type[ResultContract]

    def execute(self, offer: CapabilityOffer) -> ResultContract: ...


def _offer_digest(
    definition: Capability,
    campaign: Campaign,
    phase: Literal["CAMPAIGN", "CANDIDATE"],
    input_refs: tuple[str, ...],
) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "capability": definition.model_dump(mode="json"),
                "campaign_id": str(campaign.campaign_id),
                "scope_id": str(campaign.scope.scope_id),
                "phase": phase,
                "input_refs": input_refs,
            }
        )
    ).hexdigest()


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, ExecutableCapability] = {}
        self._result_models: dict[str, type[ResultContract]] = {}

    def register(self, capability: ExecutableCapability) -> None:
        definition = capability.definition
        if definition.capability_id in self._capabilities:
            raise CapabilityError(f"duplicate capability {definition.capability_id}")
        if definition.output_contract in self._result_models:
            raise CapabilityError(f"duplicate result contract {definition.output_contract}")
        self._capabilities[definition.capability_id] = capability
        self._result_models[definition.output_contract] = capability.result_model

    def offers(
        self,
        campaign: Campaign,
        evidence: Iterable[ScientificEvidence],
        *,
        phase: Literal["CAMPAIGN", "CANDIDATE"],
        input_refs: tuple[str, ...] = (),
    ) -> tuple[CapabilityOffer, ...]:
        evidence_items = tuple(evidence)
        existing_types = {item.evidence_type for item in evidence_items}
        bound_refs = tuple(str(item.evidence_id) for item in evidence_items) + input_refs
        offers: list[CapabilityOffer] = []
        for capability_id in sorted(self._capabilities):
            definition = self._capabilities[capability_id].definition
            if definition.supported_phase != phase:
                continue
            if definition.evidence_type_produced in existing_types:
                continue
            if not set(definition.prerequisites).issubset(existing_types):
                continue
            digest = _offer_digest(definition, campaign, phase, bound_refs)
            offers.append(
                CapabilityOffer(
                    capability_id=definition.capability_id,
                    capability_version=definition.version,
                    campaign_id=campaign.campaign_id,
                    scope_id=campaign.scope.scope_id,
                    phase=phase,
                    input_refs=tuple(item.evidence_id for item in evidence_items),
                    offer_digest=digest,
                )
            )
        return tuple(offers)

    def validate_offer(
        self,
        offer: CapabilityOffer,
        campaign: Campaign,
        evidence: Iterable[ScientificEvidence],
        *,
        phase: Literal["CAMPAIGN", "CANDIDATE"],
        input_refs: tuple[str, ...] = (),
    ) -> ExecutableCapability:
        capability = self._capabilities.get(offer.capability_id)
        if capability is None:
            raise CapabilityError(f"unregistered capability {offer.capability_id}")
        definition = capability.definition
        evidence_items = tuple(evidence)
        existing_types = {item.evidence_type for item in evidence_items}
        bound_refs = tuple(str(item.evidence_id) for item in evidence_items) + input_refs
        expected = _offer_digest(definition, campaign, phase, bound_refs)
        expected_input_refs = tuple(item.evidence_id for item in evidence_items)
        if (
            offer.campaign_id != campaign.campaign_id
            or offer.scope_id != campaign.scope.scope_id
            or offer.phase != phase
            or offer.input_refs != expected_input_refs
            or offer.capability_version != definition.version
            or offer.offer_digest != expected
            or definition.supported_phase != phase
            or definition.evidence_type_produced in existing_types
            or not set(definition.prerequisites).issubset(existing_types)
        ):
            raise CapabilityError("stale, mutated, or ineligible capability offer")
        return capability

    def execute(self, capability: ExecutableCapability, offer: CapabilityOffer) -> CapabilityResult:
        payload = capability.execute(offer)
        validated = capability.result_model.model_validate(payload.model_dump())
        definition = capability.definition
        return CapabilityResult(
            capability_id=definition.capability_id,
            capability_version=definition.version,
            output_contract=definition.output_contract,
            payload=validated.model_dump(mode="json"),
            completeness=Completeness.COMPLETE,
            limitations=definition.limitations,
        )

    def validate_result(self, result: CapabilityResult) -> ResultContract:
        model = self._result_models.get(result.output_contract)
        if model is None:
            raise CapabilityError(f"unregistered result contract {result.output_contract}")
        return model.model_validate(result.payload)

    def definition(self, capability_id: str) -> Capability:
        try:
            return self._capabilities[capability_id].definition
        except KeyError as error:
            raise CapabilityError(f"unregistered capability {capability_id}") from error


class ScalarPatternCapability:
    result_model: type[ResultContract] = ScalarPatternResult
    definition = Capability(
        capability_id="bootstrap.scalar-pattern",
        version="1.0.0",
        scientific_purpose="produce a synthetic scalar pattern",
        evidence_type_produced="bootstrap.scalar-pattern.v1",
        supported_phase="CAMPAIGN",
        supported_scope="any synthetic bootstrap scope",
        prerequisites=(),
        input_contract="ontojev.scope.v1",
        output_contract="bootstrap.scalar-pattern-result.v1",
        expected_cost=1,
        expected_runtime_seconds=0.01,
        completeness_semantics="one deterministic complete synthetic observation",
        limitations=("synthetic bootstrap evidence",),
    )

    def execute(self, offer: CapabilityOffer) -> ResultContract:
        return ScalarPatternResult(label="alpha", magnitude=0.75, units="synthetic-unit")


class PairwiseRelationCapability:
    result_model: type[ResultContract] = PairwiseRelationResult
    definition = Capability(
        capability_id="bootstrap.pairwise-relation",
        version="1.0.0",
        scientific_purpose="produce a synthetic pairwise relation",
        evidence_type_produced="bootstrap.pairwise-relation.v1",
        supported_phase="CAMPAIGN",
        supported_scope="any synthetic bootstrap scope",
        prerequisites=("bootstrap.scalar-pattern.v1",),
        input_contract="ontojev.evidence-refs.v1",
        output_contract="bootstrap.pairwise-relation-result.v1",
        expected_cost=1,
        expected_runtime_seconds=0.01,
        completeness_semantics="one deterministic complete synthetic relation",
        limitations=("synthetic bootstrap evidence",),
    )

    def execute(self, offer: CapabilityOffer) -> ResultContract:
        return PairwiseRelationResult(left="alpha", right="beta", relation="aligned", strength=0.8)


class CategoricalProfileCapability:
    result_model: type[ResultContract] = CategoricalProfileResult
    definition = Capability(
        capability_id="bootstrap.categorical-profile",
        version="1.0.0",
        scientific_purpose="produce a third heterogeneous synthetic schema",
        evidence_type_produced="bootstrap.categorical-profile.v1",
        supported_phase="CAMPAIGN",
        supported_scope="any synthetic bootstrap scope",
        prerequisites=("bootstrap.pairwise-relation.v1",),
        input_contract="ontojev.evidence-refs.v1",
        output_contract="bootstrap.categorical-profile-result.v1",
        expected_cost=1,
        expected_runtime_seconds=0.01,
        completeness_semantics="a complete deterministic synthetic category profile",
        limitations=("synthetic bootstrap evidence",),
    )

    def execute(self, offer: CapabilityOffer) -> ResultContract:
        return CategoricalProfileResult(categories=("x", "y", "z"), weights=(0.2, 0.3, 0.5))


class FollowUpCapability:
    result_model: type[ResultContract] = FollowUpResult
    definition = Capability(
        capability_id="bootstrap.follow-up",
        version="1.0.0",
        scientific_purpose="resolve one synthetic Candidate evidence gap",
        evidence_type_produced="bootstrap.follow-up.v1",
        supported_phase="CANDIDATE",
        supported_scope="any synthetic bootstrap Candidate",
        prerequisites=(),
        input_contract="ontojev.evidence-state.v1",
        output_contract="bootstrap.follow-up-result.v1",
        expected_cost=1,
        expected_runtime_seconds=0.01,
        completeness_semantics="one deterministic complete synthetic follow-up",
        limitations=("synthetic bootstrap evidence",),
    )

    def execute(self, offer: CapabilityOffer) -> ResultContract:
        return FollowUpResult(observation="synthetic follow-up complete", resolved_gap="robustness")


def bootstrap_registry(*, include_third: bool = True) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(ScalarPatternCapability())
    registry.register(PairwiseRelationCapability())
    if include_third:
        registry.register(CategoricalProfileCapability())
    registry.register(FollowUpCapability())
    return registry
