# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of the **coding-swarm** framework
- Core Python package (`coding_swarm`) with orchestrator, config loader, and CLI
- Shell harness scripts (`harness.sh`, `entrypoint.sh`) for autonomous agent loops
- Dockerfile for agent containers (Ubuntu 24.04 + git + Claude Code CLI)
- 4 built-in agent roles: Generalist, Code Reviewer, Optimizer, Test Writer
- Git synchronization module with task locking via `current_tasks/*.lock`
- Monitoring dashboard for live agent activity
- CLI commands: `init`, `launch`, `status`, `logs`, `stop`, `dashboard`
