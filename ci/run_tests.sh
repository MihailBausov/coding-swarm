#!/usr/bin/env bash
set -euo pipefail

echo "🧪 Running tests..."
pytest --cov=coding_swarm tests/ -v
