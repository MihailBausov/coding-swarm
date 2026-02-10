# Overview

## What Anthropic Did

In February 2026, Anthropic published [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler). The key insight: instead of one AI agent working sequentially, they ran **16 parallel Claude instances** in Docker containers against a shared git repository.

The result: a 100,000-line Rust-based C compiler capable of compiling the Linux kernel — produced autonomously over ~2,000 sessions.

### Core Architecture

1. **Infinite harness loop** — A bash script runs `claude --dangerously-skip-permissions -p "$(cat AGENT_PROMPT.md)"` in a `while true` loop inside each container.
2. **Bare git repo** — A shared bare repo at `/upstream` serves as the coordination hub. Each container clones it, works locally, then pushes.
3. **Task locking** — Files in `current_tasks/` act as distributed locks. An agent creates `current_tasks/my_task.lock` before starting. If two agents collide, the second one's push fails → it picks a different task.
4. **No orchestrator** — There is no central coordinator. Each agent independently reads the repo state (progress files, task locks, git log) and decides what to work on next.
5. **Specialized roles** — Different agents had different prompts: feature builders, code reviewers, optimizers, documentation writers.

### Key Lessons

- **Tests are the product** — The test suite is the primary mechanism for keeping agents on track. Tests must be high-quality and comprehensive.
- **Context window management** — Output must be minimal. Log to files, pre-compute summaries, avoid printing thousands of lines.
- **Time blindness** — Agents can't tell time. Include `--fast` test modes that run 10% samples.
- **Merge conflicts are fine** — Claude is smart enough to resolve them.

## What Coding Swarm Does

This framework generalises Anthropic's approach so you can apply it to **any project**:

| Anthropic's Approach | Coding Swarm |
|---------------------|--------------|
| Hardcoded for C compiler | Config-driven via `swarm.yaml` |
| Manual Docker setup | Automated with `swarm launch` |
| No monitoring | Built-in dashboard and log viewer |
| Custom bash scripts | Reusable harness + entrypoint |
| One set of prompts | Pluggable prompt templates per role |
| Single AI provider (Claude) | Multi-provider: Anthropic, Gemini, OpenAI |

## When to Use This

- **Large codebases** that benefit from parallel work streams
- **Greenfield projects** where multiple features can advance simultaneously
- **Test-driven refactors** where agents can each fix different tests
- **Code quality sweeps** where reviewers, testers, and optimizers run in parallel
- **Any task** where you'd otherwise supervise a single AI agent for hours
