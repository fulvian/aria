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
