# Performance Benchmarks

## Metrics to Track

When running a coding swarm, track these metrics to evaluate effectiveness:

### Agent Productivity
- **Commits per agent per hour** — how active is each agent?
- **Tests fixed per session** — are agents making real progress?
- **Lines of code per session** — volume (not necessarily quality)
- **Task completion rate** — what % of locked tasks get completed?

### Coordination Overhead
- **Merge conflict frequency** — how often do agents collide?
- **Lock contention rate** — how often does a lock push fail?
- **Wasted sessions** — sessions where an agent made no meaningful progress

### Quality
- **Test pass rate over time** — should be monotonically increasing
- **Regression rate** — how often do new changes break existing tests?
- **Code duplication trend** — does the reviewer agent keep it in check?

## Measuring

```bash
# Commits per agent
git shortlog -s --after="1 hour ago"

# Test pass rate history
grep "tests passing" agent_logs/*.log | tail -20

# Active sessions
docker ps --filter "name=swarm-" --format "{{.Names}} {{.Status}}"
```

## Tuning

- **Too many generalists?** → Agents step on each other's toes. Reduce count or increase specialization.
- **High merge conflict rate?** → Agents are working on overlapping files. Improve task granularity.
- **Stalled progress?** → Check if tests are too strict or prompts are too vague.
- **Low quality output?** → Add more code-reviewer agents, improve test coverage.
