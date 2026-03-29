-- name: CreateAgency :one
INSERT INTO agencies (
    id,
    name,
    domain,
    description,
    status,
    created_at,
    updated_at
) VALUES (
    ?,
    ?,
    ?,
    ?,
    ?,
    strftime('%s', 'now'),
    strftime('%s', 'now')
) RETURNING *;

-- name: GetAgencyByID :one
SELECT *
FROM agencies
WHERE id = ? LIMIT 1;

-- name: GetAgencyByName :one
SELECT *
FROM agencies
WHERE name = ? LIMIT 1;

-- name: ListAgencies :many
SELECT *
FROM agencies
ORDER BY name ASC;

-- name: ListAgenciesByStatus :many
SELECT *
FROM agencies
WHERE status = ?
ORDER BY name ASC;

-- name: UpdateAgencyStatus :exec
UPDATE agencies
SET status = ?, updated_at = strftime('%s', 'now')
WHERE id = ?;

-- name: DeleteAgency :exec
DELETE FROM agencies
WHERE id = ?;

-- name: UpsertAgencyState :one
INSERT INTO agency_states (
    id,
    agency_id,
    status,
    last_task_id,
    metrics,
    updated_at
) VALUES (
    ?,
    ?,
    ?,
    ?,
    ?,
    strftime('%s', 'now')
) ON CONFLICT (id) DO UPDATE SET
    status = excluded.status,
    last_task_id = excluded.last_task_id,
    metrics = excluded.metrics,
    updated_at = strftime('%s', 'now')
RETURNING *;

-- name: GetAgencyState :one
SELECT *
FROM agency_states
WHERE agency_id = ? LIMIT 1;

-- name: DeleteAgencyState :exec
DELETE FROM agency_states
WHERE agency_id = ?;
