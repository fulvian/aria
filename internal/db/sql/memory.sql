-- name: SaveWorkingContext :one
INSERT INTO working_memory_contexts (
    id, session_id, context_json, version, created_at, updated_at, expires_at
) VALUES (
    ?, ?, ?, ?, strftime('%s', 'now'), strftime('%s', 'now'), ?
)
ON CONFLICT(session_id) DO UPDATE SET
    context_json = excluded.context_json,
    version = version + 1,
    updated_at = strftime('%s', 'now'),
    expires_at = excluded.expires_at
RETURNING *;

-- name: GetWorkingContext :one
SELECT * FROM working_memory_contexts
WHERE session_id = ? AND (expires_at IS NULL OR expires_at > strftime('%s', 'now'))
LIMIT 1;

-- name: DeleteExpiredContexts :exec
DELETE FROM working_memory_contexts
WHERE expires_at IS NOT NULL AND expires_at < strftime('%s', 'now');

-- name: DeleteWorkingContext :exec
DELETE FROM working_memory_contexts WHERE session_id = ?;
