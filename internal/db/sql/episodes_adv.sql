-- name: SearchEpisodesFull :many
-- Advanced episode search with all filters
SELECT * FROM episodes
WHERE
    (session_id = ? OR ? = '')
    AND (agency_id = ? OR ? = '')
    AND (agent_id = ? OR ? = '')
    AND (task LIKE '%' || ? || '%' OR ? = '')
    AND (created_at >= ? OR ? = 0)
    AND (created_at <= ? OR ? = 0)
ORDER BY
    CASE outcome
        WHEN 'success' THEN 1
        WHEN 'partial' THEN 2
        WHEN 'failure' THEN 3
        ELSE 4
    END,
    created_at DESC
LIMIT ? OFFSET ?;

-- name: SearchEpisodesByTimeRange :many
SELECT * FROM episodes
WHERE created_at >= ? AND created_at <= ?
ORDER BY created_at DESC
LIMIT ? OFFSET ?;

-- name: SearchEpisodesByAgent :many
SELECT * FROM episodes
WHERE agent_id = ?
ORDER BY created_at DESC
LIMIT ? OFFSET ?;

-- name: CountEpisodesByOutcome :one
SELECT
    outcome,
    COUNT(*) as count
FROM episodes
WHERE created_at >= ? AND created_at <= ?
GROUP BY outcome;
