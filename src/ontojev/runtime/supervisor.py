"""Hard-deadline execution in a killable child process."""

from __future__ import annotations

import multiprocessing
from dataclasses import dataclass
from multiprocessing.queues import Queue
from typing import Any, cast

from ontojev.capabilities.registry import ExecutableCapability
from ontojev.domain.models import CapabilityOffer, CapabilityResult, Completeness


class CapabilityTimeout(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeLimits:
    timeout_seconds: float = 600
    finalization_reserve_seconds: float = 30

    def __post_init__(self) -> None:
        if (
            self.timeout_seconds <= 0
            or not 0 < self.finalization_reserve_seconds < self.timeout_seconds
        ):
            raise ValueError("finalization reserve must be positive and below the hard timeout")

    @property
    def execution_seconds(self) -> float:
        return self.timeout_seconds - self.finalization_reserve_seconds


def _child_execute(
    capability: ExecutableCapability, offer: CapabilityOffer, queue: Queue[Any]
) -> None:
    try:
        payload = capability.execute(offer)
        queue.put(("ok", payload.model_dump(mode="json")))
    except BaseException as error:
        queue.put(("error", f"{type(error).__name__}: {error}"))


class BoundedExecutor:
    def __init__(self, limits: RuntimeLimits) -> None:
        self.limits = limits

    def execute(self, capability: ExecutableCapability, offer: CapabilityOffer) -> CapabilityResult:
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        process = context.Process(target=_child_execute, args=(capability, offer, queue))
        process.start()
        process.join(self.limits.execution_seconds)
        if process.is_alive():
            process.terminate()
            process.join(self.limits.finalization_reserve_seconds)
            if process.is_alive():
                process.kill()
                process.join()
            raise CapabilityTimeout(f"capability exceeded {self.limits.execution_seconds} seconds")
        if queue.empty():
            raise RuntimeError(f"capability process exited with code {process.exitcode}")
        status, value = cast(tuple[str, object], queue.get())
        if status != "ok":
            raise RuntimeError(str(value))
        definition = capability.definition
        payload = capability.result_model.model_validate(value)
        return CapabilityResult(
            capability_id=definition.capability_id,
            capability_version=definition.version,
            output_contract=definition.output_contract,
            payload=payload.model_dump(mode="json"),
            completeness=Completeness.COMPLETE,
            limitations=definition.limitations,
        )
