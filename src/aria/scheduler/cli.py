from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, cast

if TYPE_CHECKING:
    from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aria.config import get_config
from aria.scheduler.schema import TaskCategory, TaskPolicy, TaskRun, make_task
from aria.scheduler.store import TaskStore

app = typer.Typer(
    name="schedule",
    help="ARIA scheduler management CLI",
    no_args_is_help=True,
)
console = Console()


def _db_path() -> Path:
    config = get_config()
    return config.paths.runtime / "scheduler" / "scheduler.db"


async def _with_store() -> TaskStore:
    store = TaskStore(_db_path())
    await store.connect()
    return store


def _format_timestamp(ts: int | None) -> str:
    if ts is None:
        return "-"
    dt = datetime.fromtimestamp(ts / 1000, tz=UTC)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_payload(payload_str: str) -> dict:
    try:
        parsed = json.loads(payload_str)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON payload: {e}") from e
    if not isinstance(parsed, dict):
        raise typer.BadParameter("Payload must be a JSON object")
    return parsed


@app.command("list")
def schedule_list(
    status: Annotated[str | None, typer.Option("--status")] = None,
    category: Annotated[str | None, typer.Option("--category")] = None,
) -> None:
    asyncio.run(_schedule_list(status, category))


async def _schedule_list(status: str | None, category: str | None) -> None:
    store = await _with_store()
    try:
        tasks = await store.list_tasks(status=[status] if status else None, category=category)

        if not tasks:
            console.print("[yellow]No tasks found[/yellow]")
            return

        table = Table(title="Scheduled Tasks")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Category", style="magenta")
        table.add_column("Trigger", style="yellow")
        table.add_column("Status", style="blue")
        table.add_column("Policy", style="white")
        table.add_column("Next Run", style="white")

        for task in sorted(tasks, key=lambda t: t.next_run_at or 0):
            table.add_row(
                task.id[:8] + "...",
                task.name,
                task.category,
                task.trigger_type,
                task.status,
                task.policy,
                _format_timestamp(task.next_run_at),
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(tasks)} task(s)[/dim]")
    finally:
        await store.close()


@app.command("add")
def schedule_add(
    name: Annotated[str, typer.Option("--name", "-n", help="Task name")],
    cron: Annotated[
        str,
        typer.Option("--cron", "-c", help="Cron expression (e.g. '0 8 * * *')"),
    ],
    category: Annotated[
        str,
        typer.Option(
            "--category",
            "-g",
            help="Task category: search, workspace, memory, custom, system",
        ),
    ],
    payload: Annotated[
        str,
        typer.Option("--payload", "-p", help="JSON payload for the task"),
    ],
    policy: Annotated[
        str,
        typer.Option("--policy", help="Execution policy: allow, ask, deny"),
    ] = "allow",
    timezone: Annotated[
        str,
        typer.Option("--timezone", "-z", help="Timezone (default: Europe/Rome)"),
    ] = "Europe/Rome",
) -> None:
    asyncio.run(_schedule_add(name, cron, category, payload, policy, timezone))


async def _schedule_add(
    name: str,
    cron: str,
    category: str,
    payload: str,
    policy: str,
    timezone: str,
) -> None:
    from croniter import croniter  # type: ignore[import-untyped]

    if policy not in ("allow", "ask", "deny"):
        raise typer.BadParameter("Invalid policy. Must be one of: allow, ask, deny")

    if category not in ("search", "workspace", "memory", "custom", "system"):
        raise typer.BadParameter(
            "Invalid category. Must be one of: search, workspace, memory, custom, system"
        )

    if not croniter.is_valid(cron):
        raise typer.BadParameter(f"Invalid cron expression: {cron}")

    payload_dict = _parse_payload(payload)

    now = datetime.now(tz=UTC)
    next_run_dt = croniter(cron, now).get_next(datetime)

    task = make_task(
        name=name,
        category=cast("TaskCategory", category),
        trigger_type="cron",
        payload=payload_dict,
        schedule_cron=cron,
        policy=cast("TaskPolicy", policy),
        timezone=timezone,
        trigger_config={"cron": cron, "timezone": timezone},
    )
    task.next_run_at = int(next_run_dt.timestamp() * 1000)

    store = await _with_store()
    try:
        task_id = await store.create_task(task)
    finally:
        await store.close()

    console.print("[green]Task created successfully![/green]")
    console.print(f"  ID:       {task_id}")
    console.print(f"  Name:     {name}")
    console.print(f"  Category: {category}")
    console.print(f"  Cron:     {cron}")
    console.print(f"  Policy:   {policy}")


@app.command("remove")
def schedule_remove(
    id: Annotated[str, typer.Argument(help="Task ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
) -> None:
    asyncio.run(_schedule_remove(id, force))


async def _schedule_remove(task_id: str, force: bool) -> None:
    store = await _with_store()
    try:
        task = await store.get_task(task_id)
        if not task:
            console.print(f"[red]Task not found: {task_id}[/red]")
            raise typer.Exit(code=1)

        if not force:
            confirmed = typer.confirm(
                f"Remove task '{task.name}' ({task_id[:8]}...)?", default=False
            )
            if not confirmed:
                console.print("[yellow]Aborted[/yellow]")
                return

        deleted = await store.delete_task(task_id)
    finally:
        await store.close()

    if deleted:
        console.print(f"[green]Task removed: {task_id}[/green]")
    else:
        console.print(f"[red]Failed to remove task: {task_id}[/red]")
        raise typer.Exit(code=1)


@app.command("run")
def schedule_run(
    id: Annotated[str, typer.Argument(help="Task ID to run")],
) -> None:
    asyncio.run(_schedule_run(id))


async def _schedule_run(task_id: str) -> None:
    store = await _with_store()
    try:
        task = await store.get_task(task_id)
        if not task:
            console.print(f"[red]Task not found: {task_id}[/red]")
            raise typer.Exit(code=1)

        if task.status == "dlq":
            console.print(
                "[yellow]Task is in DLQ. "
                f"Use 'aria schedule replay {task_id[:8]}' instead.[/yellow]"
            )
            raise typer.Exit(code=1)

        now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
        await store.update_task(task_id, next_run_at=now_ms, status="active")

        queued_run = TaskRun(
            task_id=task_id,
            started_at=now_ms,
            finished_at=now_ms,
            outcome="success",
            result_summary="Manual trigger requested via CLI",
        )
        await store.record_run(queued_run)
    finally:
        await store.close()

    console.print(f"[green]Task queued for run: {task_id}[/green]")


@app.command("replay")
def schedule_replay(
    id: Annotated[str, typer.Argument(help="Task ID to replay from DLQ")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
) -> None:
    asyncio.run(_schedule_replay(id, force))


async def _schedule_replay(task_id: str, force: bool) -> None:
    store = await _with_store()
    try:
        task = await store.get_task(task_id)
        if not task:
            console.print(f"[red]Task not found: {task_id}[/red]")
            raise typer.Exit(code=1)

        if task.status != "dlq":
            console.print(f"[yellow]Task is not in DLQ (status: {task.status}).[/yellow]")
            return

        if not force:
            confirmed = typer.confirm(
                f"Replay task '{task.name}' ({task_id[:8]}...)?", default=False
            )
            if not confirmed:
                console.print("[yellow]Aborted[/yellow]")
                return

        now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
        await store.update_task(
            task_id,
            status="active",
            retry_count=0,
            last_error=None,
            next_run_at=now_ms,
        )
    finally:
        await store.close()

    console.print(f"[green]Task replayed: {task_id}[/green]")


@app.command("status")
def schedule_status(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed information")
    ] = False,
) -> None:
    asyncio.run(_schedule_status(verbose))


async def _schedule_status(verbose: bool) -> None:
    store = await _with_store()
    try:
        all_tasks = await store.list_tasks()
    finally:
        await store.close()

    counts: dict[str, int] = {}
    categories: dict[str, int] = {}
    for task in all_tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
        categories[task.category] = categories.get(task.category, 0) + 1

    console.print("\n[bold]ARIA Scheduler Status[/bold]")
    console.print(f"  Total tasks: {len(all_tasks)}")

    for status, count in sorted(counts.items()):
        color = {
            "active": "green",
            "paused": "yellow",
            "dlq": "red",
            "completed": "blue",
            "failed": "red",
        }.get(status, "white")
        console.print(f"  [{color}]{status}[/{color}]: {count}")

    if categories:
        console.print("\n[bold]By Category:[/bold]")
        for cat, count in sorted(categories.items()):
            console.print(f"  {cat}: {count}")

    if verbose:
        console.print("\n[bold]Task Details:[/bold]")
        for task in sorted(all_tasks, key=lambda t: t.name):
            console.print(
                f"  [{task.status}] {task.name} ({task.id[:8]}...) "
                f"next={_format_timestamp(task.next_run_at)}"
            )
            if task.last_error:
                console.print(f"    Error: {task.last_error[:80]}")


def main() -> int:
    app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
