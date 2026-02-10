# Tests and CI for Autonomous Agents

Lessons from Anthropic's experience running 16 parallel Claudes.

## Why Tests Matter More Than Ever

When humans write code, tests catch bugs. When AI agents write code autonomously, **tests are the only thing keeping them on track**. The test suite *is* the product specification.

> "Claude will work autonomously to solve whatever problem I give it. So it's important that the task verifier is nearly perfect, otherwise Claude will solve the wrong problem."
>
> — Nicholas Carlini, Anthropic

## Designing Tests for AI Agents

### 1. Make Output Context-Friendly

AI agents have limited context windows. Don't pollute them with test output.

**Do:**
- Print a one-line summary: `47/50 tests passing (3 failures in module X)`
- Log details to files: `test_results/test_123.log`
- Use `ERROR:` prefix on error lines so agents can grep for them
- Pre-compute aggregate statistics

**Don't:**
- Print the full output of every test
- Dump stack traces to stdout
- Print thousands of lines of diff output

### 2. Include a `--fast` Mode

Agents will happily spend hours running the full test suite instead of making progress.

```bash
# Full suite (CI only)
./run_tests.sh

# 10% random sample (agent default)
./run_tests.sh --fast

# Deterministic per-agent, random across VMs
./run_tests.sh --fast --seed $AGENT_ID
```

### 3. Tests Must Actually Verify Correctness

AI agents will find the path of least resistance. Tests that are easy to game will be gamed.

**Bad test**: `assert len(output) > 0` — agent can return garbage.
**Good test**: `assert parse(output) == expected_ast` — agent must produce correct output.

### 4. Regression Tests Are Critical

Every bug fix should add a test that would have caught the bug:

```
tests/
  regression/
    issue_42_null_pointer.py
    issue_57_off_by_one.py
```

### 5. Build a CI Pipeline

Even without traditional CI, you can enforce quality:

```bash
#!/bin/bash
# pre-push hook or harness check

# Run fast tests
./run_tests.sh --fast
if [ $? -ne 0 ]; then
    echo "ERROR: Tests failing. Fix before pushing."
    exit 1
fi
```

## Monitoring Agent Progress

### PROGRESS.md

Agents maintain a shared `PROGRESS.md` file with:
- Current test pass rates
- List of completed tasks
- Known bugs and blockers
- Next priorities

### Git Log Analysis

```bash
# See what agents have been doing
git log --oneline --author="swarm-" -20

# See which agents are most active
git shortlog -s --author="swarm-"

# See files most frequently modified
git log --name-only --format="" | sort | uniq -c | sort -rn | head -20
```

### Task Lock Monitoring

```bash
# Currently locked tasks
ls current_tasks/*.lock

# Who's working on what
for f in current_tasks/*.lock; do
    echo "$(basename $f .lock): $(head -1 $f)"
done
```
