"""Small append-only SQLite repository and immutable artifact store."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel

from ontojev.domain.models import ArtifactRef, ResearchRun, RunStatus, utc_now

ModelT = TypeVar("ModelT", bound=BaseModel)


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class ArtifactIntegrityError(RuntimeError):
    pass


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root / "artifacts" / "sha256"
        self.root.mkdir(parents=True, exist_ok=True)

    def publish_bytes(self, content: bytes, *, media_type: str, suffix: str) -> ArtifactRef:
        digest = hashlib.sha256(content).hexdigest()
        relative = Path("artifacts") / "sha256" / digest[:2] / f"{digest}{suffix}"
        target = self.root.parent.parent / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            descriptor, temporary_name = tempfile.mkstemp(dir=target.parent, prefix=".publish-")
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_name, target)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        return ArtifactRef(sha256=digest, media_type=media_type, relative_path=relative.as_posix())

    def publish_model(self, model: BaseModel) -> ArtifactRef:
        return self.publish_bytes(
            canonical_json(model.model_dump(mode="json")),
            media_type="application/json",
            suffix=".json",
        )

    def read(self, reference: ArtifactRef) -> bytes:
        path = self.root.parent.parent / reference.relative_path
        if not path.is_file():
            raise ArtifactIntegrityError(f"missing artifact {reference.artifact_id}")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != reference.sha256:
            raise ArtifactIntegrityError(f"corrupt artifact {reference.artifact_id}")
        return content


class Repository:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.database_path = root / "ontojev.sqlite3"
        self.artifacts = ArtifactStore(root)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS records (
                    kind TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    parent_id TEXT,
                    payload_json TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (kind, record_id, revision)
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    relative_path TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save(
        self,
        kind: str,
        record_id: UUID,
        model: BaseModel,
        *,
        parent_id: UUID | None = None,
    ) -> int:
        payload = canonical_json(model.model_dump(mode="json"))
        digest = hashlib.sha256(payload).hexdigest()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(revision), -1) AS revision "
                "FROM records WHERE kind=? AND record_id=?",
                (kind, str(record_id)),
            ).fetchone()
            revision = int(row["revision"]) + 1
            connection.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    kind,
                    str(record_id),
                    revision,
                    str(parent_id) if parent_id else None,
                    payload.decode(),
                    digest,
                    utc_now().isoformat(),
                ),
            )
        return revision

    def load_latest(self, kind: str, record_id: UUID, model_type: type[ModelT]) -> ModelT | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM records WHERE kind=? AND record_id=? "
                "ORDER BY revision DESC LIMIT 1",
                (kind, str(record_id)),
            ).fetchone()
        return None if row is None else model_type.model_validate_json(row["payload_json"])

    def list_latest(self, kind: str, model_type: type[ModelT]) -> tuple[ModelT, ...]:
        query = """
            SELECT records.payload_json FROM records
            JOIN (
                SELECT record_id, MAX(revision) AS revision FROM records
                WHERE kind=? GROUP BY record_id
            ) latest ON records.record_id=latest.record_id AND records.revision=latest.revision
            WHERE records.kind=? ORDER BY records.created_at, records.record_id
        """
        with self._connect() as connection:
            rows = connection.execute(query, (kind, kind)).fetchall()
        return tuple(model_type.model_validate_json(row["payload_json"]) for row in rows)

    def register_artifact(self, reference: ArtifactRef) -> None:
        self.artifacts.read(reference)
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO artifacts VALUES (?, ?, ?, ?, ?)",
                (
                    str(reference.artifact_id),
                    reference.sha256,
                    reference.media_type,
                    reference.relative_path,
                    utc_now().isoformat(),
                ),
            )

    def recover_running_runs(self) -> int:
        recovered = 0
        for run in self.list_latest("research_run", ResearchRun):
            if run.status is RunStatus.RUNNING:
                interrupted = run.model_copy(
                    update={
                        "status": RunStatus.INTERRUPTED,
                        "finished_at": utc_now(),
                        "error": "process ended before terminal publication",
                    }
                )
                self.save("research_run", run.run_id, interrupted)
                recovered += 1
        return recovered
