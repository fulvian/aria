-- name: CreateEpisodeEmbedding :one
INSERT INTO episode_embeddings (
    id,
    episode_id,
    provider,
    model,
    dimensions,
    vector,
    text_hash,
    text_preview,
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
    strftime('%s', 'now')
) RETURNING *;

-- name: GetEpisodeEmbedding :one
SELECT * FROM episode_embeddings
WHERE episode_id = ?
LIMIT 1;

-- name: GetEpisodeEmbeddingByHash :one
SELECT * FROM episode_embeddings
WHERE text_hash = ? AND episode_id = ?
LIMIT 1;

-- name: DeleteEpisodeEmbedding :exec
DELETE FROM episode_embeddings
WHERE episode_id = ?;

-- name: CreateFactEmbedding :one
INSERT INTO fact_embeddings (
    id,
    fact_id,
    provider,
    model,
    dimensions,
    vector,
    text_hash,
    text_preview,
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
    strftime('%s', 'now')
) RETURNING *;

-- name: GetFactEmbedding :one
SELECT * FROM fact_embeddings
WHERE fact_id = ?
LIMIT 1;

-- name: GetFactEmbeddingByHash :one
SELECT * FROM fact_embeddings
WHERE text_hash = ? AND fact_id = ?
LIMIT 1;

-- name: DeleteFactEmbedding :exec
DELETE FROM fact_embeddings
WHERE fact_id = ?;

-- name: ListEpisodeEmbeddings :many
SELECT * FROM episode_embeddings
ORDER BY created_at DESC
LIMIT ? OFFSET ?;

-- name: CountEpisodeEmbeddings :one
SELECT COUNT(*) as count FROM episode_embeddings;

-- name: ListFactEmbeddings :many
SELECT * FROM fact_embeddings
ORDER BY created_at DESC
LIMIT ? OFFSET ?;

-- name: CountFactEmbeddings :one
SELECT COUNT(*) as count FROM fact_embeddings;
