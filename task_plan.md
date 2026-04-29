# MCP Productivity Coordination + Academic MCP Hardening — Task Plan

## Goal
Implementare il piano `docs/plans/mcp_productivity_coordination_optimization_plan_2026-04-29.md`:
Fase A (P0): search-agent exposure fix, conductor+productivity-agent, wrapper hardening
Fase B (P1): checksum/version pin per scientific-papers, MANIFEST.md

## Constraints
- AGENTS.md rules: wiki-first, Context7-first, no destructive actions
- LLM Wiki maintenance after each phase

## Phases

### Phase 0 — Source Audit [COMPLETE]
- [x] Read wiki index.md, log.md, research-routing.md, mcp-architecture.md, productivity-agent.md
- [x] Read search-agent.md, aria-conductor.md, productivity-agent.md, workspace-agent.md
- [x] Read pubmed-wrapper.sh, scientific-papers-wrapper.sh
- [x] Read mcp.json, router.py
- [x] Context7: /cyanheads/pubmed-mcp-server (9 tool confermati)
- [x] Context7: /benedict2310/scientific-papers-mcp (5 tool confermati)

### Phase A — Stabilizzazione immediata (P0) [COMPLETE]
- [x] A-1: search-agent.md — allowed-tools pubmed-mcp/* (9) + scientific-papers-mcp/* (5); mcp-dependencies
- [x] A-2: aria-conductor.md — productivity-agent nei sub-agenti + dispatch rules
- [x] A-3: pubmed-wrapper.sh — fallback bunx→npx con log WARN
- [x] A-4: scientific-papers-wrapper.sh — hard fail diagnostico su patch seed invalido

### Phase B — Refactor affidabilità MCP accademici (P1) [COMPLETE]
- [x] B-1: sci-papers version pin 0.1.40 (invece di @latest)
- [x] B-1: checksum SHA256 originali (da npm pack @0.1.40)
- [x] B-1: checksum SHA256 patched (da docs/patches/)
- [x] B-1: verifica pre-patch (original checksum match) + post-patch (patched checksum match)
- [x] B-1: MANIFEST.md creato con checksums, bug fixes, update procedure
- [x] B-1: .original.js sostituiti con veri originali npm (prima erano duplicati patched)

### Phase Wiki — LLM Wiki Update [COMPLETE]
- [x] docs/llm_wiki/wiki/log.md — implementation log entry
- [x] docs/llm_wiki/wiki/index.md — status v4.0, raw sources, bootstrap log
- [x] docs/llm_wiki/wiki/research-routing.md — agent/skill alignment table updated

### Phase C — Coordinamento formale tra i 3 agenti (P1) [COMPLETE]
- [x] C-1: Capability Matrix canonica — docs/foundation/agent-capability-matrix.md
- [x] C-1: Wiki mirror — docs/llm_wiki/wiki/agent-capability-matrix.md
- [x] C-2: Handoff protocol — payload {goal, constraints, required_output, timeout, trace_id}
- [x] C-3: Routing policy — 12 condizioni + catene dispatch + limiti operativi
- [x] Conductor prompt: capability matrix + dispatche rules
- [x] Template: _aria-conductor.template.md updated

### Phase D — Verifica, test e rollout (P0/P1) [COMPLETE]
- [x] D-1: 22 config consistency tests (search-agent YAML ↔ router)
- [x] D-1: 12 conductor dispatch tests (productivity-agent, handoff, config)
- [x] D-2: shell syntax check (both wrappers)
- [x] Search tests: 137/137 PASS
- [x] Conductor tests: 12/12 PASS
- [x] mypy src/aria/agents/search/: Success

## Expected Output
- search-agent.md: fully aligned tool exposure
- aria-conductor.md: productivity-agent dispatchable
- pubmed-wrapper.sh: graceful bunx→npx fallback
- scientific-papers-wrapper.sh: version-pinned, checksum-verified patching
- docs/patches/scientific-papers-mcp/: true originals + manifest
- wiki: aggiornato
