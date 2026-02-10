"""Git synchronization utilities for the coding swarm.

Handles the shared bare repository, per-agent workspace cloning,
push/pull cycles, and task-locking via files in current_tasks/.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path
from typing import Optional

from .config import SwarmConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(
    cmd: list[str], cwd: str | Path | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a subprocess with sensible defaults."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _git(
    args: list[str], cwd: str | Path | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    """Shortcut for running git commands."""
    return _run(["git"] + args, cwd=cwd, check=check)


# ---------------------------------------------------------------------------
# Upstream bare-repo management
# ---------------------------------------------------------------------------


def init_upstream_repo(
    upstream_dir: str | Path,
    source: str | Path | None = None,
    branch: str = "main",
) -> Path:
    """Create (or re-use) the bare git repository that all agents share.

    If *source* is provided it is cloned as the initial content.
    Otherwise an empty repo with a single initial commit is created.

    Returns:
        Absolute Path to the bare repo.
    """
    upstream = Path(upstream_dir).resolve()

    if upstream.exists() and (upstream / "HEAD").exists():
        # Already initialised — nothing to do.
        return upstream

    upstream.mkdir(parents=True, exist_ok=True)

    if source:
        # Clone the source into the bare repo
        _git(["clone", "--bare", str(source), str(upstream)])
    else:
        _git(["init", "--bare", "--initial-branch", branch, str(upstream)])

        # We need an initial commit so agents can clone immediately.
        # Create a temporary working tree to make the commit.
        tmp_work = upstream.parent / "_tmp_init"
        tmp_work.mkdir(exist_ok=True)
        _git(["clone", str(upstream), str(tmp_work)])
        _git(["checkout", "-b", branch], cwd=tmp_work)

        # Seed directories that the harness expects.
        (tmp_work / "current_tasks").mkdir(exist_ok=True)
        (tmp_work / "current_tasks" / ".gitkeep").touch()
        (tmp_work / "agent_logs").mkdir(exist_ok=True)
        (tmp_work / "agent_logs" / ".gitkeep").touch()

        readme = tmp_work / "PROGRESS.md"
        readme.write_text(
            textwrap.dedent("""\
            # Progress

            This file is maintained by the swarm agents.
            Each agent updates it with status, completed tasks, and next steps.
        """)
        )

        _git(["add", "."], cwd=tmp_work)
        _git(["commit", "-m", "Initial swarm scaffold"], cwd=tmp_work)
        _git(["push", "origin", branch], cwd=tmp_work)

        # Clean up temp
        import shutil

        shutil.rmtree(tmp_work, ignore_errors=True)

    return upstream


def seed_project_files(
    upstream_dir: str | Path,
    project_path: str | Path,
    branch: str = "main",
) -> None:
    """Copy an existing project's files into the upstream bare repo.

    Clones the bare repo to a temp dir, copies project files in,
    commits, and pushes.
    """
    import shutil

    upstream = Path(upstream_dir).resolve()
    project = Path(project_path).resolve()

    tmp = upstream.parent / "_tmp_seed"
    if tmp.exists():
        shutil.rmtree(tmp)

    _git(["clone", str(upstream), str(tmp)])
    _git(["checkout", branch], cwd=tmp, check=False)

    # Copy project files (skip .git and .swarm dirs)
    for item in project.iterdir():
        if item.name in (".git", ".swarm"):
            continue
        dest = tmp / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    _git(["add", "."], cwd=tmp)
    result = _git(["status", "--porcelain"], cwd=tmp)
    if result.stdout.strip():
        _git(["commit", "-m", "Seed project files"], cwd=tmp)
        _git(["push", "origin", branch], cwd=tmp)

    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Workspace operations (run inside a container or locally)
# ---------------------------------------------------------------------------


def clone_workspace(
    upstream_dir: str | Path,
    workspace_dir: str | Path = "/workspace",
    branch: str = "main",
) -> Path:
    """Clone the upstream bare repo into a workspace directory.

    Returns:
        Path to the cloned workspace.
    """
    workspace = Path(workspace_dir)
    if workspace.exists() and (workspace / ".git").exists():
        # Already cloned — just pull.
        _git(["fetch", "origin"], cwd=workspace)
        _git(["reset", "--hard", f"origin/{branch}"], cwd=workspace)
        return workspace

    workspace.mkdir(parents=True, exist_ok=True)
    _git(["clone", str(upstream_dir), str(workspace)])
    _git(["checkout", branch], cwd=workspace, check=False)
    return workspace


def sync_push(
    workspace_dir: str | Path,
    message: str = "Agent update",
    branch: str = "main",
) -> bool:
    """Pull latest from upstream, merge, and push the agent's changes.

    Returns:
        True if push succeeded, False on merge conflict or error.
    """
    ws = Path(workspace_dir)

    _git(["add", "-A"], cwd=ws)

    # Check if there's anything to commit
    status = _git(["status", "--porcelain"], cwd=ws)
    if not status.stdout.strip():
        return True  # nothing to push

    _git(["commit", "-m", message], cwd=ws, check=False)

    # Pull with rebase to keep history clean
    pull = _git(["pull", "--rebase", "origin", branch], cwd=ws, check=False)
    if pull.returncode != 0:
        # Abort rebase and try a regular merge
        _git(["rebase", "--abort"], cwd=ws, check=False)
        merge = _git(["pull", "--no-rebase", "origin", branch], cwd=ws, check=False)
        if merge.returncode != 0:
            # Auto-resolve: accept ours on conflict
            _git(["checkout", "--ours", "."], cwd=ws, check=False)
            _git(["add", "."], cwd=ws, check=False)
            _git(["commit", "-m", "Auto-merge: accept ours"], cwd=ws, check=False)

    push = _git(["push", "origin", branch], cwd=ws, check=False)
    return push.returncode == 0


# ---------------------------------------------------------------------------
# Task locking
# ---------------------------------------------------------------------------


def lock_task(
    workspace_dir: str | Path,
    task_name: str,
    agent_id: str,
    branch: str = "main",
) -> bool:
    """Claim a task by creating a lock file in current_tasks/.

    The lock file records the agent ID and a description.
    Push fails if another agent already claimed the same task → returns False.

    Returns:
        True if the lock was successfully pushed.
    """
    ws = Path(workspace_dir)
    tasks_dir = ws / "current_tasks"
    tasks_dir.mkdir(exist_ok=True)

    # Sanitise task name for filename
    safe_name = task_name.replace(" ", "_").replace("/", "_")
    lock_file = tasks_dir / f"{safe_name}.lock"

    if lock_file.exists():
        return False  # already locked locally

    lock_file.write_text(f"agent: {agent_id}\ntask: {task_name}\n")

    _git(["add", str(lock_file)], cwd=ws)
    _git(["commit", "-m", f"Lock task: {task_name} (agent {agent_id})"], cwd=ws)

    # Pull first, then push — if collision, another agent got there first
    _git(["pull", "--rebase", "origin", branch], cwd=ws, check=False)
    result = _git(["push", "origin", branch], cwd=ws, check=False)

    if result.returncode != 0:
        # Conflict — remove our lock and abort
        lock_file.unlink(missing_ok=True)
        _git(["reset", "--hard", f"origin/{branch}"], cwd=ws, check=False)
        return False

    return True


def unlock_task(
    workspace_dir: str | Path,
    task_name: str,
    branch: str = "main",
) -> None:
    """Remove a task lock after completion."""
    ws = Path(workspace_dir)
    safe_name = task_name.replace(" ", "_").replace("/", "_")
    lock_file = ws / "current_tasks" / f"{safe_name}.lock"

    if lock_file.exists():
        lock_file.unlink()
        _git(["add", "-A"], cwd=ws)
        _git(["commit", "-m", f"Unlock task: {task_name}"], cwd=ws)
        sync_push(ws, f"Unlock task: {task_name}", branch)


def list_active_tasks(workspace_dir: str | Path) -> list[dict[str, str]]:
    """Return a list of currently locked tasks with their agent assignments."""
    tasks_dir = Path(workspace_dir) / "current_tasks"
    if not tasks_dir.exists():
        return []

    tasks = []
    for lock_file in tasks_dir.glob("*.lock"):
        content = lock_file.read_text()
        info: dict[str, str] = {"file": lock_file.name}
        for line in content.strip().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()
        tasks.append(info)
    return tasks
