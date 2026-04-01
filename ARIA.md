# ARIA - Note Persistenti

## Ultime Modifiche (2026-04-01)

### Universal Startup System
- Sistema di health check e auto-recovery per lo startup
- 4 fasi: PRE-FLIGHT → CORE SERVICES → ARIA COMPONENTS → OPTIONAL SERVICES
- Circuit breaker per LLM provider calls
- Status tracker atomico con supporto subscription
- UI components per visualizzazione status
- Flag `--startup-debug` per debug dello startup

```bash
# Run con startup debug (mostra health check status)
aria --startup-debug
```

### File creati
- `internal/startup/` - Core startup system
  - `checker.go` - Checker interface
  - `status.go` - StatusTracker
  - `circuitbreaker.go` - Circuit breaker
  - `bootstrap.go` - BootstrapManager
  - `startup_tui.go` - TUI components
  - `recovery.go` - RecoveryManager
  - `checkers/` - Service-specific checkers

---

## Utente
- **Nome**: Fulvio
- **Età**: 45 anni
- **Famiglia**: Sposato con Federica, figlia Adriana (21 mesi)
- **Città**: Caltanissetta, Sicilia
- **Lingua preferita**: Italiano

## Lavoro
- **Ruolo**: Consulente per la Pubblica Amministrazione
- **Settori principali**:
  - Progetti di innovazione tecnologica negli Uffici Giudiziari
  - Gestioni associate per enti locali (Comuni e Unioni di Comuni italiani)

## Preferenze
- Gli piace il tennis 🎾 (gioca)
- Serie crime e film 🎬
- Appassionato di tecnologia, informatica, AI, LLM, training e fine-tuning con librerie transformer (LoRA, QLoRA)
- Vibe coding / coding assistito da AI — ha creato aria stesso
- Suite Google Workspace (documenti, fogli, presentazioni — formati Office vari)
- Lavora molto in call online (Google Meet, Microsoft Teams)

## Tool
- Google Workspace (online)
- Google Meet, Microsoft Teams
- AI coding tools (aria, altri)

## Comandi Utili

### Build & Run
```bash
# Build ariacli
go build -o ariacli ./main.go

# Run interattivo (con env)
source .env && go run ./main.go

# Run con prompt diretto
./ariacli -p "query"
```

### Test & Lint
```bash
go test ./...              # Tutti i test
go test ./internal/llm/tools/...  # Test package specifico
go vet ./...                # Lint
```

### Git
```bash
git status                 # Status
git log --oneline -5       # Ultimi commit
git branch -a              # Tutti i branch
```

## ARIA Architecture

### Agencies
- `development` - Coding, devops, testing
- `weather` - Previsioni meteo
- `nutrition` - Cibo, nutrizione, ricette ⭐

### Nutrition Agency
```bash
# Query esempio
./ariacli -p "cerca una ricetta con pollo e broccoli"
./ariacli -p "quali sono i nutrienti di una mela"
./ariacli -p "crea un piano alimentare dimagrente"
./ariacli -p "ci sono richiami alimentari negli USA"
```
