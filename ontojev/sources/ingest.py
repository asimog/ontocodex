"""Bounded, digest-pinned ingestion for operator-adopted research sources."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from uuid import UUID

from ontojev.domain.models import (
    LiteratureContext,
    Provenance,
    ProvenanceCategory,
    ResearchProgram,
    SourceManifest,
    SourceSnapshot,
)
from ontojev.storage.repository import Repository


class SourceError(RuntimeError):
    pass


class SourceService:
    """Import immutable local data after schema, size, and digest preflight."""

    def __init__(self, repository: Repository, *, max_bytes: int = 100_000_000) -> None:
        self.repository = repository
        self.max_bytes = max_bytes

    def import_csv(self, manifest_path: Path, data_path: Path) -> SourceSnapshot:
        manifest = SourceManifest.model_validate_json(manifest_path.read_bytes())
        program = self._active_program()
        if manifest.cancer_scope != program.cancer_scope:
            raise SourceError("source cancer scope does not match the ResearchProgram")
        existing = self.repository.list_latest("source_snapshot", SourceSnapshot)
        if any(
            item.snapshot_id in program.source_snapshot_ids
            and item.manifest.cohort_role is manifest.cohort_role
            for item in existing
        ):
            raise SourceError(f"a {manifest.cohort_role.value} source is already adopted")
        size = data_path.stat().st_size
        if size <= 0 or size > self.max_bytes:
            raise SourceError(f"source size {size} is outside the permitted bound")
        content = data_path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != manifest.sha256:
            raise SourceError("source digest does not match the adopted manifest")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise SourceError("source must be UTF-8 CSV") from error
        reader = csv.DictReader(io.StringIO(text))
        columns = set(reader.fieldnames or ())
        missing_columns = set(manifest.required_columns) - columns
        if missing_columns:
            raise SourceError(f"source is missing columns: {', '.join(sorted(missing_columns))}")
        row_count = observed_rows = missing_rows = 0
        for row in reader:
            row_count += 1
            status = (row.get("status") or "").strip().lower()
            if not (row.get("sample_id") or "").strip() or not (row.get("feature") or "").strip():
                raise SourceError(f"row {row_count} lacks sample_id or feature")
            if status in {
                "1",
                "true",
                "altered",
                "positive",
                "0",
                "false",
                "unaltered",
                "negative",
            }:
                observed_rows += 1
            elif status in {"", "na", "n/a", "null", "missing"}:
                missing_rows += 1
            else:
                raise SourceError(f"row {row_count} has unsupported status {status!r}")
        if row_count == 0:
            raise SourceError("source contains no data rows")
        data_ref = self.repository.artifacts.publish_bytes(
            content, media_type="text/csv", suffix=".csv"
        )
        self.repository.register_artifact(data_ref)
        snapshot = SourceSnapshot(
            manifest=manifest,
            data_ref=data_ref,
            row_count=row_count,
            observed_rows=observed_rows,
            missing_rows=missing_rows,
        )
        self.repository.save("source_snapshot", snapshot.snapshot_id, snapshot)
        self._attach_to_program(snapshot)
        return snapshot

    def import_literature(
        self, program_id: UUID, *, citation: str, persistent_id: str, relevance: str, path: Path
    ) -> LiteratureContext:
        content = path.read_bytes()
        if not content or len(content) > self.max_bytes:
            raise SourceError("literature artifact is empty or exceeds the permitted bound")
        reference = self.repository.artifacts.publish_bytes(
            content,
            media_type="application/pdf" if path.suffix.lower() == ".pdf" else "text/plain",
            suffix=path.suffix.lower() or ".txt",
        )
        self.repository.register_artifact(reference)
        context = LiteratureContext(
            program_id=program_id,
            citation=citation,
            persistent_id=persistent_id,
            relevance=relevance,
            artifact_ref=reference,
            provenance=Provenance(
                category=ProvenanceCategory.EXTERNAL_LITERATURE_CONTEXT,
                producer_id="operator-adopted-literature",
                producer_version="1",
            ),
        )
        self.repository.save("literature_context", context.literature_id, context)
        return context

    def _attach_to_program(self, snapshot: SourceSnapshot) -> None:
        program = self._active_program()
        if snapshot.manifest.cancer_scope != program.cancer_scope:
            raise SourceError("source cancer scope does not match the ResearchProgram")
        if snapshot.snapshot_id in program.source_snapshot_ids:
            return
        revised = program.model_copy(
            update={"source_snapshot_ids": (*program.source_snapshot_ids, snapshot.snapshot_id)}
        )
        self.repository.save("program", program.program_id, revised)

    def _active_program(self) -> ResearchProgram:
        active = tuple(
            item for item in self.repository.list_latest("program", ResearchProgram) if item.active
        )
        if len(active) != 1:
            raise SourceError("source import requires exactly one active ResearchProgram")
        return active[0]


def load_manifest(path: Path) -> SourceManifest:
    try:
        return SourceManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise SourceError(f"invalid source manifest: {error}") from error
