-- Migration 0003: Add memory HITL pending queue

CREATE TABLE IF NOT EXISTS memory_hitl_pending (
    id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    trace_id TEXT,
    channel TEXT NOT NULL DEFAULT 'cli',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL,
    resolved_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_memory_hitl_pending_status ON memory_hitl_pending(status);
CREATE INDEX IF NOT EXISTS idx_memory_hitl_pending_created ON memory_hitl_pending(created_at);
