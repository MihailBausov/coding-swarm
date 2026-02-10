"""Configuration loader for coding_swarm.

Reads a swarm.yaml config file and provides typed configuration
for the orchestrator, agents, and Docker settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PROVIDERS = ("anthropic", "gemini", "openai")

DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-opus-4-20250514",
    "gemini": "gemini-2.5-pro",
    "openai": "o3",
}


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
    provider: str = "anthropic"  # anthropic | gemini | openai
    model: str = ""  # empty → resolved from DEFAULT_MODELS[provider]
    count: int = 1
    extra_args: str = ""


@dataclass
class DockerConfig:
    """Docker-related settings."""

    image: str = "coding-swarm:latest"
    api_keys: dict[str, str] = field(
        default_factory=lambda: {
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
    )
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
        provider = entry.get("provider", "anthropic")
        if provider not in VALID_PROVIDERS:
            raise ValueError(
                f"Invalid provider '{provider}' for agent '{entry['role']}'. "
                f"Valid providers: {', '.join(VALID_PROVIDERS)}"
            )
        model = entry.get("model", "") or DEFAULT_MODELS[provider]
        agents.append(
            AgentConfig(
                role=entry["role"],
                prompt=entry.get(
                    "prompt", f"agents/prompts/{entry['role'].upper()}.md"
                ),
                provider=provider,
                model=model,
                count=entry.get("count", 1),
                extra_args=entry.get("extra_args", ""),
            )
        )
    return agents


def _parse_docker(raw: dict) -> DockerConfig:
    default_keys = {
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    api_keys = raw.get("api_keys", default_keys)
    return DockerConfig(
        image=raw.get("image", "coding-swarm:latest"),
        api_keys=api_keys,
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
#
# Supported providers: anthropic, gemini, openai
# Each agent can specify its own provider and model.
# If model is omitted, a sensible default is used per provider.

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
    provider: anthropic          # anthropic | gemini | openai
    prompt: agents/prompts/GENERALIST.md
    # model: claude-opus-4-20250514  (default for anthropic)
    count: 3

  - role: code-reviewer
    provider: gemini
    prompt: agents/prompts/CODE-REVIEWER.md
    # model: gemini-2.5-pro          (default for gemini)
    count: 1

  - role: test-writer
    provider: openai
    prompt: agents/prompts/TEST-WRITER.md
    # model: o3                      (default for openai)
    count: 1

  - role: optimizer
    provider: anthropic
    prompt: agents/prompts/OPTIMIZER.md
    count: 1

docker:
  image: coding-swarm:latest
  # Map of provider → env var name holding the API key:
  api_keys:
    anthropic: ANTHROPIC_API_KEY
    gemini: GEMINI_API_KEY
    openai: OPENAI_API_KEY
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
