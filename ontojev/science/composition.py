"""Evidence-neutral deterministic composition."""

from __future__ import annotations

from collections.abc import Iterable

from ontojev.domain.models import Campaign, Completeness, ScientificEvidence, StatisticalState


class CompositionError(RuntimeError):
    pass


class Composer:
    def compose(
        self, campaign: Campaign, evidence_items: Iterable[ScientificEvidence]
    ) -> StatisticalState:
        evidence = tuple(evidence_items)
        if not evidence:
            raise CompositionError("composition requires evidence")
        seen_types: set[str] = set()
        for item in evidence:
            if item.campaign_id != campaign.campaign_id:
                raise CompositionError("evidence belongs to another Campaign")
            if item.scope.compatibility_key != campaign.scope.compatibility_key:
                raise CompositionError("evidence scope is incompatible")
            if item.completeness is not Completeness.COMPLETE:
                raise CompositionError("partial evidence cannot form a complete state")
            if item.evidence_type in seen_types:
                raise CompositionError("duplicate evidence dimension")
            seen_types.add(item.evidence_type)
        dimensions = tuple(sorted(seen_types))
        synthetic = all(item.evidence_type.startswith("bootstrap.") for item in evidence)
        return StatisticalState(
            campaign_id=campaign.campaign_id,
            scope=campaign.scope,
            evidence_refs=tuple(item.evidence_id for item in evidence),
            evidence_dimensions=dimensions,
            current_patterns=tuple(f"validated {item}" for item in dimensions),
            contradictions=(),
            uncertainty=(
                ("bootstrap evidence has no biological interpretation",)
                if synthetic
                else tuple(sorted({note for item in evidence for note in item.uncertainty}))
            ),
            missing_evidence=(),
            maturity="SYNTHETIC_BOOTSTRAP" if synthetic else "OBSERVATIONAL_DESCRIPTIVE",
        )
