# Agent Architecture

## System Architecture

```
Host Machine
├── swarm CLI (Python)
│   ├── Reads swarm.yaml
│   ├── Creates bare git repo (.swarm/upstream.git)
│   ├── Builds Docker image
│   └── Launches N containers
│
├── .swarm/upstream.git (bare repo)
│   ├── current_tasks/*.lock   ← distributed task locks
│   ├── agent_logs/            ← session logs
│   └── PROGRESS.md            ← shared status file
│
└── Docker Containers
    ├── swarm-generalist-0
    │   ├── /upstream (mounted bare repo)
    │   ├── /workspace (cloned working copy)
    │   ├── /scripts/harness.sh (infinite loop)
    │   └── /prompts/GENERALIST.md
    ├── swarm-generalist-1
    ├── swarm-code-reviewer-0
    ├── swarm-test-writer-0
    └── ...
```

## The Harness Loop

Each container runs `scripts/harness.sh` in an infinite loop:

```
┌─────────────────────────────────────┐
│           Agent Container            │
│                                     │
│  ┌───────────────────────────────┐  │
│  │      harness.sh (loop)        │  │
│  │                               │  │
│  │  1. git pull from /upstream   │  │
│  │  2. Build context-rich prompt │  │
│  │     - Read PROGRESS.md       │  │
│  │     - List current_tasks/    │  │
│  │     - Recent git log         │  │
│  │  3. Dispatch to AI provider  │  │
│  │     → claude (anthropic)     │  │
│  │     → gemini (gemini)        │  │
│  │     → codex  (openai)        │  │
│  │  4. git add + commit         │  │
│  │  5. git push to /upstream    │  │
│  │  6. Sleep 5s                 │  │
│  │  7. → back to step 1        │  │
│  └───────────────────────────────┘  │
│                                     │
└─────────────────────────────────────┘
```

## Task Locking Protocol

The task-locking mechanism prevents multiple agents from duplicating work:

1. **Agent reads** `current_tasks/` to see what's already locked
2. **Agent creates** `current_tasks/my_task.lock` with its ID
3. **Agent commits and pushes** the lock file
4. If push **succeeds** → agent owns the task
5. If push **fails** (conflict) → another agent got there first → pick a different task
6. When done, **agent removes** the lock file and pushes

This is a lightweight form of distributed consensus using git as the coordination layer.

## Git Synchronization

Agents use a pull-rebase-push cycle:

```
Agent workspace                  Bare upstream repo
     │                                  │
     │──── git pull --rebase ──────────►│
     │                                  │
     │    (agent works on code)         │
     │                                  │
     │──── git add + commit            │
     │──── git push ──────────────────►│
     │                                  │
     │  If push fails (conflict):       │
     │    git pull --rebase             │
     │    resolve conflicts             │
     │    git push (retry)              │
```

## Agent Roles

Each role has a dedicated prompt that shapes the agent's behavior:

| Role | Focus | Prompt |
|------|-------|--------|
| Generalist | Feature implementation, bug fixes | `GENERALIST.md` |
| Code Reviewer | Quality, deduplication, refactoring | `CODE-REVIEWER.md` |
| Test Writer | Test coverage, regression prevention | `TEST-WRITER.md` |
| Optimizer | Performance profiling and improvement | `OPTIMIZER.md` |

### Creating Custom Roles

1. Create a new prompt file: `agents/prompts/MY-ROLE.md`
2. Add it to `swarm.yaml`:
   ```yaml
   agents:
     - role: my-role
       prompt: agents/prompts/MY-ROLE.md
       count: 1
   ```

## Docker Isolation

Each agent runs in its own Docker container for safety:

- **No host access** — agents only see `/workspace`, `/upstream`, and `/logs`
- **No network by default** — unless you configure `docker.network`
- **Non-persistent** — containers can be killed and restarted without data loss (all work is in git)
- **`--dangerously-skip-permissions`** — gives the AI full shell access *inside* the container only
