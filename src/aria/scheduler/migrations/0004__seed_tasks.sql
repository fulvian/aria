-- Seed tasks for Sprint 1.4 (Workspace-Agent + E2E MVP)
-- Per blueprint §6.2 and sprint plan W1.4.H

-- Task 1: Daily email triage (08:00 every day)
INSERT OR IGNORE INTO tasks (
    id, name, category, trigger_type, trigger_config,
    schedule_cron, timezone, next_run_at, status, policy,
    budget_tokens, budget_cost_eur, max_retries, retry_count,
    last_error, owner_user_id, payload,
    lease_owner, lease_expires_at, created_at, updated_at
) VALUES (
    'seed-daily-email-triage',
    'daily-email-triage',
    'workspace',
    'cron',
    '{"cron": "0 8 * * *", "timezone": "Europe/Rome"}',
    '0 8 * * *',
    'Europe/Rome',
    NULL,
    'active',
    'allow',
    30000,
    0.05,
    3,
    0,
    NULL,
    NULL,
    '{"sub_agent": "workspace-agent", "skill": "triage-email", "trace_prefix": "daily-triage"}',
    NULL,
    NULL,
    :now_ms,
    :now_ms
);

-- Task 2: Weekly backup (03:00 every Sunday)
INSERT OR IGNORE INTO tasks (
    id, name, category, trigger_type, trigger_config,
    schedule_cron, timezone, next_run_at, status, policy,
    budget_tokens, budget_cost_eur, max_retries, retry_count,
    last_error, owner_user_id, payload,
    lease_owner, lease_expires_at, created_at, updated_at
) VALUES (
    'seed-weekly-backup',
    'weekly-backup',
    'system',
    'cron',
    '{"cron": "0 3 * * 0", "timezone": "Europe/Rome"}',
    '0 3 * * 0',
    'Europe/Rome',
    NULL,
    'active',
    'allow',
    5000,
    0.01,
    3,
    0,
    NULL,
    NULL,
    '{"command": "scripts/backup.sh"}',
    NULL,
    NULL,
    :now_ms,
    :now_ms
);

-- Task 3: Blueprint-keeper stub (policy deny until Phase 2)
INSERT OR IGNORE INTO tasks (
    id, name, category, trigger_type, trigger_config,
    schedule_cron, timezone, next_run_at, status, policy,
    budget_tokens, budget_cost_eur, max_retries, retry_count,
    last_error, owner_user_id, payload,
    lease_owner, lease_expires_at, created_at, updated_at
) VALUES (
    'seed-blueprint-review',
    'blueprint-review',
    'system',
    'cron',
    '{"cron": "0 10 * * 0", "timezone": "Europe/Rome"}',
    '0 10 * * 0',
    'Europe/Rome',
    NULL,
    'active',
    'deny',
    20000,
    0.02,
    1,
    0,
    NULL,
    NULL,
    '{"sub_agent": "blueprint-keeper"}',
    NULL,
    NULL,
    :now_ms,
    :now_ms
);
