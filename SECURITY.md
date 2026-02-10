# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

Please report security vulnerabilities by emailing security@coding-swarm.local (replace with actual email) or by opening a GitHub advisory if hosted on GitHub.

### Autonomous Agent Risks

Running autonomous AI agents with `--dangerously-skip-permissions` inside Docker containers carries inherent risks:

1. **Container Escape**: While we use standard Docker isolation, container escapes are theoretically possible. Do not run agents on sensitive production hosts without additional sandboxing (e.g., gVisor).
2. **Resource Exhaustion**: Agents run in infinite loops. Use Docker resource limits (`--cpus`, `--memory`) to prevent them from consuming all host resources.
3. **Network Access**: By default, agents may have network access. You can restrict this by passing `--network none` in `config.docker.extra_args`, but this will prevent `pip install` or other network-dependent tasks.

We recommend running the swarm in an ephemeral VM or a dedicated sandbox environment.
