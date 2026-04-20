-- Migration 0002: Add episodic_tombstones table
-- Per blueprint P6 - soft delete for verbatim preservation

CREATE TABLE IF NOT EXISTS episodic_tombstones (
    episodic_id TEXT PRIMARY KEY,
    tombstoned_at INTEGER NOT NULL,
    reason TEXT NOT NULL,
    actor_user_id TEXT
);
