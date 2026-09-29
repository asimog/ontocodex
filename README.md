# OntoJev

OntoJev is a persistent, cancer-general autonomous computational research laboratory. It supports
the deterministic synthetic bootstrap and operator-adopted observational programs. Lung cancer is
the first program template, not an architectural boundary. Results are descriptive computational
evidence and never therapeutic claims.

## Authority

- Humans bound programs, permitted sources, budgets, credentials, and deployment.
- OntoCodex directs scientific questions and chooses among validated offers.
- Python measures, validates, persists, and executes.
- Wide and Deep Jev provide bounded typed judgments, never measurements.

## Development

Python 3.12 and `uv` are required.

```bash
uv sync --locked --extra dev
uv run ruff format --check .
uv run ruff check .
uv run mypy ontojev tests
uv run pytest
```

Run bounded synthetic research and inspect durable state:

```bash
uv run ontojev run --root .ontojev --max-runs 1
uv run ontojev status --root .ontojev
```

Initialize an observational program, adopt one primary and one replication CSV, then advance the
same scheduler:

```bash
uv run ontojev init --root .ontojev --cancer-scope "lung cancer"
uv run ontojev source-import --root .ontojev --manifest primary.json --data primary.csv
uv run ontojev source-import --root .ontojev --manifest replication.json --data replication.csv
uv run ontojev run --root .ontojev --max-runs 11
uv run ontojev observe --root .ontojev
```

Additional programs may be initialized without activation. Select one explicitly with
`ontojev program-activate --root .ontojev --program-id <uuid>`; exactly one program owns scheduler
attention at a time.

Source manifests pin citation, license, release, scope, cohort role, required columns, and SHA-256.
Input CSVs use `sample_id,feature,status`; accepted status values are explicit positive, negative,
or missing values. Literature is imported separately with `literature-import` and cannot become
measurement evidence.

The default director remains deterministic so offline development and CI never incur provider
calls. To exercise the M1 scientific-director boundary, configure `OPENROUTER_API_KEY` outside
the repository and run:

```bash
uv run ontojev run --root .ontojev --max-runs 1 --director codex
```

This invokes upstream Codex CLI in an isolated temporary directory using the configured
OpenRouter model. Python still validates the typed decision before any ResearchRun begins.

Wide and Deep use deterministic adapters by default. A credentialed TypeSafe Jev call is opt-in:

```bash
uv run ontojev run --root .ontojev --max-runs 1 --jev typesafe
```

Set `TYPESAFE_API_KEY` outside the repository. Jev receives bounded state summaries without raw
result payloads; Python still owns Candidate admission, capability execution, and Stage 8.

