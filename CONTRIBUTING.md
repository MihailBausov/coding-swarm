# Contributing

## Getting Started

1. Clone the repo and install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

2. Run the tests:
   ```bash
   pytest
   ```

3. Check code style:
   ```bash
   ruff check coding_swarm/
   ```

## Project Structure

- `coding_swarm/` — Python package (CLI, orchestrator, config, sync, monitor)
- `scripts/` — Shell scripts that run inside Docker containers
- `agents/prompts/` — Markdown prompt templates for each agent role
- `docs/` — Architecture and usage documentation
- `tests/` — Unit and integration tests

## Adding a New Agent Role

1. Create `agents/prompts/YOUR-ROLE.md` following the existing prompt patterns
2. Add an entry in `swarm.example.yaml` as a reference
3. Document the role in `docs/AGENT-ARCHITECTURE.md`

## Code Style

- Python: Follow PEP 8, checked with `ruff`
- Shell: Use `set -euo pipefail`, quote variables, use functions
- Markdown: Keep prompts clear and actionable

## Pull Requests

- One feature or fix per PR
- Include tests for new functionality
- Update documentation for user-facing changes
