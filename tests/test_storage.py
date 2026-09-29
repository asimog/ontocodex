from pathlib import Path

import pytest

from ontojev.domain.models import ResearchRun, RunStatus, utc_now
from ontojev.storage.repository import ArtifactIntegrityError, Repository


def test_reopen_preserves_validated_records_and_recovers_interrupted_run(tmp_path: Path) -> None:
    first = Repository(tmp_path)
    run = ResearchRun(decision_kind="fixture", status=RunStatus.RUNNING, started_at=utc_now())
    first.save("research_run", run.run_id, run)

    reopened = Repository(tmp_path)
    assert reopened.recover_running_runs() == 1
    recovered = reopened.load_latest("research_run", run.run_id, ResearchRun)
    assert recovered is not None
    assert recovered.status is RunStatus.INTERRUPTED
    assert recovered.error == "process ended before terminal publication"


def test_artifact_reader_rejects_missing_and_corrupt_content(tmp_path: Path) -> None:
    repository = Repository(tmp_path)
    reference = repository.artifacts.publish_bytes(
        b'{"valid":true}', media_type="application/json", suffix=".json"
    )
    repository.register_artifact(reference)
    path = tmp_path / reference.relative_path
    path.write_bytes(b"corrupt")

    with pytest.raises(ArtifactIntegrityError, match="corrupt artifact"):
        repository.artifacts.read(reference)
