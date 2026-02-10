"""Swarm orchestrator — manages Docker containers and agent lifecycle.

This is the main engine: it creates a bare git repo, builds or pulls
the Docker image, spins up N containers (one per agent instance), and
provides methods to monitor and stop them.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import AgentConfig, SwarmConfig
from .sync import init_upstream_repo, seed_project_files


# ---------------------------------------------------------------------------
# Agent container descriptor
# ---------------------------------------------------------------------------


@dataclass
class AgentContainer:
    """Tracks a single running agent container."""

    container_id: str
    agent_id: str
    role: str
    model: str
    prompt_file: str
    status: str = "running"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class SwarmOrchestrator:
    """Creates and manages the parallel agent swarm.

    Usage::

        config = load_config("swarm.yaml")
        orch = SwarmOrchestrator(config)
        orch.launch()
        orch.status()
        orch.stop()
    """

    def __init__(self, config: SwarmConfig, work_dir: str | Path = ".") -> None:
        self.config = config
        self.work_dir = Path(work_dir).resolve()
        self.upstream_dir = self.work_dir / config.upstream_dir
        self.logs_dir = self.work_dir / config.logs_dir
        self.containers: list[AgentContainer] = []

    # ---- Docker helpers ---------------------------------------------------

    @staticmethod
    def _docker(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker"] + args,
            capture_output=True,
            text=True,
            check=check,
        )

    def _ensure_image(self) -> None:
        """Build the Docker image if a Dockerfile exists, otherwise pull."""
        image = self.config.docker.image
        build_ctx = Path(self.config.docker.build_context)

        dockerfile = build_ctx / "Dockerfile"
        if dockerfile.exists():
            print(f"📦 Building Docker image '{image}' ...")
            self._docker(["build", "-t", image, str(build_ctx)])
        else:
            # Check if image exists locally
            result = self._docker(["image", "inspect", image], check=False)
            if result.returncode != 0:
                print(f"📥 Pulling Docker image '{image}' ...")
                self._docker(["pull", image])

    def _build_env_args(self, agent_cfg: AgentConfig) -> list[str]:
        """Build the -e flags for docker run."""
        env_args: list[str] = []

        # Pass all provider API keys so mixed swarms work
        for provider, env_var in self.config.docker.api_keys.items():
            api_key = os.environ.get(env_var, "")
            if api_key:
                env_args += ["-e", f"{env_var}={api_key}"]

        # Provider
        env_args += ["-e", f"AGENT_PROVIDER={agent_cfg.provider}"]

        # Model
        env_args += ["-e", f"AGENT_MODEL={agent_cfg.model}"]

        # Role
        env_args += ["-e", f"AGENT_ROLE={agent_cfg.role}"]

        # Extra env
        for key, val in self.config.docker.extra_env.items():
            env_args += ["-e", f"{key}={val}"]

        return env_args

    def _build_volume_args(self) -> list[str]:
        """Build the -v flags for docker run."""
        vol_args: list[str] = []

        # Mount the upstream bare repo
        vol_args += ["-v", f"{self.upstream_dir}:/upstream"]

        # Mount log directory
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        vol_args += ["-v", f"{self.logs_dir}:/logs"]

        # User-specified volumes
        for host, container in self.config.docker.volumes.items():
            vol_args += ["-v", f"{host}:{container}"]

        return vol_args

    # ---- Public API -------------------------------------------------------

    def launch(self) -> list[AgentContainer]:
        """Initialize the upstream repo and launch all agent containers.

        Returns:
            List of AgentContainer descriptors for the launched agents.
        """
        print("🚀 Launching coding swarm ...\n")

        # 1. Create the bare upstream repo
        print(f"📂 Initializing upstream repo at {self.upstream_dir}")
        source = self.config.project.repo_url or None
        init_upstream_repo(
            self.upstream_dir, source=source, branch=self.config.project.branch
        )

        # 2. If a local project path is given, seed its files
        if self.config.project.repo_path:
            project_path = Path(self.config.project.repo_path)
            if project_path.exists() and project_path.is_dir():
                print(f"📄 Seeding project files from {project_path}")
                seed_project_files(
                    self.upstream_dir, project_path, self.config.project.branch
                )

        # 3. Build / pull Docker image
        self._ensure_image()

        # 4. Spin up containers
        print()
        agent_index = 0
        for agent_cfg in self.config.agents:
            for i in range(agent_cfg.count):
                agent_id = f"{agent_cfg.role}-{i}"
                agent_index += 1

                print(f"  🤖 Starting agent {agent_id} (model={agent_cfg.model})")

                env_args = self._build_env_args(agent_cfg)
                vol_args = self._build_volume_args()

                # Read the prompt file and pass it as AGENT_PROMPT env var
                prompt_path = self.work_dir / agent_cfg.prompt
                if prompt_path.exists():
                    env_args += ["-e", f"AGENT_PROMPT_FILE=/prompts/{prompt_path.name}"]
                    vol_args += ["-v", f"{prompt_path.parent}:/prompts:ro"]

                env_args += ["-e", f"AGENT_ID={agent_id}"]
                env_args += ["-e", f"BRANCH={self.config.project.branch}"]
                env_args += ["-e", f"TEST_COMMAND={self.config.project.test_command}"]

                cmd = (
                    [
                        "docker",
                        "run",
                        "-d",
                        "--name",
                        f"swarm-{agent_id}",
                        "--hostname",
                        agent_id,
                    ]
                    + env_args
                    + vol_args
                    + [
                        self.config.docker.image,
                    ]
                )

                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=False
                )
                if result.returncode != 0:
                    print(f"    ❌ Failed to start {agent_id}: {result.stderr.strip()}")
                    continue

                container_id = result.stdout.strip()[:12]
                container = AgentContainer(
                    container_id=container_id,
                    agent_id=agent_id,
                    role=agent_cfg.role,
                    model=agent_cfg.model,
                    prompt_file=agent_cfg.prompt,
                )
                self.containers.append(container)
                print(f"    ✅ Started → {container_id}")

        print(f"\n🎉 Swarm launched with {len(self.containers)} agent(s)\n")
        return self.containers

    def status(self) -> list[dict]:
        """Return the current status of all swarm containers."""
        statuses = []
        for c in self.containers:
            result = self._docker(
                ["inspect", "--format", "{{.State.Status}}", c.container_id],
                check=False,
            )
            state = result.stdout.strip() if result.returncode == 0 else "unknown"
            statuses.append(
                {
                    "agent_id": c.agent_id,
                    "container_id": c.container_id,
                    "role": c.role,
                    "model": c.model,
                    "state": state,
                }
            )
        return statuses

    def stop(self) -> None:
        """Gracefully stop all swarm containers."""
        print("🛑 Stopping swarm ...\n")
        for c in self.containers:
            print(f"  Stopping {c.agent_id} ({c.container_id}) ...")
            self._docker(["stop", c.container_id], check=False)
            self._docker(["rm", c.container_id], check=False)
        self.containers.clear()
        print("\n✅ All agents stopped.\n")

    def logs(self, agent_id: str, tail: int = 50) -> str:
        """Retrieve recent logs from a specific agent container."""
        for c in self.containers:
            if c.agent_id == agent_id:
                result = self._docker(
                    ["logs", "--tail", str(tail), c.container_id],
                    check=False,
                )
                return result.stdout + result.stderr
        return f"Agent '{agent_id}' not found."

    def list_running_agents(self) -> list[str]:
        """Return agent IDs of containers currently in 'running' state."""
        running = []
        for s in self.status():
            if s["state"] == "running":
                running.append(s["agent_id"])
        return running
