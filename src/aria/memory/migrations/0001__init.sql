-- Migration 0001: Initialize memory schema
-- Creates base episodic and semantic tables
-- Note: PRAGMAs are applied in connect() before migrations run,
-- so they are NOT included here to avoid transaction conflicts.

-- Tier 0: Raw episodic memory (verbatim preservation)
CREATE TABLE IF NOT EXISTS episodic (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    actor TEXT NOT NULL CHECK (actor IN ('user_input', 'tool_output', 'agent_inference', 'system_event')),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    tags TEXT DEFAULT '[]',
    meta TEXT DEFAULT '{}',
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_episodic_session ON episodic(session_id);
CREATE INDEX IF NOT EXISTS idx_episodic_ts ON episodic(ts);
CREATE INDEX IF NOT EXISTS idx_episodic_actor ON episodic(actor);

-- Tier 1 semantic chunks + FTS5 index table
CREATE TABLE IF NOT EXISTS semantic_chunks (
    id TEXT PRIMARY KEY,
    source_episodic_ids TEXT NOT NULL,
    actor TEXT NOT NULL CHECK (actor IN ('user_input', 'tool_output', 'agent_inference', 'system_event')),
    kind TEXT NOT NULL CHECK (kind IN ('fact', 'preference', 'decision', 'action_item', 'concept')),
    text TEXT NOT NULL,
    keywords TEXT DEFAULT '[]',
    confidence REAL DEFAULT 1.0,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    occurrences INTEGER DEFAULT 1,
    embedding_id TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_chunks_actor ON semantic_chunks(actor);
CREATE INDEX IF NOT EXISTS idx_chunks_kind ON semantic_chunks(kind);
CREATE INDEX IF NOT EXISTS idx_chunks_first_seen ON semantic_chunks(first_seen);

CREATE VIRTUAL TABLE IF NOT EXISTS semantic USING fts5(
    id,
    source_episodic_ids,
    actor,
    kind,
    text,
    keywords,
    confidence,
    first_seen,
    last_seen,
    occurrences,
    embedding_id,
    content='semantic_chunks',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS semantic_fts_insert AFTER INSERT ON semantic_chunks BEGIN
    INSERT INTO semantic(rowid, id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id)
    VALUES (NEW.rowid, NEW.id, NEW.source_episodic_ids, NEW.actor, NEW.kind, NEW.text, NEW.keywords, NEW.confidence, NEW.first_seen, NEW.last_seen, NEW.occurrences, NEW.embedding_id);
END;

CREATE TRIGGER IF NOT EXISTS semantic_fts_delete AFTER DELETE ON semantic_chunks BEGIN
    INSERT INTO semantic(semantic, rowid, id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id)
    VALUES ('delete', OLD.rowid, OLD.id, OLD.source_episodic_ids, OLD.actor, OLD.kind, OLD.text, OLD.keywords, OLD.confidence, OLD.first_seen, OLD.last_seen, OLD.occurrences, OLD.embedding_id);
END;

CREATE TRIGGER IF NOT EXISTS semantic_fts_update AFTER UPDATE ON semantic_chunks BEGIN
    INSERT INTO semantic(semantic, rowid, id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id)
    VALUES ('delete', OLD.rowid, OLD.id, OLD.source_episodic_ids, OLD.actor, OLD.kind, OLD.text, OLD.keywords, OLD.confidence, OLD.first_seen, OLD.last_seen, OLD.occurrences, OLD.embedding_id);
    INSERT INTO semantic(rowid, id, source_episodic_ids, actor, kind, text, keywords, confidence, first_seen, last_seen, occurrences, embedding_id)
    VALUES (NEW.rowid, NEW.id, NEW.source_episodic_ids, NEW.actor, NEW.kind, NEW.text, NEW.keywords, NEW.confidence, NEW.first_seen, NEW.last_seen, NEW.occurrences, NEW.embedding_id);
END;

-- FTS5 virtual table for full-text search on episodic content
CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts USING fts5(
    content,
    actor,
    session_id,
    content='episodic',
    content_rowid='rowid'
);

-- Triggers to keep episodic_fts in sync with episodic table
-- (Note: These require SQLite 3.51.3+ per MIN_SQLITE_VERSION)
CREATE TRIGGER IF NOT EXISTS episodic_fts_insert AFTER INSERT ON episodic BEGIN
    INSERT INTO episodic_fts(rowid, content, actor, session_id)
    VALUES (NEW.rowid, NEW.content, NEW.actor, NEW.session_id);
END;

CREATE TRIGGER IF NOT EXISTS episodic_fts_delete AFTER DELETE ON episodic BEGIN
    INSERT INTO episodic_fts(episodic_fts, rowid, content, actor, session_id)
    VALUES ('delete', OLD.rowid, OLD.content, OLD.actor, OLD.session_id);
END;

CREATE TRIGGER IF NOT EXISTS episodic_fts_update AFTER UPDATE ON episodic BEGIN
    INSERT INTO episodic_fts(episodic_fts, rowid, content, actor, session_id)
    VALUES ('delete', OLD.rowid, OLD.content, OLD.actor, OLD.session_id);
    INSERT INTO episodic_fts(rowid, content, actor, session_id)
    VALUES (NEW.rowid, NEW.content, NEW.actor, NEW.session_id);
END;

-- Schema migrations tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL,
    checksum TEXT NOT NULL
);
