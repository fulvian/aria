# ARIA Nutrition Agency — Piano di Fondazione e Creazione

**Data**: 2026-03-30  
**Owner**: General Manager (orchestrazione)  
**Scope**: Analisi architetturale + piano implementativo per nuova agenzia Alimentazione/Nutrizione  
**Stato**: Draft pronto per approvazione PRD/TDD

---

## 1) Obiettivo

Implementare la prima agenzia di dominio “alimentazione” capace di gestire:
- ricette culinarie e varianti
- analisi nutrizionale dei pasti
- piani alimentari personalizzati (non-medicali)
- consigli di stile di vita sano
- alert di sicurezza alimentare (recall/eventi)

con architettura **Agency → Agents → Skills → Tools** coerente con:
- `docs/guides/aria-entity-creation-guide.md`
- `docs/foundation/BLUEPRINT.md` (FASE 5 agencies rollout)
- implementazione reale corrente (`weather` + `development` agencies)

---

## 2) Stato codebase attuale (impatto su design)

### 2.1 Pattern già validato
- Agency concrete: `internal/aria/agency/weather.go` (Direct API pattern)
- Config agenzia: `internal/aria/config/weather.go`
- Integrazione runtime: `internal/app/aria_integration.go`
- Skill layer: `internal/aria/skill/*`
- Registry/lifecycle già presenti e funzionanti

### 2.2 Vincoli tecnici da rispettare
- `contracts.AgencyName` non include ancora `nutrition` (oggi include `personal`)
- Routing domain (`routing.DomainName`) non include `nutrition` (oggi include `personal`)
- `SetupDefaultSkills` registra solo skill development (va esteso per nuove skill, preferibilmente per agency-aware setup)
- Necessità di mantenere approccio **Direct API first** (token/costo/latency migliori rispetto a MCP per API fisse)

### 2.3 Decisione architetturale proposta
Per evitare ambiguità del dominio `personal`, introdurre **agency dedicata**:
- `AgencyNutrition = "nutrition"`
- domain classifier dedicato `DomainNutrition = "nutrition"`

> Nota blueprint/governance: questa è un’estensione del modello a nuova entità di dominio; richiede update del blueprint/changelog prima dell’implementazione completa.

---

## 3) Architettura target della Nutrition Agency

## 3.1 Agency

**Nome**: `nutrition`  
**Dominio**: `nutrition`  
**Descrizione**: alimentazione, nutrizione, meal planning, food safety

### 3.2 Agenti specializzati (prima release)

1. **CulinaryAgent**
   - missione: ricette, varianti, sostituzioni ingredienti, cucina per vincoli (veg, gluten-free, low-carb)
   - skill principali: `recipe-search`, `recipe-adaptation`

2. **DietPlannerAgent**
   - missione: piano alimentare personalizzato (obiettivo, preferenze, allergeni, budget, tempo)
   - skill principali: `diet-plan-generation`, `meal-plan-optimization`

3. **NutritionAnalystAgent**
   - missione: analisi macro/micro nutrienti e confronto con target
   - skill principali: `nutrition-analysis`, `label-interpretation`

4. **HealthyLifestyleCoachAgent**
   - missione: consigli abitudini sane e aderenza comportamentale
   - skill principali: `healthy-habits-coaching`, `nutrition-education`

5. **FoodSafetyAgent**
   - missione: verifica recall/allerta su prodotti e categorie
   - skill principali: `food-recall-monitoring`, `food-risk-summary`

---

## 4) Skills v1 (MVP → V1.1)

### MVP (obbligatorie)
- `recipe-search`
- `nutrition-analysis`
- `diet-plan-generation`
- `food-recall-monitoring`

### V1.1 (subito dopo MVP)
- `recipe-adaptation`
- `meal-plan-optimization`
- `healthy-habits-coaching`
- `nutrition-education`

### Regole di esecuzione skill
- validazione input rigorosa (allergeni/intolleranze/obiettivi)
- output strutturato + spiegazione testuale
- policy guardrail: nessuna prescrizione medica, nessuna diagnosi

---

## 5) Ricerca API e dataset utili (free/free-tier) — evidenza ufficiale

## 5.1 Catalogo raccomandato

| Provider | Categoria | Auth | Free/free-tier verificato | Note licenza/ToS | Idoneità ARIA |
|---|---|---|---|---|---|
| **USDA FoodData Central** (`fdc.nal.usda.gov`) | Nutrienti ufficiali, alimenti branded/foundation | API key (data.gov) | ~**1000 req/ora/IP** (FDC guide), DEMO_KEY limitato | Dati in **CC0/public domain**, citazione richiesta | **Core** per analisi nutrizionale |
| **Open Food Facts API** (`openfoodfacts.github.io`) | Barcode/ingredienti/nutrizione crowdsourced | read: custom User-Agent; write: auth | Rate limits endpoint-based (es. 100 req/min product, 10 req/min search) | **ODbL + attribution + share-alike** | **Core** per lookup prodotti |
| **TheMealDB** (`themealdb.com`) | Ricette e metadata base | test key `1`, key premium per app store | API gratuita per sviluppo; produzione commerciale richiede subscription | ToS specifica condizioni app-store/commercial | **Core** per recipe discovery rapido |
| **Spoonacular** (`spoonacular.com`) | Ricette + meal planning + nutrition | API key | Piano free: **50 points/day**; quote model con headers quota | caching limitata (FAQ/docs), backlink nel free plan | **Optional premium** (feature avanzate) |
| **CalorieNinjas** (`calorieninjas.com`) | NLP nutrition + ricette | API key header | Piano free: **10,000 calls/month**, non commercial | commercial da piani paid | **Optional** per prototipi NLP |
| **FatSecret Platform API** (`platform.fatsecret.com`) | Food DB globale, barcode, recipe, localization | OAuth/API auth | Basic free: **5,000 calls/day**, US dataset | attribution obbligatoria su Basic/Premier Free | **Strong optional** per crescita globale |
| **openFDA Food Enforcement/Event** (`open.fda.gov`) | Recall/sicurezza alimentare USA | API key opzionale | senza key: 240 req/min, 1000/day; con key: 240 req/min, 120k/day | dataset pubblico FDA, TOS openFDA | **Core** per FoodSafetyAgent |
| **WHO GHO OData API / Nutrition portal** (`who.int`, `ghoapi.azureedge.net`) | Indicatori nutrizionali globali epidemiologici | no key (endpoint OData) | accesso open (nessun free-tier commerciale, open data portal) | uso dati WHO con termini WHO | **Support** (educazione/report macro) |
| **EFSA OpenFoodTox** (`efsa.europa.eu`) | Hazard chimici alimentari UE | open access | database aperto, download/dashboards | legal notice EFSA, riferimento a output originale | **Support** per risk knowledge |

## 5.2 Provider da NON usare come base free-first
- **Edamam Nutrition API**: piani principalmente a pagamento; free commerciale non adatto come backbone
- **Nutritionix**: tier free pubblico rimosso; trial su richiesta business/research
- **API Ninjas (nutrition endpoint)**: free non commerciale, quindi non adatto come default produzione

## 5.3 Strategia provider

### Stack minimo consigliato (MVP)
1. **USDA FDC** (nutrienti authoritative)
2. **Open Food Facts** (barcode/prodotto reale)
3. **TheMealDB** (ricette)
4. **openFDA food enforcement** (sicurezza/recall)

### Stack esteso (V1.1+)
- Spoonacular/FatSecret come source premium/fallback
- WHO/EFSA come knowledge/regulatory enrichment

---

## 6) Tooling plan (Direct API first)

## 6.1 Nuovi tool proposti (`internal/llm/tools/`)
- `nutrition_usda.go`
- `nutrition_openfoodfacts.go`
- `recipes_mealdb.go`
- `food_safety_openfda.go`

Opzionali:
- `nutrition_spoonacular.go`
- `nutrition_fatsecret.go`

## 6.2 Perché NO MCP per MVP
- API endpoint noti e stabili
- overhead token/costo inferiore con Direct API
- latenza inferiore e controllo migliore su retry/rate-limit

## 6.3 Standard operativi tool
- timeout 20–30s, retry con backoff
- rate limiter per provider (token bucket)
- risposta normalizzata JSON strutturato
- error mapping coerente (`NewTextErrorResponse`)

---

## 7) Data model e policy di sicurezza

## 7.1 Input minimo utente (profilo nutrizione)
- età (range), sesso opzionale, peso/altezza opzionali
- obiettivo (dimagrire/mantenimento/massa)
- livello attività
- preferenze alimentari
- allergeni/intolleranze
- vincoli etici/religiosi
- budget e tempo cucina

## 7.2 Guardrail obbligatori
- bloccare claim medici/diagnostici
- disclaimer automatico quando richieste cliniche
- escalation a “consulto professionista” per condizioni mediche
- PII minimization + retention policy memoria

## 7.3 Compliance dati/licenze
- tracciamento `data_source` per ogni risposta
- attribution renderer per provider che lo richiedono
- flag `share_alike_required` per output derivati da ODbL

---

## 8) Piano implementativo per fasi

## Fase N0 — Foundation & contracts (2-3 giorni)
- aggiungere costanti:
  - `contracts.AgencyNutrition`
  - `routing.DomainNutrition`
  - nuove `SkillName` nutrizione in `internal/aria/skill/skill.go`
- estendere config root:
  - `Agencies.Nutrition.Enabled`
- creare config dedicata `internal/aria/config/nutrition.go`

**Gate**: build + vet + test pass

## Fase N1 — Tools MVP (4-6 giorni)
- implementare 4 tool core (USDA, OFF, MealDB, openFDA)
- test unitari tool con mock HTTP

**Gate**: `go test ./internal/llm/tools/...`

## Fase N2 — Skills MVP (4-6 giorni)
- `nutrition_analysis.go`
- `recipe_search.go`
- `diet_plan_generation.go`
- `food_recall_monitoring.go`

**Gate**: test skill + canExecute con verifica config provider

## Fase N3 — Agency & agent bridge (4-6 giorni)
- `internal/aria/agency/nutrition.go`
- bridge agenti e routing skill-based
- memory domain “nutrition”

**Gate**: test integration agency

## Fase N4 — Integrazione orchestrator/app (2-3 giorni)
- wire in `internal/app/aria_integration.go`
- registrazione con orchestrator + agency service
- policy routing per query nutrizione/alimentazione

**Gate**: e2e prompt test in ARIA mode

## Fase N5 — Quality/observability/docs (2-3 giorni)
- metriche: success rate, provider error rate, fallback rate
- update blueprint roadmap/changelog
- documentazione operativa e runbook rate limits

**Gate finale**:
- `go build ./...`
- `go vet ./...`
- `go test ./...`
- smoke test prompt reali alimentazione

---

## 9) File plan (checklist concreta)

### Nuovi file
- `internal/aria/agency/nutrition.go`
- `internal/aria/config/nutrition.go`
- `internal/aria/skill/nutrition_analysis.go`
- `internal/aria/skill/recipe_search.go`
- `internal/aria/skill/diet_plan_generation.go`
- `internal/aria/skill/food_recall_monitoring.go`
- `internal/llm/tools/nutrition_usda.go`
- `internal/llm/tools/nutrition_openfoodfacts.go`
- `internal/llm/tools/recipes_mealdb.go`
- `internal/llm/tools/food_safety_openfda.go`

### File da aggiornare
- `internal/aria/contracts/contracts.go`
- `internal/aria/routing/classifier.go`
- `internal/aria/config/config.go`
- `internal/aria/skill/skill.go`
- `internal/aria/skill/registry.go`
- `internal/app/aria_integration.go`
- `docs/foundation/BLUEPRINT.md` (roadmap + changelog)

---

## 10) Config & env vars proposte

```bash
ARIA_AGENCIES_NUTRITION_ENABLED=true

ARIA_NUTRITION_USDA_API_KEY="..."
ARIA_NUTRITION_OPENFOODFACTS_USER_AGENT="ARIA/1.0 (contact@example.com)"
ARIA_NUTRITION_MEALDB_API_KEY="1"  # dev
ARIA_NUTRITION_OPENFDA_API_KEY="..."  # opzionale ma raccomandata

ARIA_NUTRITION_DEFAULT_LOCALE="it-IT"
ARIA_NUTRITION_DEFAULT_COUNTRY="IT"
ARIA_NUTRITION_MAX_DAILY_PLANS=20
ARIA_NUTRITION_ENABLE_MEDICAL_GUARDRAILS=true
```

---

## 11) Rischi principali e mitigazioni

1. **Rischio medico-legale**
   - Mitigazione: policy non-medical + disclaimer + blocco richieste cliniche

2. **Rate limit/provider outage**
   - Mitigazione: fallback provider + cache breve + circuit breaker

3. **Qualità dati crowdsourced (Open Food Facts)**
   - Mitigazione: confidence score per fonte + cross-check con USDA quando possibile

4. **Conflitti licenza (ODbL share-alike)**
   - Mitigazione: output tagging e regole di riuso esplicite

---

## 12) Next action consigliata (subito eseguibile)

1. Approvare questo piano come **PRD Nutrition Agency** (Milestone 1).  
2. Produrre **TDD tecnico** con design di interfacce tool/skill/agency e test matrix (Milestone 2).  
3. Avviare implementazione Fasi N0→N2 (MVP tecnico) in branch dedicato.

---

## 13) Fonti ufficiali principali usate

- USDA FDC API Guide: https://fdc.nal.usda.gov/api-guide
- api.data.gov rate limits: https://api.data.gov/docs/developer-manual/
- Open Food Facts API docs: https://openfoodfacts.github.io/openfoodfacts-server/api/
- Open Food Facts API conditions: https://support.openfoodfacts.org/help/en-gb/12-api-data-reuse/94-are-there-conditions-to-use-the-api
- TheMealDB API + terms: https://www.themealdb.com/api.php , https://www.themealdb.com/terms_of_use.php
- Spoonacular pricing/docs: https://spoonacular.com/food-api/pricing , https://spoonacular.com/food-api/docs#Quotas
- CalorieNinjas API/pricing: https://calorieninjas.com/api , https://calorieninjas.com/pricing
- FatSecret editions/attribution: https://platform.fatsecret.com/api-editions , https://platform.fatsecret.com/attribution
- openFDA auth/query/food enforcement: https://open.fda.gov/apis/authentication/ , https://open.fda.gov/apis/query-parameters/ , https://open.fda.gov/apis/food/enforcement/
- WHO GHO OData API + Nutrition portal: https://www.who.int/data/gho/info/gho-odata-api , https://platform.who.int/nutrition/nutrition-portals
- EFSA OpenFoodTox: https://www.efsa.europa.eu/en/data-report/chemical-hazards-database-openfoodtox
- Edamam terms/pricing context: https://developer.edamam.com/edamam-nutrition-api , https://www.edamam.com/terms/api
- Nutritionix access policy: https://developer.nutritionix.com/ , https://www.nutritionix.com/request-api-trial
