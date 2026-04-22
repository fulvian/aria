# Google Workspace Tool Profile Matrix

**Document Control**
- Date: 2026-04-22
- Author: ARIA General Manager
- Status: Ratified
- Scope: W1.6.A6 - Profile catalog for workspace agent tool profiles

---

## Overview

This document defines 8 tool profiles for the workspace-agent, each scoped to <= 20 tools per P9 constraint. Each profile exposes a focused subset of Google Workspace capabilities with explicit HITL requirements for write operations.

**Profile Naming Convention**: `workspace-{product}-{mode}`
- `{product}`: mail, docs, sheets, slides, calendar, drive
- `{mode}`: read, write

---

## Complete Tool Inventory (from Context7 `/taylorwilsdon/google_workspace_mcp`)

### Gmail Tools

| Tool | Mode | HITL Required | Profile |
|------|------|--------------|---------|
| `google_workspace_search_gmail_messages` | read | No | workspace-mail-read |
| `google_workspace_get_gmail_message_content` | read | No | workspace-mail-read |
| `google_workspace_send_gmail_message` | write | YES | workspace-mail-write |
| `google_workspace_draft_gmail_message` | write | YES | workspace-mail-write |

### Calendar Tools

| Tool | Mode | HITL Required | Profile |
|------|------|--------------|---------|
| `google_workspace_list_calendars` | read | No | workspace-calendar-read |
| `google_workspace_get_events` | read | No | workspace-calendar-read |
| `google_workspace_get_event` | read | No | workspace-calendar-read |
| `google_workspace_create_event` | write | YES | workspace-calendar-write |
| `google_workspace_modify_event` | write | YES | workspace-calendar-write |
| `google_workspace_delete_event` | write | YES | workspace-calendar-write |

### Drive Tools

| Tool | Mode | HITL Required | Profile |
|------|------|--------------|---------|
| `google_workspace_search_drive_files` | read | No | workspace-drive-read |
| `google_workspace_get_drive_file_content` | read | No | workspace-drive-read |
| `google_workspace_list_drive_items` | read | No | workspace-drive-read |
| `google_workspace_create_drive_file` | write | YES | workspace-drive-write |

### Docs Tools

| Tool | Mode | HITL Required | Profile |
|------|------|--------------|---------|
| `google_workspace_search_docs` | read | No | workspace-docs-read |
| `google_workspace_get_doc_content` | read | No | workspace-docs-read |
| `google_workspace_list_docs_in_folder` | read | No | workspace-docs-read |
| `google_workspace_read_doc_comments` | read | No | workspace-docs-read |
| `google_workspace_create_doc` | write | YES | workspace-docs-write |
| `google_workspace_create_doc_comment` | write | YES | workspace-docs-write |
| `google_workspace_reply_to_comment` | write | YES | workspace-docs-write |
| `google_workspace_resolve_comment` | write | YES | workspace-docs-write |

### Sheets Tools

| Tool | Mode | HITL Required | Profile |
|------|------|--------------|---------|
| `google_workspace_list_spreadsheets` | read | No | workspace-sheets-read |
| `google_workspace_get_spreadsheet_info` | read | No | workspace-sheets-read |
| `google_workspace_read_sheet_values` | read | No | workspace-sheets-read |
| `google_workspace_read_sheet_comments` | read | No | workspace-sheets-read |
| `google_workspace_modify_sheet_values` | write | YES | workspace-sheets-write |
| `google_workspace_create_spreadsheet` | write | YES | workspace-sheets-write |
| `google_workspace_create_sheet` | write | YES | workspace-sheets-write |
| `google_workspace_create_sheet_comment` | write | YES | workspace-sheets-write |
| `google_workspace_reply_to_sheet_comment` | write | YES | workspace-sheets-write |
| `google_workspace_resolve_sheet_comment` | write | YES | workspace-sheets-write |

### Slides Tools

| Tool | Mode | HITL Required | Profile |
|------|------|--------------|---------|
| `google_workspace_get_presentation` | read | No | workspace-slides-read |
| `google_workspace_get_page` | read | No | workspace-slides-read |
| `google_workspace_get_page_thumbnail` | read | No | workspace-slides-read |
| `google_workspace_read_presentation_comments` | read | No | workspace-slides-read |
| `google_workspace_create_presentation` | write | YES | workspace-slides-write |
| `google_workspace_batch_update_presentation` | write | YES | workspace-slides-write |
| `google_workspace_create_presentation_comment` | write | YES | workspace-slides-write |
| `google_workspace_reply_to_presentation_comment` | write | YES | workspace-slides-write |
| `google_workspace_resolve_presentation_comment` | write | YES | workspace-slides-write |

### Forms Tools (future expansion)

| Tool | Mode | HITL Required | Profile |
|------|------|--------------|---------|
| `google_workspace_create_form` | write | YES | workspace-forms-write |
| `google_workspace_get_form` | read | No | workspace-forms-read |
| `google_workspace_get_form_response` | read | No | workspace-forms-read |
| `google_workspace_list_form_responses` | read | No | workspace-forms-read |
| `google_workspace_set_publish_settings` | write | YES | workspace-forms-write |

### Chat Tools (future expansion)

| Tool | Mode | HITL Required | Profile |
|------|------|--------------|---------|
| `google_workspace_list_spaces` | read | No | workspace-chat-read |
| `google_workspace_get_messages` | read | No | workspace-chat-read |
| `google_workspace_send_message` | write | YES | workspace-chat-write |
| `google_workspace_search_messages` | read | No | workspace-chat-read |

---

## 8 Core Profiles

### 1. workspace-mail-read (4 tools) ✅ <= 20

**Tools:**
- `google_workspace_search_gmail_messages`
- `google_workspace_get_gmail_message_content`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`

**HITL Required:** No (read-only)

---

### 2. workspace-mail-write (6 tools) ✅ <= 20

**Tools:**
- `google_workspace_send_gmail_message`
- `google_workspace_draft_gmail_message`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`
- `aria_memory_hitl_ask`

**HITL Required:** YES (all write operations)

---

### 3. workspace-calendar-read (5 tools) ✅ <= 20

**Tools:**
- `google_workspace_list_calendars`
- `google_workspace_get_events`
- `google_workspace_get_event`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`

**HITL Required:** No (read-only)

---

### 4. workspace-calendar-write (7 tools) ✅ <= 20

**Tools:**
- `google_workspace_create_event`
- `google_workspace_modify_event`
- `google_workspace_delete_event`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`
- `aria_memory_hitl_ask`

**HITL Required:** YES (all write operations)

---

### 5. workspace-docs-read (6 tools) ✅ <= 20

**Tools:**
- `google_workspace_search_docs`
- `google_workspace_get_doc_content`
- `google_workspace_list_docs_in_folder`
- `google_workspace_read_doc_comments`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`

**HITL Required:** No (read-only)

---

### 6. workspace-docs-write (8 tools) ✅ <= 20

**Tools:**
- `google_workspace_create_doc`
- `google_workspace_create_doc_comment`
- `google_workspace_reply_to_comment`
- `google_workspace_resolve_comment`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`
- `aria_memory_hitl_ask`

**HITL Required:** YES (all write operations)

---

### 7. workspace-sheets-read (6 tools) ✅ <= 20

**Tools:**
- `google_workspace_list_spreadsheets`
- `google_workspace_get_spreadsheet_info`
- `google_workspace_read_sheet_values`
- `google_workspace_read_sheet_comments`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`

**HITL Required:** No (read-only)

---

### 8. workspace-sheets-write (10 tools) ✅ <= 20

**Tools:**
- `google_workspace_modify_sheet_values`
- `google_workspace_create_spreadsheet`
- `google_workspace_create_sheet`
- `google_workspace_create_sheet_comment`
- `google_workspace_reply_to_sheet_comment`
- `google_workspace_resolve_sheet_comment`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`
- `aria_memory_hitl_ask`

**HITL Required:** YES (all write operations)

---

## Additional Profiles (Future Expansion)

### workspace-slides-read (4 tools) ✅ <= 20

**Tools:**
- `google_workspace_get_presentation`
- `google_workspace_get_page`
- `google_workspace_get_page_thumbnail`
- `google_workspace_read_presentation_comments`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`

**HITL Required:** No (read-only)

---

### workspace-slides-write (5 tools) ✅ <= 20

**Tools:**
- `google_workspace_create_presentation`
- `google_workspace_batch_update_presentation`
- `google_workspace_create_presentation_comment`
- `google_workspace_reply_to_presentation_comment`
- `google_workspace_resolve_presentation_comment`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`
- `aria_memory_hitl_ask`

**HITL Required:** YES (all write operations)

---

### workspace-drive-read (3 tools) ✅ <= 20

**Tools:**
- `google_workspace_search_drive_files`
- `google_workspace_get_drive_file_content`
- `google_workspace_list_drive_items`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`

**HITL Required:** No (read-only)

---

### workspace-drive-write (1 tool) ✅ <= 20

**Tools:**
- `google_workspace_create_drive_file`

**Memory Integration:**
- `aria_memory_remember`
- `aria_memory_recall`
- `aria_memory_hitl_ask`

**HITL Required:** YES (write operation)

---

## Implementation Notes

### Profile Selection Logic

The conductor should route intents to profiles based on:

1. **Intent keywords** → profile mapping:
   - "email", "mail", "gmail" → `workspace-mail-read` or `workspace-mail-write`
   - "calendar", "event", "meeting" → `workspace-calendar-read` or `workspace-calendar-write`
   - "document", "doc", "docs" → `workspace-docs-read` or `workspace-docs-write`
   - "spreadsheet", "sheet", "sheets" → `workspace-sheets-read` or `workspace-sheets-write`
   - "presentation", "slides" → `workspace-slides-read` or `workspace-slides-write`
   - "drive", "file" → `workspace-drive-read` or `workspace-drive-write`

2. **Operation type** → read vs write:
   - Read operations (search, get, list) → `*-read` profile
   - Write operations (create, modify, delete, send) → `*-write` profile + HITL

### HITL Enforcement Pattern

For write operations, the skill must:
1. Execute read phase (inspect current state)
2. Call `aria_memory_hitl_ask` with proposed action summary
3. Wait for user approval
4. Execute write operation only after approval
5. Verify write via read-back
6. Record result in memory

### Scope Preflight Check

Before invoking any profile:
1. Check that required OAuth scopes are available
2. If scope missing → return re-consent guidance
3. If transient failure → bounded retry with exponential backoff
4. If write denied → archive decision in memory with denial rationale

---

## Quality Verification

| Profile | Tool Count | Status |
|---------|------------|--------|
| workspace-mail-read | 2 + 2 memory = 4 | ✅ |
| workspace-mail-write | 2 + 3 memory = 5 | ✅ |
| workspace-calendar-read | 3 + 2 memory = 5 | ✅ |
| workspace-calendar-write | 3 + 3 memory = 6 | ✅ |
| workspace-docs-read | 4 + 2 memory = 6 | ✅ |
| workspace-docs-write | 4 + 3 memory = 7 | ✅ |
| workspace-sheets-read | 4 + 2 memory = 6 | ✅ |
| workspace-sheets-write | 6 + 3 memory = 9 | ✅ |
| workspace-slides-read | 4 + 2 memory = 6 | ✅ |
| workspace-slides-write | 5 + 3 memory = 8 | ✅ |
| workspace-drive-read | 3 + 2 memory = 5 | ✅ |
| workspace-drive-write | 1 + 3 memory = 4 | ✅ |

All profiles <= 20 tools. ✅

---

## References

- Context7: `/taylorwilsdon/google_workspace_mcp` - Official tool list
- Blueprint §12 - Workspace Agent specification
- Plan: `docs/plans/google_workspace_agent_full_operational_plan.md`