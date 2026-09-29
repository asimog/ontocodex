"""Synthetic dossier rendering."""

from __future__ import annotations

import json

from ontojev.domain.models import DossierMetadata


class DossierRenderer:
    def render_json(self, dossier: DossierMetadata) -> bytes:
        return json.dumps(
            dossier.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False
        ).encode()

    def render_markdown(self, dossier: DossierMetadata) -> bytes:
        lines = [
            "# Synthetic OntoJev Dossier",
            "",
            "> Bootstrap-only computational evidence. Not therapeutic validation.",
            "",
            f"- Dossier: `{dossier.dossier_id}`",
            f"- Program: `{dossier.program_id}`",
            f"- Research question: `{dossier.question_id}`",
            f"- Campaign: `{dossier.campaign_id}`",
            f"- Candidate: `{dossier.candidate_id}`",
            f"- Final result: `{dossier.final_result_id}`",
            f"- Evidence items: {len(dossier.evidence_refs)}",
            f"- EvidenceState revisions: {len(dossier.evidence_state_ids)}",
            f"- Stopping rationale: {dossier.stopping_rationale}",
            "",
            "## Uncertainty",
            *[f"- {item}" for item in dossier.uncertainty],
            "",
            "## Limitations",
            *[f"- {item}" for item in dossier.limitations],
            "",
        ]
        return "\n".join(lines).encode()
