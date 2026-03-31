-- +goose Up
-- +goose StatementBegin

-- Episode embeddings table for storing vector representations of episodes
CREATE TABLE IF NOT EXISTS episode_embeddings (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    vector BLOB NOT NULL,  -- Stored as binary blob (float32 serialization)
    text_hash TEXT NOT NULL,  -- SHA256 hash of the embedded text for deduplication
    text_preview TEXT NOT NULL,  -- First 500 chars of text for debugging/display
    created_at INTEGER NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_episode_embeddings_episode_id ON episode_embeddings (episode_id);
CREATE INDEX IF NOT EXISTS idx_episode_embeddings_text_hash ON episode_embeddings (text_hash);

-- Facts embeddings table for semantic memory
CREATE TABLE IF NOT EXISTS fact_embeddings (
    id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    vector BLOB NOT NULL,
    text_hash TEXT NOT NULL,
    text_preview TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (fact_id) REFERENCES facts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fact_embeddings_fact_id ON fact_embeddings (fact_id);
CREATE INDEX IF NOT EXISTS idx_fact_embeddings_text_hash ON fact_embeddings (text_hash);

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

DROP TABLE IF EXISTS fact_embeddings;
DROP TABLE IF EXISTS episode_embeddings;

-- +goose StatementEnd