"""Real-time monitoring of swarm agent activity.

Watches agent logs, current task locks, and git history to provide
a live dashboard of what the swarm is doing.
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import SwarmConfig
from .sync import list_active_tasks


def _git_log(repo_dir: str | Path, count: int = 10) -> list[dict[str, str]]:
    """Fetch recent git log entries from the upstream repo."""
    repo = Path(repo_dir)
    if not repo.exists():
        return []

    # Clone to a temp dir to read log (bare repos need a worktree)
    result = subprocess.run(
        ["git", "log", f"--max-count={count}", "--format=%H|%an|%ar|%s"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []

    entries = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            entries.append(
                {
                    "hash": parts[0][:8],
                    "author": parts[1],
                    "when": parts[2],
                    "message": parts[3],
                }
            )
    return entries


class SwarmMonitor:
    """Provides a snapshot of the swarm's current state.

    Usage::

        monitor = SwarmMonitor(config, work_dir=".")
        snapshot = monitor.snapshot()
        monitor.print_dashboard()
    """

    def __init__(self, config: SwarmConfig, work_dir: str | Path = ".") -> None:
        self.config = config
        self.work_dir = Path(work_dir).resolve()
        self.upstream_dir = self.work_dir / config.upstream_dir
        self.logs_dir = self.work_dir / config.logs_dir

    def active_tasks(self) -> list[dict[str, str]]:
        """Return currently locked tasks (from the upstream repo)."""
        # We need a working copy to read current_tasks/
        # Use the logs dir as a temp clone
        clone_dir = self.work_dir / ".swarm" / "_monitor_clone"
        if not clone_dir.exists():
            clone_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", str(self.upstream_dir), str(clone_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            subprocess.run(
                ["git", "pull", "--rebase"],
                cwd=clone_dir,
                capture_output=True,
                text=True,
                check=False,
            )
        return list_active_tasks(clone_dir)

    def recent_commits(self, count: int = 10) -> list[dict[str, str]]:
        """Return recent commit log entries."""
        return _git_log(self.upstream_dir, count)

    def agent_log_files(self) -> list[Path]:
        """Return paths to all agent log files, sorted by modification time."""
        if not self.logs_dir.exists():
            return []
        logs = sorted(
            self.logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        return logs

    def snapshot(self) -> dict:
        """Gather a full dashboard snapshot."""
        return {
            "timestamp": datetime.now().isoformat(),
            "active_tasks": self.active_tasks(),
            "recent_commits": self.recent_commits(),
            "log_files": [str(p.name) for p in self.agent_log_files()],
        }

    def print_dashboard(self) -> None:
        """Print a human-readable dashboard to stdout."""
        snap = self.snapshot()

        print("=" * 60)
        print(f"  🐝 CODING SWARM DASHBOARD — {snap['timestamp']}")
        print("=" * 60)

        # Active tasks
        tasks = snap["active_tasks"]
        print(f"\n📋 Active Tasks ({len(tasks)}):")
        if tasks:
            for t in tasks:
                agent = t.get("agent", "?")
                task = t.get("task", t.get("file", "?"))
                print(f"   🔒 {task}  ←  agent: {agent}")
        else:
            print("   (none)")

        # Recent commits
        commits = snap["recent_commits"]
        print(f"\n📝 Recent Commits ({len(commits)}):")
        for c in commits[:8]:
            print(f"   {c['hash']}  {c['when']:>15}  {c['message']}")

        # Log files
        logs = snap["log_files"]
        print(f"\n📁 Agent Logs ({len(logs)} files):")
        for log in logs[:5]:
            print(f"   {log}")

        print("\n" + "=" * 60)
