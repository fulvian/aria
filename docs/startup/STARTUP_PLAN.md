# ARIA Universal Startup Plan
## Servizio di Health Check e Auto-Recovery per Sistema di Avvio

---

## 1. Analisi dello Stato Attuale

### 1.1 Flusso di Avvio Attuale

```
main.go
    └── cmd.Execute()
            └── rootCmd.RunE()
                    ├── 1. Parse flags
                    ├── 2. Change directory
                    ├── 3. godotenv.Load()
                    ├── 4. config.Load()           ← Configurazione
                    ├── 5. db.Connect()             ← Database SQLite (BLOCKING)
                    ├── 6. app.New(ctx, conn)      ← Creazione app
                    │       ├── session.NewService()
                    │       ├── message.NewService()
                    │       ├── history.NewService()
                    │       ├── permission.NewService()
                    │       ├── app.initTheme()
                    │       ├── agent.NewAgent()
                    │       └── app.initARIA()      ← Sistema ARIA completo
                    │               ├── skill registry
                    │               ├── agencies (dev, weather, nutrition, knowledge)
                    │               ├── memory service (4 layers)
                    │               ├── scheduler & workers
                    │               └── guardrail & permission
                    ├── 7. initMCPTools()          ← MCP (async, 30s timeout)
                    └── 8a. app.RunNonInteractive()  ← CLI mode
                    └── 8b. TUI start              ← Interactive mode
```

### 1.2 Dipendenze Esterne Identificate

| Servizio | Tipo | Stato Attuale | Criticità |
|----------|------|---------------|-----------|
| **SQLite Database** | Locale | `db.Ping()` + migrations | 🔴 Critico |
| **LLM Provider** | Remoto | Verifica via API key presence | 🟡 Medio (graceful degradation) |
| **LSP Servers** | Locale | Background init con polling | 🟢 Basso |
| **MCP Servers** | Remoto | Async init con 30s timeout | 🟢 Basso |
| **Memory Embeddings** | Remoto/Locale | Background worker | 🟡 Medio |

### 1.3 Problemi Identificati

1. **Nessun health check formale** - nessuna interfaccia `Checker`
2. **Nessun circuit breaker** - retry infinito su LLM provider
3. **Nessuna visibility** - servizi caduti non mostrati nell'UI
4. **Nessun retry con backoff** - failure = fail immediato
5. **Init LSP fire-and-forget** - nessun retry su failure transiente
6. **Nessun graceful degradation** - ARIA init fallisce → modalità legacy silenziosa

---

## 2. Architettura Proposta: Universal Startup System

### 2.1 Componenti del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIVERSAL STARTUP MANAGER                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Bootstrapper│  │HealthChecker │  │ ServiceOrchestrator  │   │
│  │             │  │              │  │                      │   │
│  │ • Phase 1   │  │ • Checker I/F│  │ • errgroup lifecycle │   │
│  │ • Phase 2   │  │ • Timeout    │  │ • Context cancel     │   │
│  │ • Phase 3   │  │ • Retry      │  │ • Graceful shutdown  │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ CircuitBreaker│ │StatusTracker │  │ RecoveryManager      │   │
│  │              │  │              │  │                      │   │
│  │ • Per-svc   │  │ • Atomic     │  │ • Startup recovery   │   │
│  │ • Half-open │  │ • UI update  │  │ • Scheduled retry   │   │
│  │ • Closed    │  │ • TTY status │  │ • Max attempts      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Interfaccia Health Checker

```go
// internal/startup/checker.go

// Checker è l'interfaccia base per tutti i health check
type Checker interface {
    Name() string                    // Nome univoco del servizio
    Priority() int                  // Priorità di inizializzazione (0=prima)
    Check(ctx context.Context) error // Verifica salute del servizio
}

// RetryableChecker estende Checker con capacità di retry
type RetryableChecker interface {
    Checker
    MaxRetries() int
    RetryDelay() time.Duration
}

// AutoRecoverer per servizi che possono essere avviati automaticamente
type AutoRecoverer interface {
    Recover(ctx context.Context) error  // Avvia/riavvia il servizio
    IsRecoverable() bool                 // Può essere recuperato?
}
```

### 2.3 Fasi di Startup

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 0: PRE-FLIGHT (Critical)                                    │
│ Ordine: 0-99                                                      │
│ Timeout: 30s total                                                 │
├─────────────────────────────────────────────────────────────────┤
│  1. Config Loader          (priority: 10)  ← Verifica .env validi │
│  2. Data Directory         (priority: 20)  ← Crea se non esiste   │
│  3. SQLite Connection      (priority: 30)  ← Ping + PRAGMA set    │
│  4. Schema Migration       (priority: 40)  ← goose.Up()           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: CORE SERVICES (Important)                                │
│ Ordine: 100-199                                                   │
│ Timeout: 60s total                                                │
├─────────────────────────────────────────────────────────────────┤
│  5. Session Service       (priority: 110)                         │
│  6. Message Service       (priority: 120)                         │
│  7. History Service       (priority: 130)                         │
│  8. Permission Service    (priority: 140)                         │
│  9. LLM Provider Config   (priority: 150)  ← Verifica API keys   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: ARIA COMPONENTS (Core)                                   │
│ Ordine: 200-299                                                   │
│ Timeout: 90s total                                               │
├─────────────────────────────────────────────────────────────────┤
│  10. Skill Registry       (priority: 210)                         │
│  11. Memory Service       (priority: 220)  ← 4-Layer System       │
│  12. Development Agency   (priority: 230)                         │
│  13. Knowledge Agency     (priority: 240)  ← Web search deps      │
│  14. Weather/Nutrition    (priority: 250)                         │
│  15. Orchestrator         (priority: 260)                         │
│  16. Scheduler/Workers   (priority: 270)                         │
│  17. Guardrail/Permission (priority: 280)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: OPTIONAL SERVICES (Degradable)                           │
│ Ordine: 300-399                                                   │
│ Timeout: Background (non blocking)                               │
├─────────────────────────────────────────────────────────────────┤
│  18. LSP Clients         (priority: 310)  ← Continue if fails     │
│  19. MCP Tools           (priority: 320)  ← Continue if fails     │
│  20. Embedding Worker   (priority: 330)  ← Continue if fails      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: READY                                                    │
│ Tutti i check passati → Avvio CLI/TUI                            │
│ Servizi degradati mostrati nello status bar                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Implementazione Dettagliata

### 3.1 Struttura File

```
internal/
  startup/
    bootstrap.go           # Coordinatore principale di startup
    bootstrap_test.go      # Test bootstrap
    checker.go             # Interfacce Checker, RetryableChecker, AutoRecoverer
    checkers/
      config.go            # Verifica configurazione
      database.go           # Verifica SQLite + migrations
      llm_provider.go       # Verifica LLM provider
      memory.go             # Verifica memory service (4 layers)
      lsp.go               # Verifica LSP clients
      mcp.go               # Verifica MCP servers
    circuitbreaker.go      # Implementazione circuit breaker
    status.go              # Status tracker atomico
    recovery.go            # Recovery manager per auto-riavvio
    startup.tui.go         # Componente TUI per visualizzazione status
    doc.go                 # Documentazione
```

### 3.2 Librerie Esterne Consigliate

| Scopo | Libreria | Note |
|-------|----------|------|
| Circuit Breaker | `github.com/sony/gobreaker` | Minimal, no dependencies |
| Exponential Backoff | `github.com/cenkalti/backoff` | Configurable, context-aware |
| Concurrent Lifecycle | `golang.org/x/sync/errgroup` | Standard, context propagation |
| Health Checks | `github.com/alexliesenfeld/health` | Flessibile per check custom |
| DB Migrations | Già in uso (goose) | Già presente nel progetto |

---

## 4. Piano di Implementazione

### Fase 1: Core Infrastructure (Settimana 1)
- [ ] Creare `internal/startup/checker.go` con interfacce
- [ ] Creare `internal/startup/bootstrap.go` con BootstrapManager
- [ ] Creare `internal/startup/status.go` con StatusTracker
- [ ] Creare `internal/startup/circuitbreaker.go`
- [ ] Creare test per bootstrap manager

### Fase 2: Checkers (Settimana 2)
- [ ] `checkers/config.go` - Config loader checker
- [ ] `checkers/database.go` - SQLite checker + recovery
- [ ] `checkers/llm_provider.go` - LLM provider checker
- [ ] `checkers/memory.go` - 4-layer memory checker
- [ ] `checkers/lsp.go` - LSP checker + recovery

### Fase 3: UI Integration (Settimana 3)
- [ ] `startup.tui.go` - Status view per TUI
- [ ] Modificare `cmd/root.go` per usare BootstrapManager
- [ ] Aggiungere flag `--startup-debug` per verbose output
- [ ] Integrare status nella status bar TUI

### Fase 4: Polish (Settimana 4)
- [ ] Aggiungere circuit breakers ai LLM provider calls
- [ ] Implementare recovery manager
- [ ] Aggiungere metriche e observability
- [ ] Performance testing e tuning

---

## 5. Metriche di Successo

| Metrica | Target |
|---------|--------|
| Tempo startup medio | < 3 secondi (senza servizi remoti) |
| Tempo startup con LSP | < 10 secondi |
| Failed startup → errore chiaro | 100% |
| Servizi opzionali down → TUI funziona | 100% |
| Recovery automatico | > 90% dei casi |
| Test coverage | > 80% |

---

## 6. Riferimenti e Best Practices

### Pattern Go per Service Health

```go
// Pattern standard per health check con timeout
type Checker interface {
    Name() string
    Check(ctx context.Context) error
}

// Esecuzione parallela con errgroup
g, ctx := errgroup.WithContext(ctx)
for _, c := range checkers {
    c := c
    g.Go(func() error {
        return c.Check(ctx)
    })
}
if err := g.Wait(); err != nil {
    // handle
}

// Retry con exponential backoff
delay := 100 * time.Millisecond
for attempt := 0; attempt <= maxRetries; attempt++ {
    if err := fn(); err == nil {
        return nil
    }
    time.Sleep(delay + jitter)
    delay = min(delay*2, 30*time.Second)
}
```

### Pattern Circuit Breaker (gobreaker)

```go
cb := gobreaker.NewCircuitBreaker(gobreaker.Settings{
    Name:        "llm-provider",
    MaxRequests: 3,
    Interval:    30 * time.Second,
    Timeout:     30 * time.Second,
    ReadyToTrip: func(counts gobreaker.Counts) bool {
        return counts.ConsecutiveFailures >= 5
    },
})
```
