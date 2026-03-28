-- name: CreateProcedure :one
INSERT INTO procedures (
    id,
    name,
    description,
    trigger_type,
    trigger_pattern,
    steps,
    success_rate,
    use_count,
    created_at,
    updated_at
) VALUES (
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    0.0,
    0,
    strftime('%s', 'now'),
    strftime('%s', 'now')
) RETURNING *;

-- name: GetProcedureByID :one
SELECT *
FROM procedures
WHERE id = ? LIMIT 1;

-- name: GetProcedureByName :one
SELECT *
FROM procedures
WHERE name = ? LIMIT 1;

-- name: ListProcedures :many
SELECT *
FROM procedures
ORDER BY use_count DESC, name ASC;

-- name: ListProceduresByTrigger :many
SELECT *
FROM procedures
WHERE trigger_type = ?
ORDER BY success_rate DESC, use_count DESC;

-- name: UpdateProcedureStats :exec
UPDATE procedures
SET success_rate = ?,
    use_count = use_count + 1,
    updated_at = strftime('%s', 'now')
WHERE id = ?;

-- name: DeleteProcedure :exec
DELETE FROM procedures
WHERE id = ?;

-- name: SearchProcedures :many
SELECT *
FROM procedures
WHERE name LIKE '%' || ? || '%'
   OR description LIKE '%' || ? || '%'
ORDER BY success_rate DESC;
