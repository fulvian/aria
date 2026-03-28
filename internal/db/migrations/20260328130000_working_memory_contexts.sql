-- +goose Up
-- +goose StatementBegin

CREATE TABLE IF NOT EXISTS working_memory_contexts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    context_json TEXT NOT NULL, -- JSON serialized Context
    version INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    expires_at INTEGER, -- TTL expiration timestamp
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wmc_session_id ON working_memory_contexts (session_id);
CREATE INDEX IF NOT EXISTS idx_wmc_expires_at ON working_memory_contexts (expires_at);

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
DROP TABLE IF EXISTS working_memory_contexts;
-- +goose StatementEnd
