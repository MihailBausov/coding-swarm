#!/usr/bin/env bash
set -euo pipefail

echo "🧹 Linting..."
ruff check .
echo "✨ Linting passed!"
