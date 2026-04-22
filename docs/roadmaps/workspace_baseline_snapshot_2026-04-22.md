---
document: Google Workspace MCP Baseline Snapshot
version: 1.0.0
status: created
date_created: 2026-04-22
owner: fulvio
phase: Phase 0
---

# Google Workspace MCP Baseline Snapshot
**Created:** 2026-04-22
**workspace-mcp version:** 1.19.0
**Collection method:** `uvx workspace-mcp --help`, repo analysis, Context7 verification

---

## 1. Upstream Tool Surface

### 1.1 Command Line Interface (verified)

```bash
uvx workspace-mcp [OPTIONS]

Options:
  --single-user         Run in single-user mode - bypass session mapping
  --tools [{gmail,drive,calendar,docs,sheets,chat,forms,slides,tasks,contacts,search,appscript} ...]
                        Specify which tools to register
  --tool-tier {core,extended,complete}
                        Load tools based on tier level
  --transport {stdio,streamable-http}
                        Transport mode: stdio (default) or streamable-http
  --read-only           Run in read-only mode - requests only read-only scopes
  --permissions SERVICE:LEVEL [SERVICE:LEVEL ...]
                        Granular per-service permission levels.
                        Format: service:level.
                        Example: --permissions gmail:organize drive:readonly
                        Gmail levels: readonly, organize, drafts, send, full (cumulative)
                        Other services: readonly, full
```

### 1.2 Complete Tool Inventory (114 tools across 10 domains)

| Domain | Tools Count | Tool Names |
|--------|------------|------------|
| Gmail | 14 | search_gmail_messages, get_gmail_message_content, get_gmail_messages_content_batch, get_gmail_attachment_content, send_gmail_message, draft_gmail_message, get_gmail_thread_content, get_gmail_threads_content_batch, list_gmail_labels, manage_gmail_label, list_gmail_filters, manage_gmail_filter, modify_gmail_message_labels, batch_modify_gmail_message_labels |
| Google Calendar | 7 | list_calendars, get_events, manage_event, manage_out_of_office, manage_focus_time, query_freebusy, create_calendar |
| Google Drive | 14 | search_drive_files, get_drive_file_content, get_drive_file_download_url, list_drive_items, create_drive_folder, create_drive_file, import_to_google_doc, get_drive_file_permissions, check_drive_file_public_access, update_drive_file, get_drive_shareable_link, manage_drive_access, copy_drive_file, set_drive_file_permissions |
| Google Docs | 20 | search_docs, get_doc_content, list_docs_in_folder, create_doc, modify_doc_text, find_and_replace_doc, insert_doc_elements, insert_doc_image, update_doc_headers_footers, batch_update_doc, inspect_doc_structure, debug_docs_runtime_info, create_table_with_data, debug_table_structure, export_doc_to_pdf, update_paragraph_style, get_doc_as_markdown, insert_doc_tab, delete_doc_tab, update_doc_tab |
| Google Sheets | 11 | list_spreadsheets, get_spreadsheet_info, read_sheet_values, modify_sheet_values, format_sheet_range, manage_conditional_formatring, create_spreadsheet, create_sheet, list_sheet_tables, append_table_rows, resize_sheet_dimensions |
| Google Slides | 5 | create_presentation, get_presentation, batch_update_presentation, get_page, get_page_thumbnail |
| Google Forms | 6 | create_form, get_form, set_publish_settings, get_form_response, list_form_responses, batch_update_form |
| Google Chat | 6 | list_spaces, get_messages, send_message, search_messages, create_reaction, download_chat_attachment |
| Google Tasks | 6 | list_task_lists, get_task_list, manage_task_list, list_tasks, get_task, manage_task |
| Google Custom Search | 2 | search_custom, get_search_engine_info |
| Google Contacts | 8 | list_contacts, get_contact, search_contacts, manage_contact, list_contact_groups, get_contact_group, manage_contacts_batch, manage_contact_group |
| Google Apps Script | 15 | list_script_projects, get_script_project, get_script_content, create_script_project, update_script_content, run_script_function, manage_deployment, list_deployments, list_script_processes, delete_script_project, list_versions, create_version, get_version, get_script_metrics, generate_trigger_code |

**Total: 114 tools across 12 domains**

### 1.3 Tool Tiers

| Tier | Services Included |
|------|-------------------|
| core | gmail, calendar, drive, docs, sheets |
| extended | core + chat, tasks, forms, contacts |
| complete | all services |

---

## 2. Runtime Configuration (Local ARIA)

### 2.1 MCP Server Configuration (kilo.json)

```json
"google_workspace": {
  "type": "local",
  "command": [
    "/home/fulvio/coding/aria/scripts/wrappers/google-workspace-wrapper.sh"
  ],
  "enabled": true,
  "environment": {
    "MCP_ENABLE_OAUTH21": "false",
    "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8080/callback",
    "GOOGLE_OAUTH_USE_PKCE": "true"
  }
}
```

### 2.2 Wrapper Path
- **Wrapper script:** `scripts/wrappers/google-workspace-wrapper.sh`
- **Credentials dir:** `.aria/runtime/credentials/google_workspace_mcp/`
- **Runtime scopes file:** `.aria/runtime/credentials/google_workspace_scopes_primary.json`

### 2.3 Current Scope State

Runtime scopes file (`google_workspace_scopes_primary.json`):
```json
{
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
  "account": "primary",
  "saved_at": 1776776328.5105875
}
```

**CRITICAL ISSUE:** Wrapper hardcodes `gmail.readonly` scope at line 77 of `google-workspace-wrapper.sh`:
```python
'scopes': ['https://www.googleapis.com/auth/gmail.readonly'],
```

### 2.4 Minimal Scopes (per ADR-0003)

ADR-0003 defines MINIMAL_SCOPES:
```python
MINIMAL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]
```

**Gap:** Runtime only has gmail.readonly; other 5 minimal scopes not granted.

---

## 3. Validator State

### 3.1 Agent Validator (`scripts/validate_agents.py`)

**Status:** BROKEN
**Issue:** References non-existent `mcp.json` instead of `kilo.json`

```
WARNING: mcp.json not found at /home/fulvio/coding/aria/.aria/kilocode/mcp.json
Agent validation FAILED:
  - aria-conductor: missing required field 'name'
  - aria-conductor: tool server 'aria-memory' not declared in mcp.json
  ... (all agents fail validation)
```

### 3.2 Skills Validator (`scripts/validate_skills.py`)

**Status:** BROKEN
**Issue:** References non-existent `mcp.json` instead of `kilo.json`

```
WARNING: mcp.json not found at /home/fulvio/coding/aria/.aria/kilocode/mcp.json, skipping server validation
Skill validation FAILED:
  - planning-with-files: tool server 'aria-memory' not declared in mcp.json
  ... (all skills fail validation)
```

---

## 4. Agent Configuration

### 4.1 workspace-agent.md (current)

```yaml
---
description: Sub-agent per operazioni Google Workspace (Gmail, Calendar, Drive, Docs, Sheets) via MCP. HITL obbligatorio su scritture.
mode: subagent
color: "#4285F4"
temperature: 0.1
permission:
  edit: deny
  bash: deny
  webfetch: deny
tools:
  task: false
  ...
---
```

**Issues:**
- Uses old frontmatter format (`tools:` instead of `allowed-tools:`)
- No explicit `allowed-tools` list (governance gap)
- No `required-skills` declared
- No P9 (20 tool limit) enforcement visible

### 4.2 Skills Available

| Skill | Path | Status |
|-------|------|--------|
| triage-email | `.aria/kilocode/skills/triage-email/SKILL.md` | exists |
| calendar-orchestration | `.aria/kilocode/skills/calendar-orchestration/SKILL.md` | exists |
| doc-draft | `.aria/kilocode/skills/doc-draft/SKILL.md` | exists |

---

## 5. Known Gaps (from analysis)

| ID | Gap | Impact | Priority |
|----|-----|--------|----------|
| G1 | Hardcoded gmail.readonly in wrapper | Only Gmail read-only works; Calendar/Drive/Docs/Sheets blocked | HIGH |
| G2 | Validators reference deleted mcp.json | All validation fails; no governance checking | HIGH |
| G3 | workspace-agent has no allowed-tools | P9 (20 tool limit) not enforced | HIGH |
| G4 | Scope coherence not checked | No verification runtime scopes vs required scopes | MEDIUM |
| G5 | No governance matrix | No centralized tool->risk->HITL->scope mapping | MEDIUM |

---

## 6. Collection Evidence

```bash
# Command used:
uvx workspace-mcp --help

# Result: workspace-mcp 1.19.0 confirmed with options:
# --single-user, --tools [...], --tool-tier {core,extended,complete}
# --transport {stdio,streamable-http}, --read-only
# --permissions SERVICE:LEVEL [...]

# Validators run:
python3 scripts/validate_agents.py  # FAILED - mcp.json not found
python3 scripts/validate_skills.py  # FAILED - mcp.json not found

# Scope files read:
# .aria/runtime/credentials/google_workspace_scopes_primary.json
# Contains only: ["https://www.googleapis.com/auth/gmail.readonly"]
```

---

## 7. Next Actions

1. **W0.2:** Create Tool Governance Matrix (all 114 tools -> domain, rw, risk, HITL, scope)
2. **W0.3:** Create ADR for wrapper/runtime credentials (document the file-based credential bridge)
3. **W0.4:** Update validators to use kilo.json instead of mcp.json
4. **W1.1:** De-hardcode wrapper scopes from canonical source

---

*This snapshot was created as part of Phase 0 (Program Setup & Governance Baseline) per `docs/plans/enhancment_workspace_PHASES-0_1_plan.md`.*
