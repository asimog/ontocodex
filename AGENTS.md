# Repository Guidelines

## Product Boundary

- OntoJev is a persistent autonomous computational cancer-research laboratory.
- OntoJev is cancer-general.
- Lung cancer is the first future scientific focus only.
- Never encode a cancer type into core runtime contracts.
- Never privilege an evidence modality or analysis family.
- Bootstrap capabilities are deterministic and synthetic.
- Bootstrap output is not biological evidence.
- A dossier is a computational case, not therapeutic validation.

## Authority

- Humans bound programs, sources, budgets, credentials, and deployment.
- OntoCodex directs research questions and scientific progression.
- OntoCodex proposes and synthesizes; it does not manufacture measurements.
- Python validates, measures, calculates, persists, and executes.
- Jev selects, scores, gates, ranks, or abstains through typed contracts.
- Wide Jev is the Campaign-level scientific judgment boundary.
- Deep Jev is the Candidate-level scientific judgment boundary.
- Candidate admission belongs to registered Python policy.
- Research-control judgment is never biological evidence.

## Architecture

- Maintain exactly one autonomous scheduler.
- Maintain exactly one scientific-state architecture.
- Campaign is scientific scope, not a scheduler.
- ResearchRun is one bounded execution attempt.
- A normal ResearchRun must not exceed 600 seconds.
- Preserve a finalization reserve inside that deadline.
- Recover interrupted work from durable state.
- Re-derive offers after recovery; never trust stale decisions.
- Capabilities expose executable science through typed contracts.
- Capability applicability must be explicit.
- Capability offers bind inputs, versions, and scope.
- ScientificEvidence references typed result artifacts.
- Core state never contains a fixed evidence-type union.
- StatisticalState references evidence rather than raw payloads.
- EvidenceState revisions are immutable and linked.
- Stage 8 verifies history before dossier creation.

## Scientific Invariants

- Missing is not zero or negative.
- Partial is not complete.
- A shard is not a population.
- Hypothesis is not evidence.
- Literature is contextual, not internal measurement.
- Jev judgment is not measurement.
- OntoCodex judgment is not measurement.
- Model confidence is not evidence maturity.
- Numerical results come from registered methods.
- Method, threshold, cohort, scope, and interpretation changes are explicit.
- Historical evidence is never rewritten.
- Cross-scope composition requires declared compatibility.
- Cross-cancer applicability is never inferred.
- Models do not receive uncontrolled raw scientific data.
- Acquisition and execution remain bounded.

## Source Layout

- Place packages under the top-level `ontojev/` directory.
- Put stable contracts in `domain/`.
- Put scientific meaning in `science/`.
- Put executable wrappers in `capabilities/`.
- Put OntoCodex projections and decisions in `ontocodex/`.
- Put judgments in `jev/`.
- Put the single scheduler and recovery in `runtime/`.
- Put durable ownership in `storage/`.
- Put Candidate and Stage 8 logic in `candidates/`.
- Put rendering in `dossier/`.
- Do not create empty modules to imitate a diagram.

## Development

- Target Python 3.12.
- Use four-space indentation and complete type annotations.
- Use frozen Pydantic models for boundary contracts.
- Use `snake_case` for modules and functions.
- Use `PascalCase` for classes and models.
- Use `UPPER_SNAKE_CASE` for constants.
- Keep registries small and explicit.
- Reject arbitrary code and untyped evidence payloads.
- Use canonical JSON and SHA-256 for durable identity.

## Verification

- Run `uv run ruff format --check .`.
- Run `uv run ruff check .`.
- Run `uv run mypy ontojev tests` in strict mode.
- Run `uv run pytest` offline.
- Linux CI is authoritative.
- Live calls remain opt-in and absent from default CI.
- Test public behavior at its strongest owner boundary.
- Give each invariant one primary test owner.
- Avoid source greps, inventory tests, and duplicate helper assertions.
- Exercise restart behavior in a fresh process where claimed.

## Documentation

- Maintain only `README.md` and the six canonical files under `docs/`.
- Update architecture when ownership changes.
- Update scientific invariants when contracts change.
- Keep the implementation plan to the future roadmap.
- Git history is the archive; do not add checkpoint reports.

## Legacy and Engineering

- Legacy code is reference material only.
- Do not add it as a runtime or test dependency.
- Do not copy its scheduler, modality lanes, or migration machinery.
- Reuse later only after a need, receiving contract, and regression test.
- Scientific OntoCodex never edits the repository.
- Self-engineering uses a separate isolated verified workflow.
- Unverified code cannot enter scientific execution.

## Commits and Reviews

- Use focused Conventional Commits.
- State the protected invariant.
- Run focused tests before the complete gate.
- Keep changes dependency-ordered and reviewable.
- Document deferred science instead of adding placeholders.

