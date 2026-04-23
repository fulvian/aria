---
document: Google Workspace Tool Governance Matrix
version: 1.0.0
status: draft
date_created: 2026-04-22
owner: fulvio
phase: Phase 0
---

# Google Workspace Tool Governance Matrix

## Purpose

This matrix provides a centralized governance registry for all 114 tools exposed by the `google_workspace_mcp` server (v1.19.0). It maps each tool to:
- Domain (Workspace product)
- Read/Write classification
- Risk level
- Policy (allow/ask/deny)
- HITL requirement
- Minimum OAuth scope required
- Owner (responsible for test coverage)
- Test case ID

## Policy Rules

| Policy | Meaning |
|--------|---------|
| **allow** | Tool can execute without explicit human approval |
| **ask** | Tool requires HITL confirmation before execution |
| **deny** | Tool is blocked from execution (requires ADR to unblock) |

## HITL Triggers (per P7)

HITL is required when:
- Tool performs destructive/irreversible actions (delete, revoke, overwrite, permission hardening)
- Tool accesses sensitive data at high scale with material blast radius
- Operation is expensive (high API quota consumption)

---

## Gmail Tools (14)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| search_gmail_messages | gmail | read | low | allow | no | gmail.readonly | workspace-owner | GW-GM-001 |
| get_gmail_message_content | gmail | read | low | allow | no | gmail.readonly | workspace-owner | GW-GM-002 |
| get_gmail_messages_content_batch | gmail | read | medium | allow | no | gmail.readonly | workspace-owner | GW-GM-003 |
| get_gmail_attachment_content | gmail | read | low | allow | no | gmail.readonly | workspace-owner | GW-GM-004 |
| send_gmail_message | gmail | write | high | ask | yes | gmail.send | workspace-owner | GW-GM-005 |
| draft_gmail_message | gmail | write | medium | ask | yes | gmail.drafts | workspace-owner | GW-GM-006 |
| get_gmail_thread_content | gmail | read | low | allow | no | gmail.readonly | workspace-owner | GW-GM-007 |
| get_gmail_threads_content_batch | gmail | read | medium | allow | no | gmail.readonly | workspace-owner | GW-GM-008 |
| list_gmail_labels | gmail | read | low | allow | no | gmail.readonly | workspace-owner | GW-GM-009 |
| manage_gmail_label | gmail | write | medium | ask | yes | gmail.modify | workspace-owner | GW-GM-010 |
| list_gmail_filters | gmail | read | low | allow | no | gmail.readonly | workspace-owner | GW-GM-011 |
| manage_gmail_filter | gmail | write | medium | ask | yes | gmail.modify | workspace-owner | GW-GM-012 |
| modify_gmail_message_labels | gmail | write | medium | ask | yes | gmail.modify | workspace-owner | GW-GM-013 |
| batch_modify_gmail_message_labels | gmail | write | high | ask | yes | gmail.modify | workspace-owner | GW-GM-014 |

---

## Google Calendar Tools (7)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| list_calendars | calendar | read | low | allow | no | calendar.readonly | workspace-owner | GW-CAL-001 |
| get_events | calendar | read | low | allow | no | calendar.readonly | workspace-owner | GW-CAL-002 |
| manage_event | calendar | write | high | ask | yes | calendar.events | workspace-owner | GW-CAL-003 |
| manage_out_of_office | calendar | write | high | ask | yes | calendar.events | workspace-owner | GW-CAL-004 |
| manage_focus_time | calendar | write | medium | ask | yes | calendar.events | workspace-owner | GW-CAL-005 |
| query_freebusy | calendar | read | low | allow | no | calendar.readonly | workspace-owner | GW-CAL-006 |
| create_calendar | calendar | write | medium | ask | yes | calendar.events | workspace-owner | GW-CAL-007 |

---

## Google Drive Tools (14)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| search_drive_files | drive | read | low | allow | no | drive.readonly | workspace-owner | GW-DR-001 |
| get_drive_file_content | drive | read | medium | allow | no | drive.readonly | workspace-owner | GW-DR-002 |
| get_drive_file_download_url | drive | read | low | allow | no | drive.readonly | workspace-owner | GW-DR-003 |
| list_drive_items | drive | read | low | allow | no | drive.readonly | workspace-owner | GW-DR-004 |
| create_drive_folder | drive | write | low | ask | yes | drive.file | workspace-owner | GW-DR-005 |
| create_drive_file | drive | write | medium | ask | yes | drive.file | workspace-owner | GW-DR-006 |
| import_to_google_doc | drive | write | medium | ask | yes | drive.file | workspace-owner | GW-DR-007 |
| get_drive_file_permissions | drive | read | medium | allow | no | drive.readonly | workspace-owner | GW-DR-008 |
| check_drive_file_public_access | drive | read | low | allow | no | drive.readonly | workspace-owner | GW-DR-009 |
| update_drive_file | drive | write | high | ask | yes | drive.file | workspace-owner | GW-DR-010 |
| get_drive_shareable_link | drive | read | low | allow | no | drive.readonly | workspace-owner | GW-DR-011 |
| manage_drive_access | drive | write | high | ask | yes | drive.file | workspace-owner | GW-DR-012 |
| copy_drive_file | drive | write | low | ask | yes | drive.file | workspace-owner | GW-DR-013 |
| set_drive_file_permissions | drive | write | high | ask | yes | drive.file | workspace-owner | GW-DR-014 |

---

## Google Docs Tools (20)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| search_docs | docs | read | low | allow | no | documents.readonly | workspace-owner | GW-DOC-001 |
| get_doc_content | docs | read | low | allow | no | documents.readonly | workspace-owner | GW-DOC-002 |
| list_docs_in_folder | docs | read | low | allow | no | documents.readonly | workspace-owner | GW-DOC-003 |
| create_doc | docs | write | medium | ask | yes | documents | workspace-owner | GW-DOC-004 |
| modify_doc_text | docs | write | medium | ask | yes | documents | workspace-owner | GW-DOC-005 |
| find_and_replace_doc | docs | write | low | ask | yes | documents | workspace-owner | GW-DOC-006 |
| insert_doc_elements | docs | write | medium | ask | yes | documents | workspace-owner | GW-DOC-007 |
| insert_doc_image | docs | write | medium | ask | yes | documents | workspace-owner | GW-DOC-008 |
| update_doc_headers_footers | docs | write | low | ask | yes | documents | workspace-owner | GW-DOC-009 |
| batch_update_doc | docs | write | high | ask | yes | documents | workspace-owner | GW-DOC-010 |
| inspect_doc_structure | docs | read | low | allow | no | documents.readonly | workspace-owner | GW-DOC-011 |
| debug_docs_runtime_info | docs | read | low | allow | no | documents.readonly | workspace-owner | GW-DOC-012 |
| create_table_with_data | docs | write | medium | ask | yes | documents | workspace-owner | GW-DOC-013 |
| debug_table_structure | docs | read | low | allow | no | documents.readonly | workspace-owner | GW-DOC-014 |
| export_doc_to_pdf | docs | write | low | ask | yes | documents | workspace-owner | GW-DOC-015 |
| update_paragraph_style | docs | write | low | ask | yes | documents | workspace-owner | GW-DOC-016 |
| get_doc_as_markdown | docs | read | low | allow | no | documents.readonly | workspace-owner | GW-DOC-017 |
| insert_doc_tab | docs | write | low | ask | yes | documents | workspace-owner | GW-DOC-018 |
| delete_doc_tab | docs | write | medium | ask | yes | documents | workspace-owner | GW-DOC-019 |
| update_doc_tab | docs | write | low | ask | yes | documents | workspace-owner | GW-DOC-020 |

---

## Google Sheets Tools (11)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| list_spreadsheets | sheets | read | low | allow | no | spreadsheets.readonly | workspace-owner | GW-SH-001 |
| get_spreadsheet_info | sheets | read | low | allow | no | spreadsheets.readonly | workspace-owner | GW-SH-002 |
| read_sheet_values | sheets | read | low | allow | no | spreadsheets.readonly | workspace-owner | GW-SH-003 |
| modify_sheet_values | sheets | write | high | ask | yes | spreadsheets | workspace-owner | GW-SH-004 |
| format_sheet_range | sheets | write | low | ask | yes | spreadsheets | workspace-owner | GW-SH-005 |
| manage_conditional_formatting | sheets | write | low | ask | yes | spreadsheets | workspace-owner | GW-SH-006 |
| create_spreadsheet | sheets | write | medium | ask | yes | spreadsheets | workspace-owner | GW-SH-007 |
| create_sheet | sheets | write | low | ask | yes | spreadsheets | workspace-owner | GW-SH-008 |
| list_sheet_tables | sheets | read | low | allow | no | spreadsheets.readonly | workspace-owner | GW-SH-009 |
| append_table_rows | sheets | write | medium | ask | yes | spreadsheets | workspace-owner | GW-SH-010 |
| resize_sheet_dimensions | sheets | write | low | ask | yes | spreadsheets | workspace-owner | GW-SH-011 |

---

## Google Slides Tools (5)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| create_presentation | slides | write | medium | ask | yes | slides | workspace-owner | GW-SL-001 |
| get_presentation | slides | read | low | allow | no | slides.readonly | workspace-owner | GW-SL-002 |
| batch_update_presentation | slides | write | high | ask | yes | slides | workspace-owner | GW-SL-003 |
| get_page | slides | read | low | allow | no | slides.readonly | workspace-owner | GW-SL-004 |
| get_page_thumbnail | slides | read | low | allow | no | slides.readonly | workspace-owner | GW-SL-005 |

---

## Google Forms Tools (6)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| create_form | forms | write | medium | ask | yes | forms | workspace-owner | GW-FM-001 |
| get_form | forms | read | low | allow | no | forms.readonly | workspace-owner | GW-FM-002 |
| set_publish_settings | forms | write | medium | ask | yes | forms | workspace-owner | GW-FM-003 |
| get_form_response | forms | read | low | allow | no | forms.readonly | workspace-owner | GW-FM-004 |
| list_form_responses | forms | read | low | allow | no | forms.readonly | workspace-owner | GW-FM-005 |
| batch_update_form | forms | write | medium | ask | yes | forms | workspace-owner | GW-FM-006 |

---

## Google Chat Tools (6)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| list_spaces | chat | read | low | allow | no | chat.readonly | workspace-owner | GW-CH-001 |
| get_messages | chat | read | medium | allow | no | chat.readonly | workspace-owner | GW-CH-002 |
| send_message | chat | write | high | ask | yes | chat | workspace-owner | GW-CH-003 |
| search_messages | chat | read | medium | allow | no | chat.readonly | workspace-owner | GW-CH-004 |
| create_reaction | chat | write | low | ask | yes | chat | workspace-owner | GW-CH-005 |
| download_chat_attachment | chat | read | medium | allow | no | chat.readonly | workspace-owner | GW-CH-006 |

---

## Google Tasks Tools (6)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| list_task_lists | tasks | read | low | allow | no | tasks.readonly | workspace-owner | GW-TS-001 |
| get_task_list | tasks | read | low | allow | no | tasks.readonly | workspace-owner | GW-TS-002 |
| manage_task_list | tasks | write | medium | ask | yes | tasks | workspace-owner | GW-TS-003 |
| list_tasks | tasks | read | low | allow | no | tasks.readonly | workspace-owner | GW-TS-004 |
| get_task | tasks | read | low | allow | no | tasks.readonly | workspace-owner | GW-TS-005 |
| manage_task | tasks | write | medium | ask | yes | tasks | workspace-owner | GW-TS-006 |

---

## Google Custom Search Tools (2)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| search_custom | search | read | low | allow | no | search.readonly | workspace-owner | GW-SR-001 |
| get_search_engine_info | search | read | low | allow | no | search.readonly | workspace-owner | GW-SR-002 |

---

## Google Contacts Tools (8)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| list_contacts | contacts | read | medium | allow | no | contacts.readonly | workspace-owner | GW-CT-001 |
| get_contact | contacts | read | medium | allow | no | contacts.readonly | workspace-owner | GW-CT-002 |
| search_contacts | contacts | read | medium | allow | no | contacts.readonly | workspace-owner | GW-CT-003 |
| manage_contact | contacts | write | high | ask | yes | contacts | workspace-owner | GW-CT-004 |
| list_contact_groups | contacts | read | low | allow | no | contacts.readonly | workspace-owner | GW-CT-005 |
| get_contact_group | contacts | read | low | allow | no | contacts.readonly | workspace-owner | GW-CT-006 |
| manage_contacts_batch | contacts | write | high | ask | yes | contacts | workspace-owner | GW-CT-007 |
| manage_contact_group | contacts | write | medium | ask | yes | contacts | workspace-owner | GW-CT-008 |

---

## Google Apps Script Tools (15)

| tool_name | domain | rw | risk | policy | hitl_required | min_scope | owner | testcase_id |
|-----------|--------|-----|------|--------|---------------|-----------|-------|-------------|
| list_script_projects | appscript | read | low | allow | no | appscript.readonly | workspace-owner | GW-AS-001 |
| get_script_project | appscript | read | low | allow | no | appscript.readonly | workspace-owner | GW-AS-002 |
| get_script_content | appscript | read | medium | allow | no | appscript.readonly | workspace-owner | GW-AS-003 |
| create_script_project | appscript | write | high | ask | yes | appscript | workspace-owner | GW-AS-004 |
| update_script_content | appscript | write | high | ask | yes | appscript | workspace-owner | GW-AS-005 |
| run_script_function | appscript | write | critical | deny | yes | appscript | workspace-owner | GW-AS-006 |
| manage_deployment | appscript | write | high | ask | yes | appscript | workspace-owner | GW-AS-007 |
| list_deployments | appscript | read | low | allow | no | appscript.readonly | workspace-owner | GW-AS-008 |
| list_script_processes | appscript | read | low | allow | no | appscript.readonly | workspace-owner | GW-AS-009 |
| delete_script_project | appscript | write | critical | deny | yes | appscript | workspace-owner | GW-AS-010 |
| list_versions | appscript | read | low | allow | no | appscript.readonly | workspace-owner | GW-AS-011 |
| create_version | appscript | write | medium | ask | yes | appscript | workspace-owner | GW-AS-012 |
| get_version | appscript | read | low | allow | no | appscript.readonly | workspace-owner | GW-AS-013 |
| get_script_metrics | appscript | read | low | allow | no | appscript.readonly | workspace-owner | GW-AS-014 |
| generate_trigger_code | appscript | write | medium | ask | yes | appscript | workspace-owner | GW-AS-015 |

---

## Scope Reference

### Minimal Scopes (per ADR-0003 - usable without escalation)
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/gmail.drafts`
- `https://www.googleapis.com/auth/gmail.send`
- `https://www.googleapis.com/auth/calendar.readonly`
- `https://www.googleapis.com/auth/calendar.events`
- `https://www.googleapis.com/auth/drive.readonly`
- `https://www.googleapis.com/auth/drive.file`
- `https://www.googleapis.com/auth/documents.readonly`
- `https://www.googleapis.com/auth/documents`
- `https://www.googleapis.com/auth/spreadsheets.readonly`
- `https://www.googleapis.com/auth/spreadsheets`
- `https://www.googleapis.com/auth/spreadsheets`
- `https://www.googleapis.com/auth/forms`
- `https://www.googleapis.com/auth/forms.readonly`
- `https://www.googleapis.com/auth/chat.readonly`
- `https://www.googleapis.com/auth/chat`
- `https://www.googleapis.com/auth/tasks.readonly`
- `https://www.googleapis.com/auth/tasks`
- `https://www.googleapis.com/auth/contacts.readonly`
- `https://www.googleapis.com/auth/contacts`

### Broad Scopes (require explicit ADR)
- `https://www.googleapis.com/auth/gmail` (full Gmail)
- `https://www.googleapis.com/auth/calendar` (full Calendar)
- `https://www.googleapis.com/auth/drive` (full Drive)
- `https://www.googleapis.com/auth/drive.readonly` (full Drive readonly)

---

## Summary Statistics

| Domain | Total Tools | Read | Write | Ask | Allow | Deny |
|--------|-------------|------|-------|-----|-------|------|
| Gmail | 14 | 8 | 6 | 6 | 8 | 0 |
| Calendar | 7 | 3 | 4 | 4 | 3 | 0 |
| Drive | 14 | 6 | 8 | 8 | 6 | 0 |
| Docs | 20 | 8 | 12 | 12 | 8 | 0 |
| Sheets | 11 | 5 | 6 | 6 | 5 | 0 |
| Slides | 5 | 3 | 2 | 2 | 3 | 0 |
| Forms | 6 | 3 | 3 | 3 | 3 | 0 |
| Chat | 6 | 3 | 3 | 3 | 3 | 0 |
| Tasks | 6 | 4 | 2 | 2 | 4 | 0 |
| Search | 2 | 2 | 0 | 0 | 2 | 0 |
| Contacts | 8 | 5 | 3 | 3 | 5 | 0 |
| Apps Script | 15 | 8 | 7 | 5 | 7 | 2 |
| **TOTAL** | **114** | **58** | **56** | **54** | **58** | **2** |

---

## Denied Tools (require ADR to unblock)

| tool_name | reason_for_deny | unlock_requirement |
|-----------|-----------------|-------------------|
| run_script_function | Can execute arbitrary code with user credentials | Dedicated ADR with security review |
| delete_script_project | Permanent deletion of Apps Script projects | Dedicated ADR with backup requirement |

---

*This matrix is part of Phase 0 governance baseline per `docs/plans/enhancment_workspace_PHASES-0_1_plan.md`.*
*Updates require PR with governance review.*
