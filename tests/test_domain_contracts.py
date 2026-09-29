from datetime import datetime

import pytest
from pydantic import ValidationError

from ontojev.domain.models import Provenance, ProvenanceCategory, ResearchProgram


def test_boundary_contracts_are_frozen_and_require_attributed_time() -> None:
    program = ResearchProgram(name="general", purpose="test")
    with pytest.raises(ValidationError):
        program.name = "changed"

    with pytest.raises(ValidationError, match="timezone-aware"):
        Provenance(
            category=ProvenanceCategory.OBSERVED,
            producer_id="fixture",
            producer_version="1",
            created_at=datetime(2026, 1, 1),
        )


def test_judgment_provenance_cannot_be_parsed_as_observation() -> None:
    judgment = Provenance(
        category=ProvenanceCategory.JEV_JUDGMENT,
        producer_id="wide",
        producer_version="1",
    )
    assert judgment.category is ProvenanceCategory.JEV_JUDGMENT
    assert judgment.model_dump(mode="json")["category"] == "JEV_JUDGMENT"
