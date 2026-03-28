-- +goose Up
-- +goose StatementBegin

-- Agencies table
CREATE TABLE IF NOT EXISTS agencies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agencies_name ON agencies (name);
CREATE INDEX IF NOT EXISTS idx_agencies_status ON agencies (status);

-- Agency states (for persistence)
CREATE TABLE IF NOT EXISTS agency_states (
    id TEXT PRIMARY KEY,
    agency_id TEXT NOT NULL,
    status TEXT NOT NULL,
    last_task_id TEXT,
    metrics TEXT, -- JSON object
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (agency_id) REFERENCES agencies (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agency_states_agency_id ON agency_states (agency_id);

-- Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL DEFAULT 'immediate',
    priority INTEGER NOT NULL DEFAULT 50,
    
    scheduled_at INTEGER,
    deadline INTEGER,
    schedule_expr TEXT,
    
    agency TEXT,
    agent TEXT,
    skills TEXT, -- JSON array
    parameters TEXT, -- JSON object
    
    status TEXT NOT NULL DEFAULT 'created',
    progress REAL NOT NULL DEFAULT 0.0,
    
    created_at INTEGER NOT NULL,
    started_at INTEGER,
    completed_at INTEGER,
    
    result TEXT, -- JSON
    error TEXT   -- JSON
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_agency ON tasks (agency);
CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_at ON tasks (scheduled_at);

-- Task dependencies
CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id TEXT NOT NULL,
    depends_on TEXT NOT NULL,
    PRIMARY KEY (task_id, depends_on),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_dependencies_task_id ON task_dependencies (task_id);
CREATE INDEX IF NOT EXISTS idx_task_dependencies_depends_on ON task_dependencies (depends_on);

-- Task events (audit trail)
CREATE TABLE IF NOT EXISTS task_events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT, -- JSON
    created_at INTEGER NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_events_task_id ON task_events (task_id);
CREATE INDEX IF NOT EXISTS idx_task_events_created_at ON task_events (created_at);

-- Episodes (episodic memory)
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    agency_id TEXT,
    agent_id TEXT,
    task TEXT, -- JSON
    actions TEXT, -- JSON array
    outcome TEXT,
    feedback TEXT, -- JSON
    embedding_id TEXT, -- Reference to vector storage
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_episodes_session_id ON episodes (session_id);
CREATE INDEX IF NOT EXISTS idx_episodes_agency_id ON episodes (agency_id);
CREATE INDEX IF NOT EXISTS idx_episodes_created_at ON episodes (created_at);

-- Facts (semantic memory)
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    category TEXT,
    content TEXT NOT NULL,
    source TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at INTEGER NOT NULL,
    last_used INTEGER,
    use_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_facts_domain ON facts (domain);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts (category);

-- Procedures (procedural memory)
CREATE TABLE IF NOT EXISTS procedures (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    trigger_type TEXT NOT NULL,
    trigger_pattern TEXT,
    steps TEXT NOT NULL, -- JSON array
    success_rate REAL NOT NULL DEFAULT 0.0,
    use_count INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_procedures_name ON procedures (name);
CREATE INDEX IF NOT EXISTS idx_procedures_trigger_type ON procedures (trigger_type);

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

DROP TABLE IF EXISTS procedures;
DROP TABLE IF EXISTS facts;
DROP TABLE IF EXISTS episodes;
DROP TABLE IF EXISTS task_events;
DROP TABLE IF EXISTS task_dependencies;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS agency_states;
DROP TABLE IF EXISTS agencies;

-- +goose StatementEnd
