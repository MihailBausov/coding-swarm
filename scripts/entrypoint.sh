#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh — Docker container entrypoint
#
# Configures the environment, sets up git, and starts the harness loop.
# =============================================================================

set -euo pipefail

AGENT_ID="${AGENT_ID:-agent-0}"

echo "🐝 Swarm agent container starting ..."
echo "   Agent: ${AGENT_ID}"
echo "   Role:  ${AGENT_ROLE:-generalist}"
echo "   Model: ${AGENT_MODEL:-claude-opus-4-20250514}"

# ---------------------------------------------------------------------------
# Git config
# ---------------------------------------------------------------------------

git config --global user.name "swarm-${AGENT_ID}"
git config --global user.email "${AGENT_ID}@coding-swarm.local"
git config --global init.defaultBranch "${BRANCH:-main}"

# Avoid issues with dubious ownership inside containers
git config --global --add safe.directory /workspace
git config --global --add safe.directory /upstream

# ---------------------------------------------------------------------------
# Ensure log directory exists
# ---------------------------------------------------------------------------

mkdir -p /logs

# ---------------------------------------------------------------------------
# Start the harness loop
# ---------------------------------------------------------------------------

exec /scripts/harness.sh
