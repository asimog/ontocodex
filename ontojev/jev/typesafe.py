"""Opt-in TypeSafe System One adapters for Wide and Deep Jev judgments."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from ontojev.domain.models import (
    Candidate,
    DeepDecision,
    EvidenceState,
    Provenance,
    ProvenanceCategory,
    StatisticalState,
    WideDecision,
)


class TypeSafeError(RuntimeError):
    pass


type WideDisposition = Literal["ADMIT", "DEFER", "REJECT", "ABSTAIN"]
type DeepMove = Literal["FOLLOW_UP", "HYPOTHESIS", "REPLICATE", "FINALIZE", "DEFER"]


class ChoiceAnswer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    type: str
    choice: str
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1)


class SystemOneResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    model: str
    answers: dict[str, ChoiceAnswer]


class SystemOneClient(Protocol):
    def evaluate(
        self, state: dict[str, object], questions: dict[str, object]
    ) -> SystemOneResponse: ...


@dataclass(frozen=True)
class TypeSafeConfig:
    api_key: str
    model: str = "jev-latest"
    endpoint: str = "https://api.typesafe.ai/v1/systemone"
    timeout_seconds: float = 30

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("TypeSafe API key is required")
        if self.timeout_seconds <= 0:
            raise ValueError("TypeSafe timeout must be positive")


class HttpSystemOneClient:
    def __init__(self, config: TypeSafeConfig) -> None:
        self.config = config

    def evaluate(self, state: dict[str, object], questions: dict[str, object]) -> SystemOneResponse:
        body = json.dumps(
            {"state": state, "model": self.config.model, "questions": questions},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        request = urllib.request.Request(
            self.config.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = response.read()
        except (OSError, urllib.error.HTTPError) as error:
            raise TypeSafeError(f"TypeSafe evaluation failed: {error}") from error
        try:
            return SystemOneResponse.model_validate_json(payload)
        except ValueError as error:
            raise TypeSafeError("TypeSafe returned an invalid typed response") from error


def _provenance(producer: str, model: str) -> Provenance:
    return Provenance(
        category=ProvenanceCategory.JEV_JUDGMENT,
        producer_id=producer,
        producer_version=model,
    )


class TypeSafeWideEvaluator:
    def __init__(self, client: SystemOneClient) -> None:
        self.client = client

    def evaluate(self, state: StatisticalState) -> tuple[WideDecision, ...]:
        projection: dict[str, object] = {
            "maturity": state.maturity,
            "evidence_dimensions": state.evidence_dimensions,
            "current_patterns": state.current_patterns,
            "contradictions": state.contradictions,
            "uncertainty": state.uncertainty,
            "missing_evidence": state.missing_evidence,
        }
        criteria = {
            "ADMIT": "The state supports bounded Candidate investigation, not a biological claim.",
            "DEFER": "Useful evidence is missing but later investigation may be justified.",
            "REJECT": "The state is incompatible or does not justify Candidate investigation.",
            "ABSTAIN": "The supplied bounded state is insufficient for this judgment.",
        }
        response = self.client.evaluate(
            projection,
            {
                "evidence_coherence": {
                    "type": "choice",
                    "instructions": (
                        "Judge whether the evidence state is coherent enough for "
                        "Candidate investigation."
                    ),
                    "criteria": criteria,
                },
                "investigation_value": {
                    "type": "choice",
                    "instructions": (
                        "Judge whether a bounded Candidate investigation has scientific value."
                    ),
                    "criteria": criteria,
                },
            },
        )
        decisions: list[WideDecision] = []
        for question_id in ("evidence_coherence", "investigation_value"):
            answer = response.answers.get(question_id)
            if answer is None or answer.choice not in criteria:
                raise TypeSafeError(f"missing or invalid Wide answer {question_id}")
            disposition = cast(WideDisposition, answer.choice)
            decisions.append(
                WideDecision(
                    state_id=state.state_id,
                    question_id=question_id,
                    score=answer.probabilities.get(answer.choice, 0),
                    disposition=disposition,
                    rationale=f"TypeSafe {response.model} typed Choice judgment",
                    provenance=_provenance("typesafe-wide", response.model),
                )
            )
        return tuple(decisions)


class TypeSafeDeepEvaluator:
    def __init__(self, client: SystemOneClient) -> None:
        self.client = client

    def evaluate(self, candidate: Candidate, evidence_state: EvidenceState) -> DeepDecision:
        criteria = (
            {
                "FOLLOW_UP": "A registered follow-up should address an explicit unresolved gap.",
                "DEFER": "The Candidate should stop without a completed computational case.",
            }
            if evidence_state.unresolved_gaps
            else {
                "FINALIZE": "The bounded investigation can proceed to Python Stage 8 verification.",
                "DEFER": "The Candidate should stop without a completed computational case.",
            }
        )
        response = self.client.evaluate(
            {
                "candidate_id": str(candidate.candidate_id),
                "revision": evidence_state.revision,
                "findings": evidence_state.findings,
                "contradictions": evidence_state.contradictions,
                "unresolved_gaps": evidence_state.unresolved_gaps,
                "maturity": evidence_state.maturity,
            },
            {
                "next_move": {
                    "type": "choice",
                    "instructions": (
                        "Select the bounded next move for this Candidate evidence state."
                    ),
                    "criteria": criteria,
                }
            },
        )
        answer = response.answers.get("next_move")
        if answer is None or answer.choice not in criteria:
            raise TypeSafeError("missing or invalid Deep next-move answer")
        return DeepDecision(
            evidence_state_id=evidence_state.evidence_state_id,
            next_move=cast(DeepMove, answer.choice),
            rationale=f"TypeSafe {response.model} typed Choice judgment",
            provenance=_provenance("typesafe-deep", response.model),
        )
