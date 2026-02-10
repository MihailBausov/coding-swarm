#!/usr/bin/env bash
# =============================================================================
# setup-project.sh — Initialize a project for swarm usage (runs on HOST)
#
# Creates the bare upstream repo, seeds project files, and prepares the
# directory structure that agents expect.
#
# Usage:
#   ./scripts/setup-project.sh [project-dir] [upstream-dir]
# =============================================================================

set -euo pipefail

PROJECT_DIR="${1:-.}"
UPSTREAM_DIR="${2:-.swarm/upstream.git}"
BRANCH="${BRANCH:-main}"

echo "📂 Setting up swarm project ..."
echo "   Project:  ${PROJECT_DIR}"
echo "   Upstream: ${UPSTREAM_DIR}"
echo "   Branch:   ${BRANCH}"
echo

# ---------------------------------------------------------------------------
# 1. Create the bare upstream repo
# ---------------------------------------------------------------------------

if [ -d "${UPSTREAM_DIR}/HEAD" ] || [ -f "${UPSTREAM_DIR}/HEAD" ]; then
    echo "✅ Upstream repo already exists."
else
    echo "Creating bare upstream repo ..."
    mkdir -p "${UPSTREAM_DIR}"
    git init --bare --initial-branch "${BRANCH}" "${UPSTREAM_DIR}"

    # Create an initial commit via a temp clone
    TMPDIR=$(mktemp -d)
    git clone "${UPSTREAM_DIR}" "${TMPDIR}/init"
    cd "${TMPDIR}/init"
    git checkout -b "${BRANCH}" 2>/dev/null || true

    # Seed the directories that agents expect
    mkdir -p current_tasks agent_logs

    cat > PROGRESS.md << 'EOF'
# Progress

This file is maintained by the swarm agents.
Each agent should update it with their status, completed tasks, and next steps.

## Status
- [ ] Project initialized
- [ ] Awaiting first agent iteration

## Completed Tasks
(none yet)

## Next Steps
- Review the codebase
- Identify and prioritize tasks
- Begin implementation
EOF

    cat > current_tasks/.gitkeep << 'EOF'
EOF
    cat > agent_logs/.gitkeep << 'EOF'
EOF

    git add .
    git commit -m "Initial swarm scaffold"
    git push origin "${BRANCH}"

    # Clean up
    rm -rf "${TMPDIR}"
    cd - > /dev/null

    echo "✅ Upstream repo created."
fi

# ---------------------------------------------------------------------------
# 2. Seed project files into upstream
# ---------------------------------------------------------------------------

PROJECT_DIR_ABS=$(cd "${PROJECT_DIR}" && pwd)

if [ "${PROJECT_DIR_ABS}" != "$(pwd)" ]; then
    echo "Seeding project files from ${PROJECT_DIR_ABS} ..."
    TMPDIR=$(mktemp -d)
    git clone "${UPSTREAM_DIR}" "${TMPDIR}/seed"
    cd "${TMPDIR}/seed"
    git checkout "${BRANCH}" 2>/dev/null || true

    # Copy project files (skip .git and .swarm)
    rsync -a --exclude='.git' --exclude='.swarm' "${PROJECT_DIR_ABS}/" ./ 2>/dev/null || {
        # Fallback without rsync
        find "${PROJECT_DIR_ABS}" -maxdepth 1 -not -name '.git' -not -name '.swarm' -not -name '.' | while read item; do
            cp -r "$item" ./ 2>/dev/null || true
        done
    }

    git add .
    if ! git diff --cached --quiet; then
        git commit -m "Seed project files"
        git push origin "${BRANCH}"
        echo "✅ Project files seeded."
    else
        echo "✅ No new files to seed."
    fi

    rm -rf "${TMPDIR}"
    cd - > /dev/null
fi

# ---------------------------------------------------------------------------
# 3. Create local directories
# ---------------------------------------------------------------------------

mkdir -p .swarm/logs

echo
echo "🎉 Setup complete!"
echo
echo "Next steps:"
echo "  1. Edit swarm.yaml (run 'swarm init' if you don't have one)"
echo "  2. Set your API key: export ANTHROPIC_API_KEY=sk-..."
echo "  3. Build the Docker image: docker build -t coding-swarm:latest ."
echo "  4. Launch the swarm: swarm launch"
