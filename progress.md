# MCP Productivity Coordination + Academic MCP Hardening — Progress

## 2026-04-29T20:17+02:00 — Session start
- Richiesta utente: implementare `docs/plans/mcp_productivity_coordination_optimization_plan_2026-04-29.md`
- Vincoli: AGENTS.md, wiki-first, Context7-first

## 2026-04-29T20:18+02:00 — Context recovery complete
- Current branch: `feature/productivity-agent-mvp` (14 uncommitted changes)
- Eseguito session catchup: planning files existono da task precedente
- Letti wiki index.md, log.md, research-routing.md, mcp-architecture.md, productivity-agent.md

## 2026-04-29T20:20+02:00 — Source audit complete
- Letti: search-agent.md, aria-conductor.md, productivity-agent.md, workspace-agent.md
- Letti: pubmed-wrapper.sh, scientific-papers-wrapper.sh, mcp.json, router.py
- Identificati tutti i gap: exposure, conductor, wrapper hardening

## 2026-04-29T20:23+02:00 — Context7 verification complete
- `/cyanheads/pubmed-mcp-server` — 9 tool names confermati (prefix `pubmed_`)
- `/benedict2310/scientific-papers-mcp` — 5 tool names confermati (no prefix)

## 2026-04-29T20:25+02:00 — Phase A implementation complete
- A-1: search-agent.md — allowed-tools + mcp-dependencies aggiunti
- A-2: aria-conductor.md — productivity-agent + dispatch rules
- A-3: pubmed-wrapper.sh — bunx→npx fallback
- A-4: scientific-papers-wrapper.sh — hard fail su patch seed invalido

## 2026-04-29T20:30+02:00 — Phase B implementation complete
- B-1: scientific-papers-wrapper — version pin 0.1.40, checksum guard, verifica pre/post patch
- B-1: MANIFEST.md creato con checksum originali/patched
- B-1: .original.js sostituiti con veri originali npm (prima erano duplicati)
- B-1: npx pinato a @0.1.40 invece di @latest

## 2026-04-29T20:35+02:00 — Wiki maintenance
- docs/llm_wiki/wiki/log.md: aggiornato
- docs/llm_wiki/wiki/index.md: v4.0 status, raw sources, bootstrap log
- docs/llm_wiki/wiki/research-routing.md: agent alignment table updated
- task_plan.md, findings.md, progress.md: aggiornati

## Errors / Adaptations
| Time | Issue | Resolution |
|------|-------|------------|
| 20:28 | `.original.js` files in docs/patches erano duplicati dei patched | Scaricati veri originali da npm pack @0.1.40 |
| 20:29 | npm pack fallisce in /tmp con path lunghi | Usato /tmp/npmextract dedicato |

## Final Outputs
- `.aria/kilocode/agents/search-agent.md` — fully aligned exposure
- `.aria/kilocode/agents/aria-conductor.md` — productivity-agent dispatchable
- `scripts/wrappers/pubmed-wrapper.sh` — bunx→npx fallback
- `scripts/wrappers/scientific-papers-wrapper.sh` — version pin + checksum guard
- `docs/patches/scientific-papers-mcp/MANIFEST.md` — version manifest
- `docs/patches/scientific-papers-mcp/*.original.js` — true npm originals
- Wiki pages aggiornate
