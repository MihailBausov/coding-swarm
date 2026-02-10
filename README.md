# 🐝 Coding Swarm

**A general-purpose framework for running parallel AI agents against any codebase.**

Inspired by [Anthropic's approach to building a C compiler with agent teams](https://www.anthropic.com/engineering/building-c-compiler), Coding Swarm lets you spin up N isolated AI agents that work on your project simultaneously — each in its own Docker container, coordinating through git.

---

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                     Your Machine                        │
│                                                         │
│  swarm CLI ──────► Bare Git Repo (.swarm/upstream.git)  │
│                          ▲    ▲    ▲                    │
│                          │    │    │                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐          │
│  │ Container │  │ Container │  │ Container │  ...      │
│  │ Agent 1   │  │ Agent 2   │  │ Agent 3   │          │
│  │ Generalist│  │ Reviewer  │  │ Tester    │          │
│  └───────────┘  └───────────┘  └───────────┘          │
└─────────────────────────────────────────────────────────┘
```

1. **Each agent runs in a Docker container** with its own workspace.
2. **All agents share a bare git repo** — they clone, work, and push back.
3. **Task locks** prevent agents from duplicating work (`current_tasks/*.lock`).
4. **Specialized roles** (generalist, reviewer, optimizer, tester) keep agents focused.
5. **An infinite harness loop** keeps each agent working autonomously.

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Initialize

```bash
cd your-project
swarm init
# Edit swarm.yaml to configure your agents
```

### 3. Set your API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Build the agent container

```bash
docker build -t coding-swarm:latest .
```

### 5. Launch the swarm

```bash
swarm launch
```

### 6. Monitor

```bash
swarm status        # Snapshot of agent activity
swarm dashboard     # Live-refreshing dashboard
swarm logs agent-0  # View a specific agent's logs
```

### 7. Stop

```bash
swarm stop
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `swarm init` | Create a starter `swarm.yaml` config |
| `swarm launch` | Start all agent containers |
| `swarm launch --dry-run` | Preview what would be launched |
| `swarm status` | Show current agent activity + task locks |
| `swarm dashboard` | Live-refreshing terminal dashboard |
| `swarm logs [agent-id]` | View agent logs |
| `swarm stop` | Stop all containers |

## Configuration

Edit `swarm.yaml` to define your swarm:

```yaml
project:
  name: my-project
  repo_path: "."
  test_command: "npm test"

agents:
  - role: generalist
    prompt: agents/prompts/GENERALIST.md
    model: claude-opus-4-20250514
    count: 3
  - role: code-reviewer
    prompt: agents/prompts/CODE-REVIEWER.md
    count: 1
  - role: test-writer
    prompt: agents/prompts/TEST-WRITER.md
    count: 1

docker:
  image: coding-swarm:latest
  api_key_env: ANTHROPIC_API_KEY
```

## Agent Roles

| Role | Prompt | Purpose |
|------|--------|---------|
| **Generalist** | `GENERALIST.md` | Picks and implements the next most impactful task |
| **Code Reviewer** | `CODE-REVIEWER.md` | Reviews quality, deduplicates, refactors |
| **Optimizer** | `OPTIMIZER.md` | Profiles and improves performance |
| **Test Writer** | `TEST-WRITER.md` | Writes tests, catches regressions, maintains CI |

You can create custom roles by adding new prompt files in `agents/prompts/`.

## Project Structure

```
coding-swarm/
├── coding_swarm/          # Python package
│   ├── __init__.py
│   ├── cli.py             # CLI entry point (swarm command)
│   ├── config.py          # YAML config loader
│   ├── core.py            # Docker orchestrator
│   ├── monitor.py         # Activity dashboard
│   └── sync.py            # Git sync + task locking
├── scripts/
│   ├── harness.sh         # Agent loop (runs inside container)
│   ├── entrypoint.sh      # Docker entrypoint
│   └── setup-project.sh   # Host-side project setup
├── agents/
│   └── prompts/           # Agent role prompt templates
├── docs/                  # Architecture documentation
├── Dockerfile             # Agent container image
├── swarm.example.yaml     # Example configuration
├── pyproject.toml         # Python package config
└── requirements.txt       # Dependencies
```

## Key Concepts (from Anthropic's Blog Post)

- **Harness Loop**: Each agent runs Claude Code CLI in an infinite bash loop. When one session ends, the next begins automatically.
- **Git as Coordination**: A bare git repo is the single source of truth. Agents clone, work, push. Git's merge mechanics prevent conflicts.
- **Task Locking**: Agents create `.lock` files in `current_tasks/` before working on something. If two agents try the same task, one will fail to push and must pick another.
- **Context-Friendly Output**: Tests and tools print minimal output to avoid polluting the AI's context window. Details go to log files.
- **Specialization**: Different agent prompts focus on different concerns — building features, reviewing code, writing tests, optimizing performance.

## License

MIT