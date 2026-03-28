-- name: CreateFact :one
INSERT INTO facts (
    id,
    domain,
    category,
    content,
    source,
    confidence,
    created_at,
    use_count
) VALUES (
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    strftime('%s', 'now'),
    0
) RETURNING *;

-- name: GetFactByID :one
SELECT *
FROM facts
WHERE id = ? LIMIT 1;

-- name: ListFactsByDomain :many
SELECT *
FROM facts
WHERE domain = ?
ORDER BY use_count DESC, created_at DESC;

-- name: ListFactsByCategory :many
SELECT *
FROM facts
WHERE category = ?
ORDER BY use_count DESC;

-- name: IncrementFactUsage :exec
UPDATE facts
SET use_count = use_count + 1,
    last_used = strftime('%s', 'now')
WHERE id = ?;

-- name: UpdateFactConfidence :exec
UPDATE facts
SET confidence = ?
WHERE id = ?;

-- name: DeleteFact :exec
DELETE FROM facts
WHERE id = ?;

-- name: SearchFacts :many
SELECT *
FROM facts
WHERE content LIKE '%' || ? || '%'
   OR domain = ?
ORDER BY use_count DESC, confidence DESC
LIMIT ?;
