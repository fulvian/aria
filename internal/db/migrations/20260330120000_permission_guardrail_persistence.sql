-- +goose Up
-- +goose StatementBegin

-- Permission rules (persistent permission grants)
CREATE TABLE IF NOT EXISTS permission_rules (
    id TEXT PRIMARY KEY,
    agency_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_pattern TEXT NOT NULL,
    level TEXT NOT NULL,
    scope TEXT NOT NULL,
    expires_at INTEGER,
    created_at INTEGER NOT NULL,
    created_by TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_permission_rules_agency_id ON permission_rules (agency_id);
CREATE INDEX IF NOT EXISTS idx_permission_rules_action ON permission_rules (action);
CREATE INDEX IF NOT EXISTS idx_permission_rules_expires_at ON permission_rules (expires_at);

-- Permission requests (audit trail)
CREATE TABLE IF NOT EXISTS permission_requests (
    id TEXT PRIMARY KEY,
    agency_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    requested_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_permission_requests_agency_id ON permission_requests (agency_id);
CREATE INDEX IF NOT EXISTS idx_permission_requests_agent_id ON permission_requests (agent_id);
CREATE INDEX IF NOT EXISTS idx_permission_requests_requested_at ON permission_requests (requested_at);

-- Permission responses (audit trail)
CREATE TABLE IF NOT EXISTS permission_responses (
    request_id TEXT PRIMARY KEY,
    granted INTEGER NOT NULL,
    level TEXT NOT NULL,
    scope TEXT NOT NULL,
    reason TEXT,
    responded_at INTEGER NOT NULL,
    expires_at INTEGER,
    FOREIGN KEY (request_id) REFERENCES permission_requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_permission_responses_responded_at ON permission_responses (responded_at);

-- Guardrail budgets (action budgets per type)
CREATE TABLE IF NOT EXISTS guardrail_budgets (
    action_type TEXT PRIMARY KEY,
    budget_limit INTEGER NOT NULL,
    used_count INTEGER NOT NULL DEFAULT 0,
    window_hours INTEGER NOT NULL,
    reset_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_guardrail_budgets_reset_at ON guardrail_budgets (reset_at);

-- Guardrail preferences (user preferences)
CREATE TABLE IF NOT EXISTS guardrail_preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1), -- Single row table
    allowed_actions TEXT, -- JSON array
    forbidden_actions TEXT, -- JSON array
    notification_level TEXT NOT NULL,
    notify_channels TEXT, -- JSON array
    max_daily_actions INTEGER NOT NULL,
    max_pending_suggestions INTEGER NOT NULL,
    auto_approve_rules TEXT, -- JSON array
    quiet_hours TEXT, -- JSON array
    active_hours TEXT, -- JSON array
    updated_at INTEGER NOT NULL
);

-- Guardrail audit log
CREATE TABLE IF NOT EXISTS guardrail_audit (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    action_details TEXT, -- JSON
    result TEXT NOT NULL,
    reason TEXT,
    timestamp INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_guardrail_audit_action_type ON guardrail_audit (action_type);
CREATE INDEX IF NOT EXISTS idx_guardrail_audit_timestamp ON guardrail_audit (timestamp);

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

DROP TABLE IF EXISTS guardrail_audit;
DROP TABLE IF EXISTS guardrail_preferences;
DROP TABLE IF EXISTS guardrail_budgets;
DROP TABLE IF EXISTS permission_responses;
DROP TABLE IF EXISTS permission_requests;
DROP TABLE IF EXISTS permission_rules;

-- +goose StatementEnd
