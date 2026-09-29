# OntoJev

OntoJev is a persistent, cancer-general autonomous computational research laboratory. Lung
cancer is the first future validation program, not an architectural boundary. This bootstrap
proves the complete research-state lifecycle with deterministic synthetic capabilities; it
performs no real cancer analysis and makes no therapeutic claims.

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

The default director remains deterministic so offline development and CI never incur provider
calls. To exercise the M1 scientific-director boundary, configure `OPENROUTER_API_KEY` outside
the repository and run:

```bash
uv run ontojev run --root .ontojev --max-runs 1 --director codex
```

This invokes upstream Codex CLI in an isolated temporary directory using the configured
OpenRouter model. Python still validates the typed decision before any ResearchRun begins.

