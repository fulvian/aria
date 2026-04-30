# Task Plan: Fix wiki_update_tool Title Field Bug

## Goal
Fix 3 bugs in ARIA wiki memory system causing `wiki_update_tool` to fail when creating topic pages without an explicit `title` field.

## Root Cause Summary
- **BUG P0**: Conductor prompt (`aria-conductor.md`) does not document `title` as required field for `op="create"`
- **BUG P1**: Pydantic validator `_validate_title_on_create` in `schema.py` is a no-op
- **BUG P2**: No auto-extraction fallback of title from markdown heading in `body_md` in `db.py`

## Phases

### Phase 1: Pydantic validator (schema.py)
- [ ] Fix `_validate_title_on_create` to raise ValueError when op="create" and title is None

### Phase 2: Title auto-extraction (db.py)
- [ ] Add fallback in `create_page`: extract first `# Heading` from body_md when title is None

### Phase 3: Conductor prompt documentation (aria-conductor.md + template)
- [ ] Add `title` column to the rules table
- [ ] Add note about title auto-extraction from body_md

### Phase 4: Quality gates
- [ ] `ruff check .`
- [ ] `mypy src`
- [ ] `pytest -q tests/unit/memory/`

### Phase 5: Wiki + State update
- [ ] Update `docs/llm_wiki/wiki/log.md`
- [ ] Update `docs/llm_wiki/wiki/index.md`
- [ ] Update `docs/llm_wiki/wiki/memory-v3.md`
- [ ] Update `.workflow/state.md`
- [ ] Update memory entities

## Files Modified
- `src/aria/memory/wiki/schema.py`
- `src/aria/memory/wiki/db.py`
- `.aria/kilocode/agents/aria-conductor.md`
- `.aria/kilo-home/.kilo/agents/_aria-conductor.template.md`
- `docs/llm_wiki/wiki/log.md`
- `docs/llm_wiki/wiki/index.md`
- `docs/llm_wiki/wiki/memory-v3.md`
- `.workflow/state.md`
