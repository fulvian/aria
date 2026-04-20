-- ARIA SQLite Schema
-- Complete schema for all ARIA SQLite databases
-- Generated from: docs/foundation/aria_foundation_blueprint.md §5, §6, §7
-- SQLite version floor: >= 3.51.3 (WAL mode required)
--
-- Databases:
--   - episodic.db (memory): Tier 0 raw + FTS5
--   - scheduler.db: tasks, task_runs, dlq, hitl_pending
--   - sessions.db (gateway): gateway_sessions

-- ============================================================
-- MEMORY DATABASE (episodic.db)
-- ============================================================

PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA wal_autocheckpoint=1000;
PRAGMA foreign_keys=ON;

-- Tier 0: Raw episodic memory (verbatim preservation)
CREATE TABLE IF NOT EXISTS episodic (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    actor TEXT NOT NULL CHECK (actor IN ('user_input', 'tool_output', 'agent_inference', 'system_event')),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    tags TEXT DEFAULT '[]',  -- JSON array
    meta TEXT DEFAULT '{}',  -- JSON object
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_episodic_session ON episodic(session_id);
CREATE INDEX IF NOT EXISTS idx_episodic_ts ON episodic(ts);
CREATE INDEX IF NOT EXISTS idx_episodic_actor ON episodic(actor);

-- Tier 1: Semantic chunks (FTS5)
-- Note: FTS5 virtual tables don't support CHECK constraints;
-- validation is done at the application level
CREATE VIRTUAL TABLE IF NOT EXISTS semantic USING fts5(
    id,
    source_episodic_ids,  -- JSON array of UUID strings
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

CREATE TABLE IF NOT EXISTS semantic_chunks (
    id TEXT PRIMARY KEY,
    source_episodic_ids TEXT NOT NULL,  -- JSON array
    actor TEXT NOT NULL CHECK (actor IN ('user_input', 'tool_output', 'agent_inference', 'system_event')),
    kind TEXT NOT NULL CHECK (kind IN ('fact', 'preference', 'decision', 'action_item', 'concept')),
    text TEXT NOT NULL,
    keywords TEXT DEFAULT '[]',  -- JSON array
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

-- Skills registry (procedural memory)
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    trigger_keywords TEXT DEFAULT '[]',  -- JSON array
    allowed_tools TEXT DEFAULT '[]',  -- JSON array
    version TEXT DEFAULT '1.0.0',
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- Review queue for agent inferences
CREATE TABLE IF NOT EXISTS review_queue (
    id TEXT PRIMARY KEY,
    episodic_ids TEXT NOT NULL,  -- JSON array
    actor TEXT NOT NULL,
    text TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    resolved_at INTEGER
);

-- ============================================================
-- SCHEDULER DATABASE (scheduler.db)
-- ============================================================

PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('search', 'workspace', 'memory', 'custom')),
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('cron', 'event', 'webhook', 'oneshot', 'manual')),
    trigger_config TEXT NOT NULL DEFAULT '{}',  -- JSON
    schedule_cron TEXT,
    timezone TEXT DEFAULT 'Europe/Rome',
    next_run_at INTEGER,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'dlq', 'completed', 'failed')),
    policy TEXT NOT NULL DEFAULT 'allow' CHECK (policy IN ('allow', 'ask', 'deny')),
    budget_tokens INTEGER,
    budget_cost_eur REAL,
    max_retries INTEGER DEFAULT 3,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    owner_user_id TEXT,
    payload TEXT NOT NULL DEFAULT '{}',  -- JSON: prompt, sub_agent, tools_scoped
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_next_run ON tasks(next_run_at) WHERE status='active';
CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

CREATE TABLE IF NOT EXISTS task_runs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    started_at INTEGER NOT NULL,
    finished_at INTEGER,
    outcome TEXT NOT NULL CHECK (outcome IN ('success', 'failed', 'blocked_budget', 'blocked_policy', 'timeout')),
    tokens_used INTEGER,
    cost_eur REAL,
    result_summary TEXT,
    logs_path TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_runs_task ON task_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_runs_started ON task_runs(started_at);

CREATE TABLE IF NOT EXISTS dlq (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    last_run_id TEXT REFERENCES task_runs(id),
    moved_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    reason TEXT NOT NULL,
    payload_snapshot TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hitl_pending (
    id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
    run_id TEXT REFERENCES task_runs(id) ON DELETE SET NULL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    expires_at INTEGER NOT NULL,
    question TEXT NOT NULL,
    options_json TEXT,  -- JSON array of choices
    channel TEXT NOT NULL CHECK (channel IN ('telegram', 'cli')),
    user_response TEXT,
    resolved_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_hitl_expires ON hitl_pending(expires_at) WHERE resolved_at IS NULL;

-- ============================================================
-- GATEWAY DATABASE (sessions.db)
-- ============================================================

PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS gateway_sessions (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL CHECK (channel IN ('telegram', 'slack', 'whatsapp', 'discord')),
    external_user_id TEXT NOT NULL,
    aria_session_id TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    last_activity INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    locale TEXT DEFAULT 'it-IT',
    state_json TEXT DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_gateway_session ON gateway_sessions(channel, external_user_id);
CREATE INDEX IF NOT EXISTS idx_gateway_external ON gateway_sessions(external_user_id);
CREATE INDEX IF NOT EXISTS idx_gateway_activity ON gateway_sessions(last_activity);

-- ============================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================

-- Auto-update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS tasks_updated_at
AFTER UPDATE ON tasks
BEGIN
    UPDATE tasks SET updated_at = strftime('%s', 'now') WHERE id = NEW.id;
END;

-- Clean up old WAL checkpoint (manual checkpoint every 6h recommended)
-- PRAGMA wal_checkpoint(TRUNCATE);
