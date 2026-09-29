# Operations

OntoJev stores state under `ONTOJEV_DATA_ROOT` (default `.ontojev`). SQLite is the lifecycle
index; immutable JSON and Markdown artifacts are content-addressed by SHA-256. Publication uses
a temporary file, verified digest, atomic rename, then database registration.

A ResearchRun defaults to a 600-second hard limit with a 30-second finalization reserve.
Capability work receives the remaining budget. Timed-out work receives a durable terminal
outcome. At startup, abandoned `RUNNING` records become `INTERRUPTED`; the scheduler derives
fresh offers from durable state rather than trusting stale decisions.

Corrupt or missing referenced artifacts stop progression. Unregistered files are ignored.
Live model, Jev, provider, network, and paid-service calls are absent from the bootstrap.

