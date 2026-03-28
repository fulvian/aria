-- name: CreateTaskEvent :one
INSERT INTO task_events (
    id,
    task_id,
    event_type,
    event_data,
    created_at
) VALUES (
    ?,
    ?,
    ?,
    ?,
    strftime('%s', 'now')
) RETURNING *;

-- name: GetTaskEvents :many
SELECT *
FROM task_events
WHERE task_id = ?
ORDER BY created_at ASC;

-- name: GetRecentTaskEvents :many
SELECT *
FROM task_events
ORDER BY created_at DESC
LIMIT ?;
