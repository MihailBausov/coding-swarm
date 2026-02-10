"""Configuration loader for coding_swarm.

Reads a swarm.yaml config file and provides typed configuration
for the orchestrator, agents, and Docker settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ProjectConfig:
    """Settings for the target project the swarm will work on."""

    name: str
    repo_url: str = ""
    repo_path: str = ""
    branch: str = "main"
    test_command: str = ""
    description: str = ""


@dataclass
class AgentConfig:
    """Definition of a single agent role."""

    role: str
    prompt: str  # path to the prompt markdown file
    model: str = "claude-opus-4-20250514"
    count: int = 1
    extra_args: str = ""


@dataclass
class DockerConfig:
    """Docker-related settings."""

    image: str = "coding-swarm:latest"
    api_key_env: str = "ANTHROPIC_API_KEY"
    extra_env: dict[str, str] = field(default_factory=dict)
    volumes: dict[str, str] = field(default_factory=dict)
    network: str = ""
    build_context: str = "."


@dataclass
class SwarmConfig:
    """Top-level configuration for the entire swarm."""

    project: ProjectConfig
    agents: list[AgentConfig]
    docker: DockerConfig = field(default_factory=DockerConfig)
    upstream_dir: str = ".swarm/upstream.git"
    logs_dir: str = ".swarm/logs"
    tasks_dir: str = "current_tasks"
    progress_file: str = "PROGRESS.md"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _parse_project(raw: dict) -> ProjectConfig:
    return ProjectConfig(
        name=raw.get("name", "my-project"),
        repo_url=raw.get("repo_url", ""),
        repo_path=raw.get("repo_path", ""),
        branch=raw.get("branch", "main"),
        test_command=raw.get("test_command", ""),
        description=raw.get("description", ""),
    )


def _parse_agents(raw: list[dict]) -> list[AgentConfig]:
    agents: list[AgentConfig] = []
    for entry in raw:
        agents.append(
            AgentConfig(
                role=entry["role"],
                prompt=entry.get(
                    "prompt", f"agents/prompts/{entry['role'].upper()}.md"
                ),
                model=entry.get("model", "claude-opus-4-20250514"),
                count=entry.get("count", 1),
                extra_args=entry.get("extra_args", ""),
            )
        )
    return agents


def _parse_docker(raw: dict) -> DockerConfig:
    return DockerConfig(
        image=raw.get("image", "coding-swarm:latest"),
        api_key_env=raw.get("api_key_env", "ANTHROPIC_API_KEY"),
        extra_env=raw.get("extra_env", {}),
        volumes=raw.get("volumes", {}),
        network=raw.get("network", ""),
        build_context=raw.get("build_context", "."),
    )


def load_config(path: str | Path = "swarm.yaml") -> SwarmConfig:
    """Load and validate a swarm configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        A fully populated SwarmConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required fields are missing.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError("Empty configuration file")

    if "project" not in raw:
        raise ValueError("'project' section is required in swarm.yaml")
    if "agents" not in raw or not raw["agents"]:
        raise ValueError("At least one agent must be defined in 'agents'")

    project = _parse_project(raw["project"])
    agents = _parse_agents(raw["agents"])
    docker = _parse_docker(raw.get("docker", {}))

    return SwarmConfig(
        project=project,
        agents=agents,
        docker=docker,
        upstream_dir=raw.get("upstream_dir", ".swarm/upstream.git"),
        logs_dir=raw.get("logs_dir", ".swarm/logs"),
        tasks_dir=raw.get("tasks_dir", "current_tasks"),
        progress_file=raw.get("progress_file", "PROGRESS.md"),
    )


# ---------------------------------------------------------------------------
# Template generator
# ---------------------------------------------------------------------------

DEFAULT_TEMPLATE = """\
# Coding Swarm Configuration
# See docs/OVERVIEW.md for details.

project:
  name: my-project
  # Either a remote URL to clone, or a local path to an existing repo:
  repo_url: ""
  repo_path: "."
  branch: main
  # Command the agents run to verify their changes:
  test_command: "make test"
  description: "Describe your project goals here"

agents:
  - role: generalist
    prompt: agents/prompts/GENERALIST.md
    model: claude-opus-4-20250514
    count: 3

  - role: code-reviewer
    prompt: agents/prompts/CODE-REVIEWER.md
    model: claude-opus-4-20250514
    count: 1

  - role: test-writer
    prompt: agents/prompts/TEST-WRITER.md
    model: claude-opus-4-20250514
    count: 1

  - role: optimizer
    prompt: agents/prompts/OPTIMIZER.md
    model: claude-opus-4-20250514
    count: 1

docker:
  image: coding-swarm:latest
  api_key_env: ANTHROPIC_API_KEY
  # Extra environment variables passed to every container:
  extra_env: {}
  # Host paths to mount into containers (host_path: container_path):
  volumes: {}
"""


def generate_template(dest: str | Path = "swarm.yaml") -> Path:
    """Write a starter swarm.yaml template to *dest*.

    Returns:
        The Path to the created file.
    """
    dest_path = Path(dest)
    if dest_path.exists():
        raise FileExistsError(f"{dest_path} already exists")
    dest_path.write_text(DEFAULT_TEMPLATE)
    return dest_path
