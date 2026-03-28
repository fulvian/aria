-- name: CreateEpisode :one
INSERT INTO episodes (
    id,
    session_id,
    agency_id,
    agent_id,
    task,
    actions,
    outcome,
    feedback,
    embedding_id,
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
    strftime('%s', 'now')
) RETURNING *;

-- name: GetEpisodeByID :one
SELECT *
FROM episodes
WHERE id = ? LIMIT 1;

-- name: ListEpisodes :many
SELECT *
FROM episodes
ORDER BY created_at DESC
LIMIT ? OFFSET ?;

-- name: ListEpisodesBySession :many
SELECT *
FROM episodes
WHERE session_id = ?
ORDER BY created_at DESC
LIMIT ? OFFSET ?;

-- name: ListEpisodesByAgency :many
SELECT *
FROM episodes
WHERE agency_id = ?
ORDER BY created_at DESC
LIMIT ? OFFSET ?;

-- name: SearchEpisodes :many
SELECT *
FROM episodes
WHERE outcome LIKE '%' || ? || '%'
   OR task LIKE '%' || ? || '%'
ORDER BY created_at DESC
LIMIT ?;

-- name: DeleteEpisode :exec
DELETE FROM episodes
WHERE id = ?;

-- name: DeleteOldEpisodes :exec
DELETE FROM episodes
WHERE created_at < ?;
