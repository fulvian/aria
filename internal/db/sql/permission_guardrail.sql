-- Permission Rules queries

-- name: CreatePermissionRule :one
INSERT INTO permission_rules (
    id,
    agency_id,
    action,
    resource_type,
    resource_pattern,
    level,
    scope,
    expires_at,
    created_at,
    created_by
) VALUES (
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    strftime('%s', 'now'),
    ?
) RETURNING *;

-- name: GetPermissionRuleByID :one
SELECT *
FROM permission_rules
WHERE id = ? LIMIT 1;

-- name: ListPermissionRulesByAgency :many
SELECT *
FROM permission_rules
WHERE agency_id = ?
ORDER BY created_at DESC;

-- name: DeletePermissionRule :exec
DELETE FROM permission_rules
WHERE id = ?;

-- name: DeleteExpiredPermissionRules :exec
DELETE FROM permission_rules
WHERE expires_at IS NOT NULL AND expires_at < strftime('%s', 'now');

-- Permission Requests queries

-- name: CreatePermissionRequest :one
INSERT INTO permission_requests (
    id,
    agency_id,
    agent_id,
    action,
    resource,
    requested_at
) VALUES (
    ?,
    ?,
    ?,
    ?,
    ?,
    strftime('%s', 'now')
) RETURNING *;

-- name: GetPermissionRequestByID :one
SELECT *
FROM permission_requests
WHERE id = ? LIMIT 1;

-- name: ListPermissionRequestsByAgency :many
SELECT *
FROM permission_requests
WHERE agency_id = ?
ORDER BY requested_at DESC
LIMIT ? OFFSET ?;

-- name: ListPermissionRequestsByAgent :many
SELECT *
FROM permission_requests
WHERE agent_id = ?
ORDER BY requested_at DESC
LIMIT ? OFFSET ?;

-- name: DeleteOldPermissionRequests :exec
DELETE FROM permission_requests
WHERE requested_at < strftime('%s', 'now', '-' || ? || ' seconds');

-- Permission Responses queries

-- name: CreatePermissionResponse :one
INSERT INTO permission_responses (
    request_id,
    granted,
    level,
    scope,
    reason,
    responded_at,
    expires_at
) VALUES (
    ?,
    ?,
    ?,
    ?,
    ?,
    strftime('%s', 'now'),
    ?
) RETURNING *;

-- name: GetPermissionResponseByRequestID :one
SELECT *
FROM permission_responses
WHERE request_id = ? LIMIT 1;

-- Guardrail Budgets queries

-- name: UpsertGuardrailBudget :one
INSERT INTO guardrail_budgets (
    action_type,
    budget_limit,
    used_count,
    window_hours,
    reset_at
) VALUES (
    ?,
    ?,
    COALESCE(?, 0),
    ?,
    ?
) ON CONFLICT(action_type) DO UPDATE SET
    budget_limit = excluded.budget_limit,
    used_count = excluded.used_count,
    window_hours = excluded.window_hours,
    reset_at = excluded.reset_at
RETURNING *;

-- name: GetGuardrailBudget :one
SELECT *
FROM guardrail_budgets
WHERE action_type = ? LIMIT 1;

-- name: ListGuardrailBudgets :many
SELECT *
FROM guardrail_budgets;

-- name: UpdateGuardrailBudgetUsed :exec
UPDATE guardrail_budgets
SET used_count = used_count + ?
WHERE action_type = ?;

-- name: ResetGuardrailBudgets :exec
UPDATE guardrail_budgets
SET used_count = 0,
    reset_at = ?
WHERE reset_at < strftime('%s', 'now');

-- Guardrail Preferences queries

-- name: UpsertGuardrailPreferences :one
INSERT INTO guardrail_preferences (
    id,
    allowed_actions,
    forbidden_actions,
    notification_level,
    notify_channels,
    max_daily_actions,
    max_pending_suggestions,
    auto_approve_rules,
    quiet_hours,
    active_hours,
    updated_at
) VALUES (
    1,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    strftime('%s', 'now')
) ON CONFLICT(id) DO UPDATE SET
    allowed_actions = excluded.allowed_actions,
    forbidden_actions = excluded.forbidden_actions,
    notification_level = excluded.notification_level,
    notify_channels = excluded.notify_channels,
    max_daily_actions = excluded.max_daily_actions,
    max_pending_suggestions = excluded.max_pending_suggestions,
    auto_approve_rules = excluded.auto_approve_rules,
    quiet_hours = excluded.quiet_hours,
    active_hours = excluded.active_hours,
    updated_at = excluded.updated_at
RETURNING *;

-- name: GetGuardrailPreferences :one
SELECT *
FROM guardrail_preferences
WHERE id = 1 LIMIT 1;

-- Guardrail Audit queries

-- name: CreateGuardrailAuditEntry :one
INSERT INTO guardrail_audit (
    id,
    action_type,
    action_details,
    result,
    reason,
    timestamp
) VALUES (
    ?,
    ?,
    ?,
    ?,
    ?,
    strftime('%s', 'now')
) RETURNING *;

-- name: ListGuardrailAuditByType :many
SELECT *
FROM guardrail_audit
WHERE action_type = ?
ORDER BY timestamp DESC
LIMIT ? OFFSET ?;

-- name: ListGuardrailAuditByTimeRange :many
SELECT *
FROM guardrail_audit
WHERE timestamp >= ? AND timestamp <= ?
ORDER BY timestamp DESC
LIMIT ? OFFSET ?;

-- name: DeleteOldGuardrailAudit :exec
DELETE FROM guardrail_audit
WHERE timestamp < strftime('%s', 'now', '-' || ? || ' seconds');
