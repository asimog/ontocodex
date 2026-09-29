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

## Scientific Engine

```text
scientific scope → registered scientific capabilities → typed evidence
→ StatisticalState → Wide Jev → Candidate → EvidenceState → Deep Jev
→ follow-up / hypothesis / replication → Stage 8 → Dossier
```

## Runtime

```text
CapabilityOffer → ResearchRun → bounded execution → persistence / provenance
→ recovery → next OntoCodex decision
```

One scheduler advances one validated decision per run. SQLite owns indexed metadata;
content-addressed artifacts own scientific payloads.

## Engineering

```text
CapabilityGap → isolated engineering → verification → registration → resume
```

The bootstrap defines this boundary but does not implement self-engineering. Scientific
OntoCodex never receives repository or shell access.

