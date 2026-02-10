# =============================================================================
# Dockerfile — Coding Swarm Agent Container
#
# Each agent runs in its own container with:
# - Git + common dev tools
# - Claude Code CLI (install your preferred AI CLI)
# - The harness scripts
# =============================================================================

FROM ubuntu:24.04

LABEL maintainer="coding-swarm"
LABEL description="Container for a parallel coding swarm agent"

# ---- System packages --------------------------------------------------------

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    ca-certificates \
    build-essential \
    jq \
    rsync \
    tree \
    python3 \
    python3-pip \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# ---- AI CLI tools ----------------------------------------------------------
# Install all three provider CLIs via npm.
# The harness dispatches to the correct one based on AGENT_PROVIDER.

RUN npm install -g @anthropic-ai/claude-code 2>/dev/null || \
    echo "⚠️  Claude Code CLI not available via npm."

RUN npm install -g @google/gemini-cli 2>/dev/null || \
    echo "⚠️  Gemini CLI not available via npm."

RUN npm install -g @openai/codex 2>/dev/null || \
    echo "⚠️  OpenAI Codex CLI not available via npm."

# ---- Working directories ----------------------------------------------------

RUN mkdir -p /workspace /upstream /logs /scripts /prompts

# ---- Copy scripts -----------------------------------------------------------

COPY scripts/harness.sh /scripts/harness.sh
COPY scripts/entrypoint.sh /scripts/entrypoint.sh
RUN chmod +x /scripts/*.sh

# ---- Copy agent prompts -----------------------------------------------------

COPY agents/prompts/ /prompts/

# ---- Environment defaults ---------------------------------------------------

ENV AGENT_ID="agent-0"
ENV AGENT_ROLE="generalist"
ENV AGENT_PROVIDER="anthropic"
ENV AGENT_MODEL="claude-opus-4-20250514"
ENV AGENT_PROMPT_FILE="/prompts/GENERALIST.md"
ENV BRANCH="main"
ENV TEST_COMMAND=""

WORKDIR /workspace

# ---- Entrypoint -------------------------------------------------------------

ENTRYPOINT ["/scripts/entrypoint.sh"]
