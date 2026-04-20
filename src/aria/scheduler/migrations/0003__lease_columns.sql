-- Migration 0003: Add lease columns for concurrency control
-- Per ADR-0005: lease-based concurrency with lease_owner/lease_expires_at
-- Enables safe concurrent scheduling across multiple scheduler instances

ALTER TABLE tasks ADD COLUMN lease_owner TEXT;
ALTER TABLE tasks ADD COLUMN lease_expires_at INTEGER;

CREATE INDEX IF NOT EXISTS idx_tasks_lease ON tasks(lease_owner, lease_expires_at);