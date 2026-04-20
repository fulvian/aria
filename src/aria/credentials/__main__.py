from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from aria.config import get_config
from aria.credentials.manager import CredentialManager

app = typer.Typer(help="ARIA credentials management CLI")
console = Console()


def _format_datetime(dt_value: str | None) -> str:
    if dt_value is None:
        return "-"
    try:
        dt = datetime.fromisoformat(dt_value)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return dt_value


def _display_status(status: dict) -> None:
    if "error" in status:
        console.print(f"[red]Error:[/red] {status['error']}")
        return

    table = Table(
        title=f"Provider: {status.get('provider', '-')} (strategy: {status.get('strategy', '-')})"
    )
    table.add_column("Key ID", style="cyan")
    table.add_column("State", style="yellow")
    table.add_column("Credits", justify="right")
    table.add_column("Failures", justify="right")
    table.add_column("Cooldown Until")
    table.add_column("Last Used")

    for key_status in status.get("keys", []):
        state = key_status.get("circuit_state", "unknown")
        color = {"closed": "green", "open": "red", "half_open": "yellow"}.get(state, "white")
        credits = key_status.get("credits_remaining")
        table.add_row(
            key_status.get("key_id", "-"),
            f"[{color}]{state}[/{color}]",
            str(credits) if credits is not None else "unlimited",
            str(key_status.get("failure_count", 0)),
            _format_datetime(key_status.get("cooldown_until")),
            _format_datetime(key_status.get("last_used_at")),
        )

    console.print(table)


def _display_audit_trail(log_path: Path, tail: int) -> None:
    if not log_path.exists():
        console.print("[yellow]No audit log found[/yellow]")
        return

    entries = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    recent = entries[-tail:]

    table = Table(title=f"Recent Audit Entries (last {len(recent)})")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Op", style="magenta")
    table.add_column("Provider", style="green")
    table.add_column("Key ID", style="yellow")
    table.add_column("Result")
    table.add_column("Credits", justify="right")
    table.add_column("Error")

    for raw_line in recent:
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        table.add_row(
            entry.get("ts", "-"),
            entry.get("op", "-"),
            entry.get("provider", "-"),
            entry.get("key_id", "-"),
            entry.get("result", "-"),
            str(entry.get("credits_remaining", "-")),
            str(entry.get("error", ""))[:80],
        )

    console.print(table)


@app.command("list")
def list_credentials(provider: Annotated[str | None, typer.Option("--provider")] = None) -> None:
    cm = CredentialManager(get_config())
    status = cm.status(provider)
    if provider is not None:
        _display_status(status)
        return
    for provider_name, provider_status in status.items():
        console.print(f"\n[bold]{provider_name}[/bold]")
        _display_status(provider_status)


@app.command()
def rotate(provider: str) -> None:
    cm = CredentialManager(get_config())
    key = asyncio.run(cm.acquire(provider, strategy="round_robin"))
    if key is None:
        console.print(f"[yellow]No keys available for {provider}[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"[green]Acquired key: {key.key_id}[/green]")


@app.command()
def status(provider: Annotated[str | None, typer.Option("--provider")] = None) -> None:
    cm = CredentialManager(get_config())
    result = cm.status(provider)
    if provider is not None:
        _display_status(result)
        return
    for provider_name, provider_status in result.items():
        console.print(f"\n[bold]{provider_name}[/bold]")
        _display_status(provider_status)


@app.command()
def audit(tail: Annotated[int, typer.Option("--tail")] = 20) -> None:
    aria_home = Path(get_config().home)
    log_dir = aria_home / ".aria" / "runtime" / "logs"
    log_path = log_dir / f"credentials-{datetime.now(tz=UTC).strftime('%Y-%m-%d')}.log"
    _display_audit_trail(log_path, tail)


@app.command()
def reload() -> None:
    cm = CredentialManager(get_config())
    cm.reload()
    console.print("[green]Credentials reloaded[/green]")


def main() -> int:
    app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
