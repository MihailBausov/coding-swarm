#!/usr/bin/env bash
# =============================================================================
# harness.sh — The core agent loop (runs INSIDE a Docker container)
#
# This is the beating heart of the swarm. It runs the AI CLI in an infinite
# loop: each iteration pulls the latest code, lets the agent work, then
# pushes changes back to the shared upstream repo.
#
# Environment variables (set by the orchestrator):
#   AGENT_ID          — unique identifier for this agent instance
#   AGENT_MODEL       — model to use (e.g. claude-opus-4-20250514)
#   AGENT_PROMPT_FILE — path to the agent's prompt markdown file
#   AGENT_ROLE        — role name (generalist, code-reviewer, etc.)
#   BRANCH            — git branch to work on (default: main)
#   TEST_COMMAND      — command to run for verification
#   ANTHROPIC_API_KEY — API key for the AI backend
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UPSTREAM="/upstream"
WORKSPACE="/workspace"
BRANCH="${BRANCH:-main}"
AGENT_ID="${AGENT_ID:-agent-0}"
AGENT_MODEL="${AGENT_MODEL:-claude-opus-4-20250514}"
AGENT_PROMPT_FILE="${AGENT_PROMPT_FILE:-/prompts/GENERALIST.md}"
LOG_DIR="/logs"
MAX_RETRIES=3

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [${AGENT_ID}] $*"
}

log_to_file() {
    local logfile="${LOG_DIR}/${AGENT_ID}_$(date -u '+%Y%m%d_%H%M%S').log"
    tee -a "$logfile"
}

# ---------------------------------------------------------------------------
# Setup workspace
# ---------------------------------------------------------------------------

setup_workspace() {
    log "Setting up workspace ..."

    if [ -d "${WORKSPACE}/.git" ]; then
        log "Workspace exists, pulling latest ..."
        cd "$WORKSPACE"
        git fetch origin
        git reset --hard "origin/${BRANCH}" 2>/dev/null || true
    else
        log "Cloning from upstream ..."
        git clone "$UPSTREAM" "$WORKSPACE"
        cd "$WORKSPACE"
        git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"
    fi

    # Configure git for this agent
    git config user.name "swarm-${AGENT_ID}"
    git config user.email "${AGENT_ID}@coding-swarm.local"
}

# ---------------------------------------------------------------------------
# Sync changes back to upstream
# ---------------------------------------------------------------------------

sync_to_upstream() {
    cd "$WORKSPACE"

    git add -A

    # Check if there are changes to commit
    if git diff --cached --quiet 2>/dev/null; then
        log "No changes to push."
        return 0
    fi

    local COMMIT_HASH
    COMMIT_HASH=$(git rev-parse --short=6 HEAD)
    git commit -m "[${AGENT_ID}] Update at ${COMMIT_HASH}" 2>/dev/null || true

    # Pull with rebase first
    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        if git pull --rebase origin "$BRANCH" 2>/dev/null; then
            break
        fi
        log "Rebase failed, attempting merge ..."
        git rebase --abort 2>/dev/null || true
        if git pull --no-rebase origin "$BRANCH" 2>/dev/null; then
            break
        fi
        # Auto-resolve conflicts by accepting ours
        git checkout --ours . 2>/dev/null || true
        git add . 2>/dev/null || true
        git commit -m "[${AGENT_ID}] Auto-merge resolution" 2>/dev/null || true
        retries=$((retries + 1))
    done

    # Push
    if git push origin "$BRANCH" 2>/dev/null; then
        log "✅ Pushed changes to upstream."
    else
        log "⚠️  Push failed — will retry next iteration."
    fi
}

# ---------------------------------------------------------------------------
# Build the agent prompt
# ---------------------------------------------------------------------------

build_prompt() {
    local prompt=""

    # Read the base prompt file
    if [ -f "$AGENT_PROMPT_FILE" ]; then
        prompt=$(cat "$AGENT_PROMPT_FILE")
    else
        prompt="You are a coding agent. Look at the codebase, find issues or improvements, fix them, and commit your changes."
    fi

    # Inject the current state context
    prompt="${prompt}

---
## Current State

**Agent ID:** ${AGENT_ID}
**Role:** ${AGENT_ROLE:-generalist}
**Branch:** ${BRANCH}
**Test Command:** ${TEST_COMMAND:-none}

### Active Tasks (currently locked by other agents):
$(ls -1 ${WORKSPACE}/current_tasks/*.lock 2>/dev/null | while read f; do echo "- $(basename "$f" .lock): $(head -1 "$f")"; done || echo "- (none)")

### Recent Git Log:
$(cd ${WORKSPACE} && git log --oneline -5 2>/dev/null || echo "(no commits yet)")

### Instructions:
1. Read PROGRESS.md for project status and remaining work.
2. Pick a task that is NOT listed in current_tasks/ (those are locked by others).
3. Create a lock file: \`echo 'agent: ${AGENT_ID}' > current_tasks/YOUR_TASK_NAME.lock\`
4. Work on the task. Run the test command if available: \`${TEST_COMMAND:-echo 'no tests configured'}\`
5. Update PROGRESS.md with what you accomplished.
6. Remove your lock file when done.
7. Commit and push your changes (the harness handles the push).
"

    echo "$prompt"
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

main() {
    log "============================================"
    log "  🐝 Coding Swarm Agent — ${AGENT_ID}"
    log "     Role:  ${AGENT_ROLE:-generalist}"
    log "     Model: ${AGENT_MODEL}"
    log "============================================"

    mkdir -p "$LOG_DIR"
    setup_workspace

    local iteration=0

    while true; do
        iteration=$((iteration + 1))
        log "--- Iteration ${iteration} ---"

        # Pull latest changes from other agents
        cd "$WORKSPACE"
        git pull --rebase origin "$BRANCH" 2>/dev/null || {
            git rebase --abort 2>/dev/null || true
            git pull --no-rebase origin "$BRANCH" 2>/dev/null || true
        }

        # Build the prompt with current context
        local PROMPT
        PROMPT=$(build_prompt)

        local COMMIT_HASH
        COMMIT_HASH=$(git rev-parse --short=6 HEAD)
        local LOGFILE="${LOG_DIR}/${AGENT_ID}_${COMMIT_HASH}_$(date -u '+%H%M%S').log"

        log "Starting Claude session (commit: ${COMMIT_HASH}) ..."

        # Run the AI agent
        # claude CLI with --dangerously-skip-permissions for autonomous mode
        claude --dangerously-skip-permissions \
            -p "$PROMPT" \
            --model "$AGENT_MODEL" \
            2>&1 | tee "$LOGFILE" || {
                log "⚠️  Claude session ended with error. Continuing ..."
            }

        log "Session complete. Syncing changes ..."

        # Push changes back to upstream
        sync_to_upstream

        log "Sleeping 5s before next iteration ..."
        sleep 5
    done
}

main "$@"