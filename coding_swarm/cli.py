"""CLI entry point for the coding swarm framework.

Provides the ``swarm`` command with subcommands for initialising,
launching, monitoring, and stopping the parallel agent swarm.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from . import __version__
from .config import generate_template, load_config
from .core import SwarmOrchestrator
from .monitor import SwarmMonitor


# Keep a module-level reference so ``stop`` can reach a running orchestrator.
_orchestrator: SwarmOrchestrator | None = None


@click.group()
@click.version_option(__version__, prog_name="coding-swarm")
def cli() -> None:
    """🐝 coding-swarm — Run parallel AI agents against any codebase."""
    pass


# ---- init -----------------------------------------------------------------


@cli.command()
@click.option(
    "--output",
    "-o",
    default="swarm.yaml",
    help="Where to write the template config.",
)
def init(output: str) -> None:
    """Create a starter swarm.yaml in the current directory."""
    try:
        path = generate_template(output)
        click.echo(f"✅ Created {path}")
        click.echo("   Edit it, then run: swarm launch")
    except FileExistsError:
        click.echo(f"⚠️  {output} already exists. Use -o to pick another name.")
        sys.exit(1)


# ---- launch ---------------------------------------------------------------


@cli.command()
@click.option(
    "--config",
    "-c",
    default="swarm.yaml",
    help="Path to swarm.yaml config file.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print what would be done without starting containers.",
)
def launch(config: str, dry_run: bool) -> None:
    """Start the agent swarm (Docker containers + harness loop)."""
    global _orchestrator

    try:
        cfg = load_config(config)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"❌ {exc}")
        sys.exit(1)

    if dry_run:
        click.echo("🔍 Dry-run mode — would launch:\n")
        total = 0
        for agent in cfg.agents:
            for i in range(agent.count):
                click.echo(
                    f"   🤖 {agent.role}-{i}  provider={agent.provider}  model={agent.model}  prompt={agent.prompt}"
                )
                total += 1
        click.echo(f"\n   Total: {total} agent(s)")
        click.echo(f"   Image: {cfg.docker.image}")
        click.echo(f"   Upstream: {cfg.upstream_dir}")
        return

    _orchestrator = SwarmOrchestrator(cfg)
    _orchestrator.launch()


# ---- status ---------------------------------------------------------------


@cli.command()
@click.option("--config", "-c", default="swarm.yaml", help="Path to swarm config.")
def status(config: str) -> None:
    """Show running agents and their current tasks."""
    try:
        cfg = load_config(config)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"❌ {exc}")
        sys.exit(1)

    monitor = SwarmMonitor(cfg)
    monitor.print_dashboard()


# ---- logs -----------------------------------------------------------------


@cli.command()
@click.argument("agent_id", required=False)
@click.option("--config", "-c", default="swarm.yaml")
@click.option("--tail", "-n", default=50, help="Number of lines to show.")
def logs(agent_id: str | None, config: str, tail: int) -> None:
    """View logs for a specific agent (or list all log files)."""
    try:
        cfg = load_config(config)
    except (FileNotFoundError, ValueError):
        click.echo("❌ Could not load config.")
        sys.exit(1)

    logs_dir = Path(cfg.logs_dir)
    if not logs_dir.exists():
        click.echo("No log files found yet.")
        return

    if agent_id is None:
        click.echo("📁 Available log files:\n")
        for f in sorted(
            logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            size = f.stat().st_size
            click.echo(f"   {f.name}  ({size:,} bytes)")
        return

    # Find matching log
    matches = list(logs_dir.glob(f"*{agent_id}*"))
    if not matches:
        click.echo(f"No log files matching '{agent_id}'")
        return

    log_file = matches[0]
    lines = log_file.read_text().splitlines()
    for line in lines[-tail:]:
        click.echo(line)


# ---- stop -----------------------------------------------------------------


@cli.command()
@click.option("--config", "-c", default="swarm.yaml")
def stop(config: str) -> None:
    """Stop all running swarm agents."""
    global _orchestrator

    if _orchestrator:
        _orchestrator.stop()
        _orchestrator = None
        return

    # If no orchestrator in memory, try to find running containers by name pattern
    import subprocess

    result = subprocess.run(
        ["docker", "ps", "--filter", "name=swarm-", "--format", "{{.ID}} {{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if not result.stdout.strip():
        click.echo("No swarm containers found.")
        return

    click.echo("🛑 Stopping swarm containers ...\n")
    for line in result.stdout.strip().splitlines():
        cid, name = line.split(None, 1)
        click.echo(f"   Stopping {name} ({cid}) ...")
        subprocess.run(["docker", "stop", cid], capture_output=True, check=False)
        subprocess.run(["docker", "rm", cid], capture_output=True, check=False)
    click.echo("\n✅ Done.")


# ---- dashboard (live) ----------------------------------------------------


@cli.command()
@click.option("--config", "-c", default="swarm.yaml")
@click.option("--interval", "-i", default=10, help="Refresh interval in seconds.")
def dashboard(config: str, interval: int) -> None:
    """Live-refresh dashboard showing swarm activity."""
    import time

    try:
        cfg = load_config(config)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"❌ {exc}")
        sys.exit(1)

    monitor = SwarmMonitor(cfg)
    click.echo("Press Ctrl+C to exit.\n")

    try:
        while True:
            click.clear()
            monitor.print_dashboard()
            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("\n👋 Exiting dashboard.")


# ---- Entry point ----------------------------------------------------------


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
