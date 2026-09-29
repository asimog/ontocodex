# OntoJev Architecture

OntoJev has one scheduler and one scientific-state architecture. **The scientific engine
contains no mandatory predefined modality sequence.**

## Autonomous Research Director

```text
ResearchProgram → ResearchPortfolio → ResearchQuestion → Campaign → OntoCodex
```

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

