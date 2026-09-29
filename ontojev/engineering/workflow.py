"""Promotion boundary for externally built and independently verified capability packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from ontojev.domain.models import (
    CapabilityGap,
    CapabilityPackageManifest,
    EngineeringTask,
    ResearchQuestion,
)
from ontojev.storage.repository import Repository


class EngineeringError(RuntimeError):
    pass


class EngineeringService:
    """Record packages proven by an external isolated verifier; never import them dynamically."""

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def propose(
        self,
        question_id: UUID,
        *,
        scientific_need: str,
        missing_capability: str,
        required_method: str,
        existing_limit: str,
    ) -> EngineeringTask:
        if self.repository.load_latest("question", question_id, ResearchQuestion) is None:
            raise EngineeringError("capability gap must belong to a durable ResearchQuestion")
        gap = CapabilityGap(
            question_id=question_id,
            scientific_need=scientific_need,
            missing_capability=missing_capability,
            required_evidence_or_method=required_method,
            existing_capability_limit=existing_limit,
        )
        task = EngineeringTask(gap_id=gap.gap_id)
        self.repository.save("capability_gap", gap.gap_id, gap)
        self.repository.save("engineering_task", task.task_id, task)
        return task

    def verify(
        self,
        task_id: UUID,
        manifest_path: Path,
        package_path: Path,
        receipt_path: Path,
    ) -> EngineeringTask:
        task = self.repository.load_latest("engineering_task", task_id, EngineeringTask)
        if task is None or task.status != "PROPOSED":
            raise EngineeringError("only a proposed engineering task can be verified")
        manifest = CapabilityPackageManifest.model_validate_json(manifest_path.read_bytes())
        package = package_path.read_bytes()
        receipt = receipt_path.read_bytes()
        if hashlib.sha256(package).hexdigest() != manifest.package_sha256:
            raise EngineeringError("capability package digest does not match its manifest")
        if hashlib.sha256(receipt).hexdigest() != manifest.verification_sha256:
            raise EngineeringError("verification receipt digest does not match its manifest")
        receipt_data = json.loads(receipt)
        if (
            receipt_data.get("exit_code") != 0
            or tuple(receipt_data.get("command", ())) != manifest.verification_command
            or receipt_data.get("package_sha256") != manifest.package_sha256
        ):
            raise EngineeringError("external verification receipt is not successful or bound")
        package_ref = self.repository.artifacts.publish_bytes(
            package, media_type="application/zip", suffix=".zip"
        )
        receipt_ref = self.repository.artifacts.publish_bytes(
            receipt, media_type="application/json", suffix=".json"
        )
        self.repository.register_artifact(package_ref)
        self.repository.register_artifact(receipt_ref)
        verified = task.model_copy(
            update={
                "status": "VERIFIED",
                "verified_tree_identity": manifest.package_sha256,
                "package_ref": package_ref,
                "verification_ref": receipt_ref,
            }
        )
        self.repository.save("engineering_task", task.task_id, verified)
        self.repository.save("capability_package", package_ref.artifact_id, manifest)
        return verified

    def activate(self, task_id: UUID, *, verified_tree_identity: str) -> EngineeringTask:
        task = self.repository.load_latest("engineering_task", task_id, EngineeringTask)
        if (
            task is None
            or task.status != "VERIFIED"
            or task.verified_tree_identity != verified_tree_identity
            or task.package_ref is None
            or task.verification_ref is None
        ):
            raise EngineeringError("task is not verified for the requested tree identity")
        self.repository.artifacts.read(task.package_ref)
        self.repository.artifacts.read(task.verification_ref)
        activated = task.model_copy(update={"status": "ACTIVATED"})
        self.repository.save("engineering_task", task.task_id, activated)
        return activated
