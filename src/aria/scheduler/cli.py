# Scheduler CLI - typer-based command interface for aria schedule
#
# W1.2.M: CLI scheduler commands
# - list    : List scheduled tasks with optional filters
# - add     : Add a new scheduled task
# - remove  : Remove a task by ID
# - run     : Manually trigger a task (no wait)
# - replay  : Resume a task from DLQ
# - status  : Show scheduler status
#
# Usage:
#   aria schedule list [--status STATUS] [--category CAT]
#   aria schedule add --name N --cron 'expr' --category CAT --payload '{json}'
#   aria schedule remove <id>
#   aria schedule run <id>
#   aria schedule replay <id>
#   aria schedule status [--verbose]

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from aria.config import get_config

app = typer.Typer(
    name="schedule",
    help="ARIA scheduler management CLI",
    no_args_is_help=True,
)
console = Console()


# === TaskStore stub (will be replaced by full W1.2.A implementation) ===
# This provides a minimal interface for CLI operations during Sprint 1.2


class TaskStore:
    """Minimal task store stub for CLI operations.

    Full implementation in W1.2.A (store.py).
    This stub provides read/write to an in-memory store for CLI testing.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._tasks: dict[str, dict] = {}

    async def connect(self) -> None:
        pass

    async def create_task(self, task: dict) -> str:
        task_id = task.get("id") or str(uuid.uuid4())
        task["id"] = task_id
        task["created_at"] = int(datetime.now(tz=UTC).timestamp() * 1000)
        task["updated_at"] = task["created_at"]
        self._tasks[task_id] = task
        return task_id

    async def update_task(self, task_id: str, **fields: object) -> None:
        if task_id in self._tasks:
            self._tasks[task_id].update(fields)
            self._tasks[task_id]["updated_at"] = int(datetime.now(tz=UTC).timestamp() * 1000)

    async def get_task(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    async def list_tasks(
        self,
        status: list[str] | None = None,
        category: str | None = None,
    ) -> list[dict]:
        results = list(self._tasks.values())
        if status:
            results = [t for t in results if t.get("status") in status]
        if category:
            results = [t for t in results if t.get("category") == category]
        return results

    async def delete_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    async def move_to_dlq(self, task_id: str, reason: str) -> None:
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = "dlq"
            self._tasks[task_id]["last_error"] = reason
            self._tasks[task_id]["updated_at"] = int(datetime.now(tz=UTC).timestamp() * 1000)

    async def record_run(self, run: dict) -> str:
        return run.get("id") or str(uuid.uuid4())


# === Helper functions ===


def _get_store() -> TaskStore:
    """Get TaskStore instance."""
    config = get_config()
    db_path = str(config.paths.runtime / "scheduler" / "scheduler.db")
    return TaskStore(db_path)


def _format_timestamp(ts: int | None) -> str:
    if ts is None:
        return "-"
    dt = datetime.fromtimestamp(ts / 1000, tz=UTC)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_payload(payload_str: str) -> dict:
    """Parse JSON payload from string."""
    try:
        return json.loads(payload_str)  # type: ignore[no-any-return]
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON payload: {e}") from e


# === CLI Commands (async) ===


@app.command("list")
def schedule_list(
    status: Annotated[str | None, typer.Option("--status")] = None,
    category: Annotated[str | None, typer.Option("--category")] = None,
) -> None:
    """List scheduled tasks with optional filters.

    Examples:
        aria schedule list
        aria schedule list --status active
        aria schedule list --category search
    """
    asyncio.run(_schedule_list(status, category))


async def _schedule_list(status: str | None, category: str | None) -> None:
    """Async implementation of schedule list."""
    store = _get_store()
    await store.connect()

    status_filter = [status] if status else None
    tasks = await store.list_tasks(status=status_filter, category=category)

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

    for task in sorted(tasks, key=lambda t: t.get("next_run_at") or 0):
        next_run = _format_timestamp(task.get("next_run_at"))
        table.add_row(
            task.get("id", "-")[:8] + "...",
            task.get("name", "-"),
            task.get("category", "-"),
            task.get("trigger_type", "-"),
            task.get("status", "-"),
            task.get("policy", "-"),
            next_run,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(tasks)} task(s)[/dim]")


@app.command("add")
def schedule_add(
    name: Annotated[str, typer.Option("--name", "-n", help="Task name")],
    cron: Annotated[str, typer.Option("--cron", "-c", help="Cron expression (e.g. '0 8 * * *')")],
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
        typer.Option(
            "--policy",
            help="Execution policy: allow, ask, deny",
        ),
    ] = "allow",
    timezone: Annotated[
        str,
        typer.Option("--timezone", "-z", help="Timezone (default: Europe/Rome)"),
    ] = "Europe/Rome",
) -> None:
    """Add a new scheduled task.

    Examples:
        aria schedule add --name "Daily search" --cron "0 8 * * *" --category search \\
            --payload '{"prompt": "search topics", "sub_agent": "search"}'

        aria schedule add -n "Weekly report" -c "0 9 * * 1" -g memory \\
            -p '{"task": "generate_report"}' --policy ask
    """
    asyncio.run(_schedule_add(name, cron, category, payload, policy, timezone))


async def _schedule_add(
    name: str,
    cron: str,
    category: str,
    payload: str,
    policy: str,
    timezone: str,
) -> None:
    """Async implementation of schedule add."""
    # Validate policy
    valid_policies = ("allow", "ask", "deny")
    if policy not in valid_policies:
        raise typer.BadParameter(f"Invalid policy: {policy}. Must be one of: {valid_policies}")

    # Validate category
    valid_categories = ("search", "workspace", "memory", "custom", "system")
    if category not in valid_categories:
        raise typer.BadParameter(
            f"Invalid category: {category}. Must be one of: {valid_categories}"
        )

    # Validate cron expression
    try:
        from croniter import croniter  # type: ignore[import-untyped]

        if not croniter.is_valid(cron):
            raise typer.BadParameter(f"Invalid cron expression: {cron}")
    except ImportError:
        console.print("[yellow]Warning: croniter not installed, skipping cron validation[/yellow]")

    payload_dict = _parse_payload(payload)

    task = {
        "id": str(uuid.uuid4()),
        "name": name,
        "category": category,
        "trigger_type": "cron",
        "trigger_config": json.dumps({"cron": cron, "timezone": timezone}),
        "schedule_cron": cron,
        "timezone": timezone,
        "next_run_at": None,  # Calculated by scheduler
        "status": "active",
        "policy": policy,
        "budget_tokens": None,
        "budget_cost_eur": None,
        "max_retries": 3,
        "retry_count": 0,
        "last_error": None,
        "owner_user_id": None,
        "payload": payload_dict,
        "lease_owner": None,
        "lease_expires_at": None,
    }

    store = _get_store()
    await store.connect()
    task_id = await store.create_task(task)

    console.print("[green]Task created successfully![/green]")
    console.print(f"  ID:       {task_id}")
    console.print(f"  Name:     {name}")
    console.print(f"  Category: {category}")
    console.print(f"  Cron:     {cron}")
    console.print(f"  Policy:   {policy}")


@app.command("remove")
def schedule_remove(
    id: Annotated[str, typer.Argument(help="Task ID to remove")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Remove a scheduled task by ID.

    Examples:
        aria schedule remove 12345678-1234-1234-1234-123456789abc
        aria schedule remove 12345678 --force
    """
    asyncio.run(_schedule_remove(id, force))


async def _schedule_remove(task_id: str, force: bool) -> None:
    """Async implementation of schedule remove."""
    store = _get_store()
    await store.connect()

    task = await store.get_task(task_id)
    if not task:
        console.print(f"[red]Task not found: {task_id}[/red]")
        raise typer.Exit(code=1)

    if not force:
        confirmed = typer.confirm(
            f"Remove task '{task.get('name')}' ({task_id[:8]}...)?",
            default=False,
        )
        if not confirmed:
            console.print("[yellow]Aborted[/yellow]")
            return

    deleted = await store.delete_task(task_id)
    if deleted:
        console.print(f"[green]Task removed: {task_id}[/green]")
    else:
        console.print(f"[red]Failed to remove task: {task_id}[/red]")
        raise typer.Exit(code=1)


@app.command("run")
def schedule_run(
    id: Annotated[str, typer.Argument(help="Task ID to run")],
) -> None:
    """Manually trigger a task (no wait for completion).

    Examples:
        aria schedule run 12345678-1234-1234-1234-123456789abc
    """
    asyncio.run(_schedule_run(id))


async def _schedule_run(task_id: str) -> None:
    """Async implementation of schedule run."""
    store = _get_store()
    await store.connect()

    task = await store.get_task(task_id)
    if not task:
        console.print(f"[red]Task not found: {task_id}[/red]")
        raise typer.Exit(code=1)

    if task.get("status") == "dlq":
        console.print(
            f"[yellow]Task is in DLQ. Use 'aria schedule replay {task_id[:8]}' instead.[/yellow]"
        )
        raise typer.Exit(code=1)

    # Record a manual run
    run_id = str(uuid.uuid4())
    run = {
        "id": run_id,
        "task_id": task_id,
        "started_at": int(datetime.now(tz=UTC).timestamp() * 1000),
        "finished_at": None,
        "outcome": "manual_trigger",
        "tokens_used": None,
        "cost_eur": None,
        "result_summary": "Manually triggered via CLI",
        "logs_path": None,
    }

    await store.record_run(run)

    console.print(f"[green]Task triggered: {task_id}[/green]")
    console.print(f"  Run ID: {run_id}")
    console.print(f"  Name:   {task.get('name')}")


@app.command("replay")
def schedule_replay(
    id: Annotated[str, typer.Argument(help="Task ID to replay from DLQ")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Resume a task from the Dead Letter Queue.

    Examples:
        aria schedule replay 12345678-1234-1234-1234-123456789abc
    """
    asyncio.run(_schedule_replay(id, force))


async def _schedule_replay(task_id: str, force: bool) -> None:
    """Async implementation of schedule replay."""
    store = _get_store()
    await store.connect()

    task = await store.get_task(task_id)
    if not task:
        console.print(f"[red]Task not found: {task_id}[/red]")
        raise typer.Exit(code=1)

    if task.get("status") != "dlq":
        status = task.get("status")
        console.print(f"[yellow]Task is not in DLQ (status: {status}). Nothing to replay.[/yellow]")
        return

    if not force:
        confirmed = typer.confirm(
            f"Replay task '{task.get('name')}' ({task_id[:8]}...)?",
            default=False,
        )
        if not confirmed:
            console.print("[yellow]Aborted[/yellow]")
            return

    # Reset task status and retry count
    await store.update_task(
        task_id,
        status="active",
        retry_count=0,
        last_error=None,
    )

    console.print(f"[green]Task replayed: {task_id}[/green]")
    console.print(f"  Name:   {task.get('name')}")
    console.print("  Status: active")


@app.command("status")
def schedule_status(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed information"),
    ] = False,
) -> None:
    """Show scheduler status.

    Examples:
        aria schedule status
        aria schedule status --verbose
    """
    asyncio.run(_schedule_status(verbose))


async def _schedule_status(verbose: bool) -> None:
    """Async implementation of schedule status."""
    store = _get_store()
    await store.connect()

    all_tasks = await store.list_tasks()

    # Count by status
    counts: dict[str, int] = {}
    for task in all_tasks:
        status = task.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1

    # Display summary
    console.print("\n[bold]ARIA Scheduler Status[/bold]")
    console.print(f"  Total tasks: {len(all_tasks)}")

    if counts:
        for status, count in sorted(counts.items()):
            color = {
                "active": "green",
                "paused": "yellow",
                "dlq": "red",
                "completed": "blue",
                "failed": "red",
            }.get(status, "white")
            console.print(f"  [{color}]{status}[/{color}]: {count}")

    # Count by category
    categories: dict[str, int] = {}
    for task in all_tasks:
        cat = task.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    if categories:
        console.print("\n[bold]By Category:[/bold]")
        for cat, count in sorted(categories.items()):
            console.print(f"  {cat}: {count}")

    if verbose:
        console.print("\n[bold]Task Details:[/bold]")
        for task in sorted(all_tasks, key=lambda t: t.get("name", "")):
            status_color = {
                "active": "green",
                "paused": "yellow",
                "dlq": "red",
                "completed": "blue",
                "failed": "red",
            }.get(task.get("status", ""), "white")
            console.print(
                f"  [{status_color}]{task.get('status', '?')}[/{status_color}] "
                f"{task.get('name', '?')} ({task.get('id', '')[:8]}...)"
            )
            if task.get("last_error"):
                console.print(f"    Error: {task.get('last_error', '')[:60]}")

    console.print()


def main() -> int:
    """Entry point for the schedule CLI."""
    app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
