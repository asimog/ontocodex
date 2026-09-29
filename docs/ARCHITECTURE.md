# OntoJev Architecture

OntoJev has one scheduler and one scientific-state architecture. **The scientific engine
contains no mandatory predefined modality sequence.**

## Autonomous Research Director

```text
ResearchProgram → ResearchPortfolio → ResearchQuestion → Campaign → OntoCodex
```

Production OntoCodex is an adapter over upstream `codex exec`. It receives only a bounded typed
projection, runs outside the source checkout with read-only/no-web policy, and returns one
schema-constrained `ResearchDecision`. Python verifies that decision against the current durable
state and exact offers. Deterministic OntoCodex implements the same boundary for offline tests.
Multiple programs may coexist, but exactly one is active and owns one Portfolio at runtime.

## Scientific Engine

```text
scientific scope → registered scientific capabilities → typed evidence
→ StatisticalState → Wide Jev → Candidate → EvidenceState → Deep Jev
→ follow-up / hypothesis / replication → Stage 8 → Dossier
```

Wide and Deep can use deterministic offline evaluators or the opt-in TypeSafe System One adapter.
The live adapter submits only bounded state summaries and typed Choice questions. Returned model
confidence remains judgment metadata; Python alone admits Candidates and verifies Stage 8.

## Runtime

```text
CapabilityOffer → ResearchRun → bounded execution → persistence / provenance
→ recovery → next OntoCodex decision
```

One scheduler advances one validated decision per run. SQLite owns indexed metadata;
content-addressed artifacts own scientific payloads.

## Adopted Sources and Scientific Expansion

Operators initialize a cancer-scoped program and adopt immutable primary and replication datasets.
Preflight validates the manifest, UTF-8 CSV contract, size, row values, and SHA-256 before artifact
registration. The registered prevalence method counts observed, altered, and missing values without
imputation. Primary analysis occurs at Campaign phase; replication occurs only after Candidate
admission. Literature uses a separate contextual provenance category and never enters measurement.

## Engineering

```text
CapabilityGap → isolated engineering → verification → registration → resume
```

An external isolated builder emits a package plus verification receipt. OntoJev verifies both
digests and the bound successful command before activation of the package record. Activation does
not dynamically import code; a normal reviewed release must register executable capability code.
Scientific OntoCodex never receives repository or shell access. Observatory is read-only and checks
registered artifact integrity while projecting lifecycle counts and active work.

