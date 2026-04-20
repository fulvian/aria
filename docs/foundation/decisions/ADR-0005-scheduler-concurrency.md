# ADR-0005: Scheduler Concurrency Model

## Status

**Accepted** — Sprint 1.2

## Context

The ARIA scheduler must support concurrent execution across multiple scheduler
instances (for HA/fault tolerance) while ensuring that:

1. No task is processed by more than one scheduler at a time
2. Tasks that crash mid-execution are recovered and retried
3. Lease ownership is clearly established and recoverable

The alternative approaches considered:

- **Optimistic locking with version columns**: Requires conflict detection and retry logic
- **Pessimistic locking with `SELECT FOR UPDATE`**: Not supported by SQLite
- **External coordination via Redis/zookeeper**: Adds infrastructure complexity
- **Single-instance scheduler**: Single point of failure, no HA

## Decision

We implement **lease-based concurrency** with two additional columns on the `tasks` table:

```sql
ALTER TABLE tasks ADD COLUMN lease_owner TEXT;        -- NULL = unleased
ALTER TABLE tasks ADD COLUMN lease_expires_at INTEGER; -- epoch ms
CREATE INDEX idx_tasks_lease ON tasks(lease_owner, lease_expires_at);
```

### Lease Semantics

1. **Acquisition**: When a scheduler picks up tasks via `acquire_due()`, it atomically
   assigns `lease_owner = worker_id` and `lease_expires_at = now + TTL`

2. **TTL**: Default lease TTL is 300 seconds (5 minutes). Schedulers should refresh
   leases via heartbeat while executing long tasks.

3. **Expiration**: If `lease_expires_at < now()` and `lease_owner = worker_id`,
   the task is considered abandoned and can be re-claimed by any scheduler.

4. **Release**: Upon task completion (success/failure), the scheduler explicitly
   releases the lease by setting `lease_owner = NULL, lease_expires_at = NULL`.

5. **Reaper**: A background process (`reaper.py`) runs every 30s and releases
   expired leases: `WHERE lease_owner IS NOT NULL AND lease_expires_at < now()`.

### Worker ID Format

Each scheduler instance generates a unique worker ID at startup:

```
scheduler-{pid}-{8-char-random-hex}
```

Example: `scheduler-12345-a1b2c3d4`

### Single-Writer Invariant

A task can only have **one** active runner at any time. This is enforced by the
atomic UPDATE in `acquire_due()`:

```sql
UPDATE tasks
SET lease_owner = ?, lease_expires_at = ?
WHERE id IN (
    SELECT id FROM tasks
    WHERE status = 'active'
      AND next_run_at <= ?
      AND (lease_owner IS NULL OR lease_expires_at < ?)
    ORDER BY next_run_at
    LIMIT ?
)
```

Only tasks that are either un-leased or have expired leases are claimed.

### Lease Refresh (Heartbeat)

Long-running tasks must refresh their lease before expiration. The recommended
pattern:

```python
async def heartbeat_task(task_id: str, worker_id: str, interval: int = 60):
    """Refresh lease every `interval` seconds."""
    while True:
        await asyncio.sleep(interval)
        now = int(time.time() * 1000)
        await store.update_task(
            task_id,
            lease_expires_at=now + (300 * 1000),
            updated_at=now
        )
```

### Recovery at Startup

On scheduler startup, the reaper should immediately release any stale leases
from crashed instances before the main loop starts.

## Consequences

### Positive

- **No external coordination**: Works with SQLite only
- **Fault tolerance**: Crashed schedulers leave recoverable leases
- **HA-ready**: Multiple schedulers can coexist safely
- **Simple implementation**: Single UPDATE statement per acquisition cycle

### Negative

- **Clock dependency**: Reaper relies on monotonic time; clock skew can cause
  premature lease expiration
- **Not a distributed lock**: Two schedulers with synchronized clocks could
  theoretically claim the same task (mitigated by atomic UPDATE)
- **Lease TTL tuning**: 300s may be too short for very long tasks

### Mitigations

1. Clock skew: Use `time.monotonic()` internally, not wall-clock time
2. Long tasks: Refresh lease well before TTL expires (every 60s for 300s TTL)
3. Crash detection: Reaper runs frequently (30s) to reclaim abandoned leases

## References

- Blueprint §6.1 — Task store schema
- Blueprint §6.5 — DLQ and retry
- Sprint 1.2 plan — W1.2.A TaskStore implementation