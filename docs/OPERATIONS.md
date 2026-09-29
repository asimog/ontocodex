# Operations

OntoJev stores state under `ONTOJEV_DATA_ROOT` (default `.ontojev`). SQLite is the lifecycle
index; immutable JSON and Markdown artifacts are content-addressed by SHA-256. Publication uses
a temporary file, verified digest, atomic rename, then database registration.

A ResearchRun defaults to a 600-second hard limit with a 30-second finalization reserve.
Capability work receives the remaining budget. Timed-out work receives a durable terminal
outcome. At startup, abandoned `RUNNING` records become `INTERRUPTED`; the scheduler derives
fresh offers from durable state rather than trusting stale decisions.

Corrupt or missing referenced artifacts stop progression. Unregistered files are ignored.
Default operation and CI make no live model, Jev, provider, network, or paid-service calls.

## Observational Programs

Create a program with `ontojev init`, then adopt sources with `ontojev source-import`. A manifest
must include the source URI, citation, license, release, cancer scope, population, universe,
`PRIMARY` or `REPLICATION` cohort role, and exact SHA-256. Only one source of each role is admitted
per program. The data contract is UTF-8 CSV with `sample_id,feature,status`; files default to a
100 MB ingestion limit. Run `ontojev observe` for counts, active identifiers, latest run status,
and registered-artifact integrity errors.

`ontojev init` leaves additional programs inactive unless `--activate` is supplied. Switch existing
programs with `ontojev program-activate`; the scheduler refuses ambiguous active-program state.

Use `ontojev literature-import` for operator-adopted contextual documents. Use `gap-propose`,
`engineering-verify`, and `engineering-activate` for the isolated engineering record flow.
Verification receipts must bind the exact package digest and successful command. Activation records
review eligibility only; it never imports or executes package code inside scientific runtime.

## OntoCodex

`--director codex` is opt-in. It requires upstream Codex CLI and `OPENROUTER_API_KEY`; the key is
read from the process environment and is never persisted. Defaults are provider `openrouter`,
model `deepseek/deepseek-v4.1-flash`, and a 120-second invocation timeout. Override the executable,
model, or timeout with `ONTOCODEX_EXECUTABLE`, `ONTOCODEX_MODEL`, and
`ONTOCODEX_TIMEOUT_SECONDS`.

Each invocation uses a fresh `CODEX_HOME` and empty temporary working directory. Its config pins
read-only sandboxing, no approvals, disabled web search, the Responses wire API, and the provider
environment-key name. Durable records retain CLI/director versions, provider, model, safe config
hash, bounded projection hash, output hash, and decision kind. Provider secrets and raw prompts
are not retained. Failures occur before ResearchRun creation; malformed or stale decisions never
reach execution.

## Jev

`--jev typesafe` is opt-in and requires `TYPESAFE_API_KEY`. The default model is `jev-latest` and
the default endpoint is `https://api.typesafe.ai/v1/systemone`; override these with
`TYPESAFE_MODEL`, `TYPESAFE_ENDPOINT`, and `TYPESAFE_TIMEOUT_SECONDS`. Credentials are sent only in
the authorization header and are never persisted. Offline CI always uses deterministic evaluators.

