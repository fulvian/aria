-- name: CreateTask :one
INSERT INTO tasks (
    id,
    name,
    description,
    type,
    priority,
    scheduled_at,
    deadline,
    schedule_expr,
    agency,
    agent,
    skills,
    parameters,
    status,
    progress,
    created_at
) VALUES (
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    'created',
    0.0,
    strftime('%s', 'now')
) RETURNING *;

-- name: GetTaskByID :one
SELECT *
FROM tasks
WHERE id = ? LIMIT 1;

-- name: ListTasks :many
SELECT *
FROM tasks
ORDER BY priority DESC, created_at ASC
LIMIT ? OFFSET ?;

-- name: ListTasksByStatus :many
SELECT *
FROM tasks
WHERE status = ?
ORDER BY priority DESC, created_at ASC
LIMIT ? OFFSET ?;

-- name: ListTasksByAgency :many
SELECT *
FROM tasks
WHERE agency = ?
ORDER BY priority DESC, created_at ASC
LIMIT ? OFFSET ?;

-- name: UpdateTaskStatus :exec
UPDATE tasks
SET status = ?,
    started_at = CASE WHEN ? = 'running' AND started_at IS NULL THEN strftime('%s', 'now') ELSE started_at END,
    completed_at = CASE WHEN ? = 'completed' OR ? = 'failed' OR ? = 'cancelled' THEN strftime('%s', 'now') ELSE completed_at END,
    progress = ?,
    result = ?,
    error = ?
WHERE id = ?;

-- name: UpdateTaskProgress :exec
UPDATE tasks
SET progress = ?
WHERE id = ?;

-- name: CancelTask :exec
UPDATE tasks
SET status = 'cancelled',
    completed_at = strftime('%s', 'now')
WHERE id = ?;

-- name: DeleteTask :exec
DELETE FROM tasks
WHERE id = ?;

-- name: AddTaskDependency :exec
INSERT INTO task_dependencies (task_id, depends_on)
VALUES (?, ?)
ON CONFLICT DO NOTHING;

-- name: RemoveTaskDependency :exec
DELETE FROM task_dependencies
WHERE task_id = ? AND depends_on = ?;

-- name: GetTaskDependencies :many
SELECT t.*
FROM tasks t
INNER JOIN task_dependencies td ON t.id = td.depends_on
WHERE td.task_id = ?;

-- name: GetDependentTasks :many
SELECT t.*
FROM tasks t
INNER JOIN task_dependencies td ON t.id = td.task_id
WHERE td.depends_on = ?;

-- name: ListPendingTasks :many
SELECT *
FROM tasks
WHERE status IN (?, ?)
  AND (scheduled_at IS NULL OR scheduled_at <= ?)
ORDER BY priority DESC, created_at ASC
LIMIT 100;

-- name: CountTasksByStatus :one
SELECT COUNT(*)
FROM tasks
WHERE status = ?;
