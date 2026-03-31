// Package agency provides the Agency system - specialized organizations
// of agents for specific domains (development, knowledge, creative, etc.).
package agency

import (
	"fmt"
	"sync"

	"github.com/fulvian/aria/internal/aria/contracts"
	ariaSkill "github.com/fulvian/aria/internal/aria/skill"
)

// ============================================================================
// AGENCY CATALOG - Unica Fonte di Verità per l'Ecosistema Agentico di ARIA
// ============================================================================
//
// Questo catalogo è il registro centrale che censisce TUTTI gli elementi
// agentici di ARIA: Agency, Agent, Skill, Tool, Provider.
//
// Struttura del catalogo:
// - Agencies: tutte le agenzie disponibili (Knowledge, Development, Weather, Nutrition, etc.)
// - Agents: tutti gli agenti per dominio
// - Skills: tutte le skill registrabili
// - Tools: tutti gli strumenti disponibili
// - Providers: tutti i search/data provider per dominio
//
//=============================================================================

//----------------------------------------------------------------------------
// Domain Constants
//----------------------------------------------------------------------------

// Domain rappresenta un dominio specialistico dell'ecosistema ARIA.
type Domain string

const (
	DomainKnowledge    Domain = "knowledge"    // Ricerca, apprendimento, analisi
	DomainDevelopment  Domain = "development"  // Coding, devops, testing
	DomainCreative     Domain = "creative"     // Scrittura, design, arte
	DomainProductivity Domain = "productivity" // Pianificazione, scheduling
	DomainPersonal     Domain = "personal"     // Salute, finanza, lifestyle
	DomainAnalytics    Domain = "analytics"    // Analisi dati, visualizzazione
	DomainNutrition    Domain = "nutrition"    // Nutrizione, ricette, diete
	DomainWeather      Domain = "weather"      // Meteo, previsioni, allerte
)

//----------------------------------------------------------------------------
// Agency Catalog Entry
//----------------------------------------------------------------------------

// AgencyCatalogEntry rappresenta un record nel catalogo delle agenzie.
type AgencyCatalogEntry struct {
	Name          contracts.AgencyName // Identificatore univoco
	Domain        Domain               // Dominio di specializzazione
	Description   string               // Descrizione sintetica
	Enabled       bool                 // Se l'agenzia è attualmente abilitata
	Agents        []AgentCatalogEntry  // Agenti appartenenti a questa agenzia
	Skills        []SkillCatalogEntry  // Skills disponibili in questa agenzia
	ProviderCount int                  // Numero di provider search/data
}

//----------------------------------------------------------------------------
// Agent Catalog Entry
//----------------------------------------------------------------------------

// AgentCatalogEntry rappresenta un record nel catalogo degli agenti.
type AgentCatalogEntry struct {
	Name        contracts.AgentName   // Identificatore univoco
	Agency      contracts.AgencyName  // Agenzia parent
	Domain      Domain                // Dominio di specializzazione
	Role        AgentRole             // Ruolo nell'agenzia
	Skills      []ariaSkill.SkillName // Skills che questo agente può eseguire
	Description string                // Descrizione ruolo
}

// AgentRole rappresenta il ruolo di un agente all'interno dell'agenzia.
type AgentRole string

const (
	RoleResearcher AgentRole = "researcher" // Ricerca e analisi
	RoleEducator   AgentRole = "educator"   // Insegnamento e spiegazione
	RoleAnalyst    AgentRole = "analyst"    // Analisi dati e sintesi
	RoleCoder      AgentRole = "coder"      // Sviluppo codice
	RoleReviewer   AgentRole = "reviewer"   // Code review
	RoleDebuggger  AgentRole = "debugger"   // Debugging
	RolePlanner    AgentRole = "planner"    // Pianificazione
	RoleExecutor   AgentRole = "executor"   // Esecuzione task
)

//----------------------------------------------------------------------------
// Skill Catalog Entry
//----------------------------------------------------------------------------

// SkillCatalogEntry rappresenta un record nel catalogo delle skill.
type SkillCatalogEntry struct {
	Name          ariaSkill.SkillName  // Identificatore univoco
	Domain        Domain               // Dominio di appartenenza
	Description   string               // Descrizione skill
	RequiredTools []ariaSkill.ToolName // Tools richiesti
	RequiredMCPs  []ariaSkill.MCPName  // MCPs richiesti
	Complexity    SkillComplexity      // Complessità implementativa
	Status        SkillStatus          // Stato corrente
}

// SkillComplexity rappresenta la complessità di una skill.
type SkillComplexity string

const (
	ComplexityBasic    SkillComplexity = "basic"    // Skill semplice
	ComplexityStandard SkillComplexity = "standard" // Skill standard
	ComplexityAdvanced SkillComplexity = "advanced" // Skill avanzata
)

// SkillStatus rappresenta lo stato di implementazione di una skill.
type SkillStatus string

const (
	SkillStatusPlanned     SkillStatus = "planned"     // Pianificata
	SkillStatusPrototype   SkillStatus = "prototype"   // Prototipo
	SkillStatusImplemented SkillStatus = "implemented" // Implementata
	SkillStatusBeta        SkillStatus = "beta"        // Beta
	SkillStatusDeprecated  SkillStatus = "deprecated"  // Deprecata
)

//----------------------------------------------------------------------------
// Tool Catalog Entry
//----------------------------------------------------------------------------

// ToolCatalogEntry rappresenta un record nel catalogo dei tool.
type ToolCatalogEntry struct {
	Name        ariaSkill.ToolName // Identificatore univoco
	Domain      Domain             // Dominio di utilizzo
	Description string             // Descrizione funzionalità
	Type        ToolType           // Tipo di tool
	Status      ToolStatus         // Stato implementazione
	Provider    string             // Provider backend
}

// ToolType rappresenta la tipologia di tool.
type ToolType string

const (
	ToolTypeSearch    ToolType = "search"    // Ricerca
	ToolTypeExecution ToolType = "execution" // Esecuzione
	ToolTypeRetrieval ToolType = "retrieval" // Recupero
	ToolTypeAnalysis  ToolType = "analysis"  // Analisi
	ToolTypeTransform ToolType = "transform" // Trasformazione
	ToolTypeExternal  ToolType = "external"  // API/MCP esterne
)

// ToolStatus rappresenta lo stato di implementazione.
type ToolStatus string

const (
	ToolStatusPlanned     ToolStatus = "planned"
	ToolStatusImplemented ToolStatus = "implemented"
	ToolStatusExternal    ToolStatus = "external"
	ToolStatusDeprecated  ToolStatus = "deprecated"
)

//----------------------------------------------------------------------------
// Provider Catalog Entry
//----------------------------------------------------------------------------

// ProviderCatalogEntry rappresenta un record nel catalogo dei provider.
type ProviderCatalogEntry struct {
	Name           string         // Identificatore provider
	Domain         Domain         // Dominio
	Type           ProviderType   // Tipologia provider
	Description    string         // Descrizione
	AuthRequired   bool           // Se richiede autenticazione
	Tier           ProviderTier   // Tier nella catena
	FreeTier       bool           // Se ha tier gratuito
	APIKeyRequired bool           // Se richiede API key
	Status         ProviderStatus // Stato provider
}

// ProviderType rappresenta la tipologia di provider.
type ProviderType string

const (
	ProviderTypeSearch    ProviderType = "search"    // Search engine
	ProviderTypeAcademic  ProviderType = "academic"  // Academic literature
	ProviderTypeArchive   ProviderType = "archive"   // Historical archives
	ProviderTypeNews      ProviderType = "news"      // News feeds
	ProviderTypeKnowledge ProviderType = "knowledge" // Knowledge base
	ProviderTypeMCP       ProviderType = "mcp"       // MCP server
)

// ProviderTier rappresenta il tier nella catena di fallback.
type ProviderTier int

const (
	Tier1Premium     ProviderTier = 1 // Provider premium
	Tier2APIBased    ProviderTier = 2 // Provider API-based
	Tier3Free        ProviderTier = 3 // Provider gratuiti
	Tier4Specialized ProviderTier = 4 // Provider specializzati
	Tier5Fallback    ProviderTier = 5 // Provider fallback
)

// ProviderStatus rappresenta lo stato di un provider.
type ProviderStatus string

const (
	ProviderStatusActive     ProviderStatus = "active"     // Attivo
	ProviderStatusLimited    ProviderStatus = "limited"    // Limitato
	ProviderStatusDeprecated ProviderStatus = "deprecated" // Deprecato
	ProviderStatusRetired    ProviderStatus = "retired"    // Ritirato
)

//----------------------------------------------------------------------------
// Agency Catalog - Registro Centrale
//----------------------------------------------------------------------------

// AgencyCatalog è il registro centrale che censisce tutti gli elementi agentici.
type AgencyCatalog struct {
	mu        sync.RWMutex
	agencies  map[contracts.AgencyName]*AgencyCatalogEntry
	agents    map[contracts.AgentName]*AgentCatalogEntry
	skills    map[ariaSkill.SkillName]*SkillCatalogEntry
	tools     map[ariaSkill.ToolName]*ToolCatalogEntry
	providers map[string]*ProviderCatalogEntry
}

// NewAgencyCatalog crea un nuovo catalogo vuoto.
func NewAgencyCatalog() *AgencyCatalog {
	return &AgencyCatalog{
		agencies:  make(map[contracts.AgencyName]*AgencyCatalogEntry),
		agents:    make(map[contracts.AgentName]*AgentCatalogEntry),
		skills:    make(map[ariaSkill.SkillName]*SkillCatalogEntry),
		tools:     make(map[ariaSkill.ToolName]*ToolCatalogEntry),
		providers: make(map[string]*ProviderCatalogEntry),
	}
}

//----------------------------------------------------------------------------
// Agency Catalog - Metodi di Registrazione
//----------------------------------------------------------------------------

// RegisterAgency registra un'agenzia nel catalogo.
func (c *AgencyCatalog) RegisterAgency(entry *AgencyCatalogEntry) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if _, exists := c.agencies[entry.Name]; exists {
		return fmt.Errorf("agency already registered: %s", entry.Name)
	}
	c.agencies[entry.Name] = entry
	return nil
}

// RegisterAgent registra un agente nel catalogo.
func (c *AgencyCatalog) RegisterAgent(entry *AgentCatalogEntry) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if _, exists := c.agents[entry.Name]; exists {
		return fmt.Errorf("agent already registered: %s", entry.Name)
	}
	c.agents[entry.Name] = entry
	return nil
}

// RegisterSkill registra una skill nel catalogo.
func (c *AgencyCatalog) RegisterSkill(entry *SkillCatalogEntry) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if _, exists := c.skills[entry.Name]; exists {
		return fmt.Errorf("skill already registered: %s", entry.Name)
	}
	c.skills[entry.Name] = entry
	return nil
}

// RegisterTool registra un tool nel catalogo.
func (c *AgencyCatalog) RegisterTool(entry *ToolCatalogEntry) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if _, exists := c.tools[entry.Name]; exists {
		return fmt.Errorf("tool already registered: %s", entry.Name)
	}
	c.tools[entry.Name] = entry
	return nil
}

// RegisterProvider registra un provider nel catalogo.
func (c *AgencyCatalog) RegisterProvider(entry *ProviderCatalogEntry) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if _, exists := c.providers[entry.Name]; exists {
		return fmt.Errorf("provider already registered: %s", entry.Name)
	}
	c.providers[entry.Name] = entry
	return nil
}

//----------------------------------------------------------------------------
// Agency Catalog - Metodi di Interrogazione
//----------------------------------------------------------------------------

// GetAgency restituisce un'agenzia dal catalogo.
func (c *AgencyCatalog) GetAgency(name contracts.AgencyName) (*AgencyCatalogEntry, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entry, exists := c.agencies[name]
	if !exists {
		return nil, fmt.Errorf("agency not found: %s", name)
	}
	return entry, nil
}

// GetAgent restituisce un agente dal catalogo.
func (c *AgencyCatalog) GetAgent(name contracts.AgentName) (*AgentCatalogEntry, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entry, exists := c.agents[name]
	if !exists {
		return nil, fmt.Errorf("agent not found: %s", name)
	}
	return entry, nil
}

// GetSkill restituisce una skill dal catalogo.
func (c *AgencyCatalog) GetSkill(name ariaSkill.SkillName) (*SkillCatalogEntry, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entry, exists := c.skills[name]
	if !exists {
		return nil, fmt.Errorf("skill not found: %s", name)
	}
	return entry, nil
}

// GetTool restituisce un tool dal catalogo.
func (c *AgencyCatalog) GetTool(name ariaSkill.ToolName) (*ToolCatalogEntry, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entry, exists := c.tools[name]
	if !exists {
		return nil, fmt.Errorf("tool not found: %s", name)
	}
	return entry, nil
}

// GetProvider restituisce un provider dal catalogo.
func (c *AgencyCatalog) GetProvider(name string) (*ProviderCatalogEntry, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entry, exists := c.providers[name]
	if !exists {
		return nil, fmt.Errorf("provider not found: %s", name)
	}
	return entry, nil
}

//----------------------------------------------------------------------------
// Agency Catalog - Liste Complete
//----------------------------------------------------------------------------

// ListAgencies restituisce tutte le agenzie registrate.
func (c *AgencyCatalog) ListAgencies() []*AgencyCatalogEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make([]*AgencyCatalogEntry, 0, len(c.agencies))
	for _, entry := range c.agencies {
		result = append(result, entry)
	}
	return result
}

// ListAgents restituisce tutti gli agenti registrati.
func (c *AgencyCatalog) ListAgents() []*AgentCatalogEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make([]*AgentCatalogEntry, 0, len(c.agents))
	for _, entry := range c.agents {
		result = append(result, entry)
	}
	return result
}

// ListAgentsByDomain restituisce gli agenti di un dato dominio.
func (c *AgencyCatalog) ListAgentsByDomain(domain Domain) []*AgentCatalogEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make([]*AgentCatalogEntry, 0)
	for _, entry := range c.agents {
		if entry.Domain == domain {
			result = append(result, entry)
		}
	}
	return result
}

// ListSkills restituisce tutte le skill registrate.
func (c *AgencyCatalog) ListSkills() []*SkillCatalogEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make([]*SkillCatalogEntry, 0, len(c.skills))
	for _, entry := range c.skills {
		result = append(result, entry)
	}
	return result
}

// ListSkillsByDomain restituisce le skill di un dato dominio.
func (c *AgencyCatalog) ListSkillsByDomain(domain Domain) []*SkillCatalogEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make([]*SkillCatalogEntry, 0)
	for _, entry := range c.skills {
		if entry.Domain == domain {
			result = append(result, entry)
		}
	}
	return result
}

// ListProviders restituisce tutti i provider registrati.
func (c *AgencyCatalog) ListProviders() []*ProviderCatalogEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make([]*ProviderCatalogEntry, 0, len(c.providers))
	for _, entry := range c.providers {
		result = append(result, entry)
	}
	return result
}

// ListProvidersByDomain restituisce i provider di un dato dominio.
func (c *AgencyCatalog) ListProvidersByDomain(domain Domain) []*ProviderCatalogEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make([]*ProviderCatalogEntry, 0)
	for _, entry := range c.providers {
		if entry.Domain == domain {
			result = append(result, entry)
		}
	}
	return result
}

// ListProvidersByTier restituisce i provider di un dato tier.
func (c *AgencyCatalog) ListProvidersByTier(tier ProviderTier) []*ProviderCatalogEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make([]*ProviderCatalogEntry, 0)
	for _, entry := range c.providers {
		if entry.Tier == tier {
			result = append(result, entry)
		}
	}
	return result
}

//----------------------------------------------------------------------------
// Agency Catalog - Bootstrap
//----------------------------------------------------------------------------

// BootstrapDefaultCatalog popola il catalogo con le implementazioni di default.
func BootstrapDefaultCatalog(c *AgencyCatalog) error {

	// =====================================================================
	// KNOWLEDGE AGENCY - Provider
	// =====================================================================

	// --- Knowledge Providers ---
	providers := []*ProviderCatalogEntry{
		// Tier 1: Premium
		{Name: "tavily", Domain: DomainKnowledge, Type: ProviderTypeSearch, Description: "Tavily AI Search API", AuthRequired: true, Tier: Tier1Premium, FreeTier: false, APIKeyRequired: true, Status: ProviderStatusActive},
		{Name: "brave", Domain: DomainKnowledge, Type: ProviderTypeSearch, Description: "Brave Search API", AuthRequired: true, Tier: Tier1Premium, FreeTier: false, APIKeyRequired: true, Status: ProviderStatusActive},

		// Tier 2: API-based
		{Name: "bing", Domain: DomainKnowledge, Type: ProviderTypeSearch, Description: "Bing Search API (RETIRED)", AuthRequired: true, Tier: Tier2APIBased, FreeTier: false, APIKeyRequired: true, Status: ProviderStatusRetired},

		// Tier 3: Free Search
		{Name: "ddg", Domain: DomainKnowledge, Type: ProviderTypeSearch, Description: "DuckDuckGo", AuthRequired: false, Tier: Tier3Free, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},
		{Name: "wikipedia", Domain: DomainKnowledge, Type: ProviderTypeKnowledge, Description: "Wikipedia API", AuthRequired: false, Tier: Tier3Free, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},

		// Tier 4: Academic Free
		{Name: "pubmed", Domain: DomainKnowledge, Type: ProviderTypeAcademic, Description: "PubMed biomedical literature", AuthRequired: false, Tier: Tier4Specialized, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},
		{Name: "arxiv", Domain: DomainKnowledge, Type: ProviderTypeAcademic, Description: "arXiv preprints", AuthRequired: false, Tier: Tier4Specialized, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},
		{Name: "semanticscholar", Domain: DomainKnowledge, Type: ProviderTypeAcademic, Description: "Semantic Scholar AI academic search", AuthRequired: false, Tier: Tier4Specialized, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},
		{Name: "openalex", Domain: DomainKnowledge, Type: ProviderTypeAcademic, Description: "OpenAlex 250M+ papers, citation graph", AuthRequired: false, Tier: Tier4Specialized, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},
		{Name: "gdelt", Domain: DomainKnowledge, Type: ProviderTypeNews, Description: "GDELT global events and news monitoring", AuthRequired: false, Tier: Tier4Specialized, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},

		// Tier 4: Premium Academic
		{Name: "valyu", Domain: DomainKnowledge, Type: ProviderTypeAcademic, Description: "Valyu semantic search (full-text arXiv)", AuthRequired: true, Tier: Tier4Specialized, FreeTier: false, APIKeyRequired: true, Status: ProviderStatusActive},
		{Name: "crossref", Domain: DomainKnowledge, Type: ProviderTypeAcademic, Description: "CrossRef DOI/citations", AuthRequired: false, Tier: Tier4Specialized, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},
		{Name: "bgpt", Domain: DomainKnowledge, Type: ProviderTypeAcademic, Description: "BGPT structured experimental data", AuthRequired: true, Tier: Tier4Specialized, FreeTier: false, APIKeyRequired: true, Status: ProviderStatusActive},

		// Tier 5: Archive/Historical
		{Name: "wayback", Domain: DomainKnowledge, Type: ProviderTypeArchive, Description: "Wayback Machine historical snapshots", AuthRequired: false, Tier: Tier5Fallback, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},
		{Name: "jina", Domain: DomainKnowledge, Type: ProviderTypeArchive, Description: "Jina Reader URL→markdown extraction", AuthRequired: false, Tier: Tier5Fallback, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},
		{Name: "youcom", Domain: DomainKnowledge, Type: ProviderTypeSearch, Description: "You.com LLM-optimized search", AuthRequired: true, Tier: Tier5Fallback, FreeTier: false, APIKeyRequired: true, Status: ProviderStatusActive},
		{Name: "context7", Domain: DomainKnowledge, Type: ProviderTypeKnowledge, Description: "Context7 library documentation", AuthRequired: true, Tier: Tier5Fallback, FreeTier: true, APIKeyRequired: true, Status: ProviderStatusActive},

		// News Archive Providers
		{Name: "thenewsapi", Domain: DomainKnowledge, Type: ProviderTypeNews, Description: "The News API - 100% free, 40k+ sources", AuthRequired: true, Tier: Tier4Specialized, FreeTier: true, APIKeyRequired: true, Status: ProviderStatusActive},
		{Name: "newsdata", Domain: DomainKnowledge, Type: ProviderTypeNews, Description: "NewsData.io - 7 years historical", AuthRequired: true, Tier: Tier4Specialized, FreeTier: true, APIKeyRequired: true, Status: ProviderStatusActive},
		{Name: "gnews", Domain: DomainKnowledge, Type: ProviderTypeNews, Description: "GNews - 6 years historical, 80k+ sources", AuthRequired: true, Tier: Tier4Specialized, FreeTier: true, APIKeyRequired: true, Status: ProviderStatusActive},
		{Name: "chroniclingamerica", Domain: DomainKnowledge, Type: ProviderTypeArchive, Description: "Chronicling America - historic US newspapers 1756-1963", AuthRequired: false, Tier: Tier4Specialized, FreeTier: true, APIKeyRequired: false, Status: ProviderStatusActive},
	}

	for _, p := range providers {
		if err := c.RegisterProvider(p); err != nil {
			return fmt.Errorf("failed to register provider %s: %w", p.Name, err)
		}
	}

	// --- Knowledge Agency Entry ---
	knowledgeAgency := &AgencyCatalogEntry{
		Name:        contracts.AgencyKnowledge,
		Domain:      DomainKnowledge,
		Description: "Research, learning, Q&A, analysis, and general knowledge tasks",
		Enabled:     true,
		Agents: []AgentCatalogEntry{
			{Name: "researcher", Agency: contracts.AgencyKnowledge, Domain: DomainKnowledge, Role: RoleResearcher, Skills: []ariaSkill.SkillName{ariaSkill.SkillWebResearch, ariaSkill.SkillFactCheck}, Description: "Research agent for web searches and fact verification"},
			{Name: "educator", Agency: contracts.AgencyKnowledge, Domain: DomainKnowledge, Role: RoleEducator, Skills: []ariaSkill.SkillName{ariaSkill.SkillSummarization}, Description: "Educational agent for teaching and explanation"},
			{Name: "analyst", Agency: contracts.AgencyKnowledge, Domain: DomainKnowledge, Role: RoleAnalyst, Skills: []ariaSkill.SkillName{ariaSkill.SkillDataAnalysis}, Description: "Analysis agent for data synthesis and comparison"},
		},
		Skills: []SkillCatalogEntry{
			{Name: ariaSkill.SkillWebResearch, Domain: DomainKnowledge, Description: "Performs web research using search providers", Status: SkillStatusImplemented},
			{Name: ariaSkill.SkillDocAnalysis, Domain: DomainKnowledge, Description: "Document analysis and extraction", Status: SkillStatusPlanned},
			{Name: ariaSkill.SkillFactCheck, Domain: DomainKnowledge, Description: "Fact-checking and verification", Status: SkillStatusPlanned},
		},
		ProviderCount: len(providers),
	}
	if err := c.RegisterAgency(knowledgeAgency); err != nil {
		return fmt.Errorf("failed to register knowledge agency: %w", err)
	}

	// =====================================================================
	// DEVELOPMENT AGENCY
	// =====================================================================
	devAgency := &AgencyCatalogEntry{
		Name:        contracts.AgencyDevelopment,
		Domain:      DomainDevelopment,
		Description: "Coding, devops, testing, and software development tasks",
		Enabled:     true,
		Skills: []SkillCatalogEntry{
			{Name: ariaSkill.SkillCodeReview, Domain: DomainDevelopment, Description: "Code review and quality assessment", Status: SkillStatusImplemented},
			{Name: ariaSkill.SkillTDD, Domain: DomainDevelopment, Description: "Test-driven development", Status: SkillStatusImplemented},
			{Name: ariaSkill.SkillDebugging, Domain: DomainDevelopment, Description: "Systematic debugging and problem solving", Status: SkillStatusImplemented},
			{Name: ariaSkill.SkillRefactoring, Domain: DomainDevelopment, Description: "Code refactoring and optimization", Status: SkillStatusPlanned},
		},
		ProviderCount: 0,
	}
	if err := c.RegisterAgency(devAgency); err != nil {
		return fmt.Errorf("failed to register development agency: %w", err)
	}

	// =====================================================================
	// WEATHER AGENCY
	// =====================================================================
	weatherAgency := &AgencyCatalogEntry{
		Name:        contracts.AgencyWeather,
		Domain:      DomainWeather,
		Description: "Weather forecasting, alerts, and meteorological data",
		Enabled:     true,
		Skills: []SkillCatalogEntry{
			{Name: ariaSkill.SkillWeatherCurrent, Domain: DomainWeather, Description: "Current weather conditions", Status: SkillStatusImplemented},
			{Name: ariaSkill.SkillWeatherForecast, Domain: DomainWeather, Description: "Weather forecasting", Status: SkillStatusImplemented},
			{Name: ariaSkill.SkillWeatherAlerts, Domain: DomainWeather, Description: "Weather alerts and warnings", Status: SkillStatusImplemented},
		},
		ProviderCount: 0,
	}
	if err := c.RegisterAgency(weatherAgency); err != nil {
		return fmt.Errorf("failed to register weather agency: %w", err)
	}

	// =====================================================================
	// NUTRITION AGENCY
	// =====================================================================
	nutritionAgency := &AgencyCatalogEntry{
		Name:        contracts.AgencyNutrition,
		Domain:      DomainNutrition,
		Description: "Nutrition, recipes, diet planning, and food monitoring",
		Enabled:     true,
		Skills: []SkillCatalogEntry{
			{Name: ariaSkill.SkillRecipeSearch, Domain: DomainNutrition, Description: "Recipe search and recommendations", Status: SkillStatusImplemented},
			{Name: ariaSkill.SkillNutritionAnalysis, Domain: DomainNutrition, Description: "Nutritional analysis of foods", Status: SkillStatusImplemented},
			{Name: ariaSkill.SkillDietPlanGeneration, Domain: DomainNutrition, Description: "Personalized diet plan generation", Status: SkillStatusImplemented},
			{Name: ariaSkill.SkillFoodRecallMonitoring, Domain: DomainNutrition, Description: "Food recall and safety monitoring", Status: SkillStatusImplemented},
		},
		ProviderCount: 0,
	}
	if err := c.RegisterAgency(nutritionAgency); err != nil {
		return fmt.Errorf("failed to register nutrition agency: %w", err)
	}

	return nil
}

//----------------------------------------------------------------------------
// Catalog Statistics
//----------------------------------------------------------------------------

// CatalogStats contiene statistiche riassuntive del catalogo.
type CatalogStats struct {
	TotalAgencies   int `json:"total_agencies"`
	TotalAgents     int `json:"total_agents"`
	TotalSkills     int `json:"total_skills"`
	TotalTools      int `json:"total_tools"`
	TotalProviders  int `json:"total_providers"`
	ActiveProviders int `json:"active_providers"`
	FreeProviders   int `json:"free_providers"`
}

// GetStats restituisce statistiche riassuntive del catalogo.
func (c *AgencyCatalog) GetStats() CatalogStats {
	c.mu.RLock()
	defer c.mu.RUnlock()

	stats := CatalogStats{
		TotalAgencies:  len(c.agencies),
		TotalAgents:    len(c.agents),
		TotalSkills:    len(c.skills),
		TotalTools:     len(c.tools),
		TotalProviders: len(c.providers),
	}

	for _, p := range c.providers {
		if p.Status == ProviderStatusActive {
			stats.ActiveProviders++
		}
		if p.FreeTier {
			stats.FreeProviders++
		}
	}

	return stats
}
