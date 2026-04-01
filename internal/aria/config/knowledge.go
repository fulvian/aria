// Package config provides ARIA-specific configuration for knowledge agency.
package config

// KnowledgeConfig defines configuration for the Knowledge Agency.
type KnowledgeConfig struct {
	Enabled bool

	// DefaultProvider is the default search provider: "tavily", "brave", "ddg", "bing", "wikipedia"
	DefaultProvider string

	// Provider API keys
	TavilyAPIKey string
	BraveAPIKey  string
	BingAPIKey   string // Bing Search API (free tier available)

	// Search settings
	MaxSearchResults int
	SearchTimeoutMs  int
	MaxRetries       int
	RetryBaseDelayMs int

	// Memory integration
	EnableMemory bool
	MemoryTopK   int
	SaveEpisodes bool
	SaveFacts    bool

	// Feature flags (free providers enabled by default)
	EnableWikipedia   bool
	EnableDDG         bool // DuckDuckGo free search
	EnableBing        bool // Bing Search API (free tier available)
	EnableDocumentPDF bool

	// Academic/Scientific search providers (free!)
	EnablePubMed          bool // PubMed biomedical literature
	EnableArXiv           bool // arXiv preprint repository
	EnableSemanticScholar bool // Semantic Scholar academic search
	EnableOpenAlex        bool // OpenAlex 250M+ papers (free, no API key)
	EnableGDELT           bool // GDELT news/events monitoring (free)

	// Historical/Archive providers (free!)
	EnableWayback bool // Wayback Machine historical snapshots
	EnableJina    bool // Jina Reader URL→markdown extraction (free)

	// Premium academic providers (require API keys)
	EnableValyu    bool   // Valyu semantic search (full-text arXiv)
	ValyuAPIKey    string // Valyu API key (get free credits at platform.valyu.ai)
	EnableCrossRef bool   // CrossRef DOI/citations
	CrossRefEmail  string // CrossRef polite pool email (required by CrossRef)
	EnableBGPT     bool   // BGPT structured experimental data
	BGPTAPIKey     string // BGPT API key

	// LLM-optimized search providers
	EnableYouCom bool   // You.com LLM-optimized search
	YouComAPIKey string // You.com API key (free tier available)

	// Documentation search providers
	EnableContext7 bool   // Context7 library documentation search (free tier)
	Context7APIKey string // Context7 API key

	// News/Historical archive providers (free tier)
	EnableTheNewsAPI         bool   // The News API - 100% free, 40k+ sources
	TheNewsAPIAPIKey         string // The News API key (get free at thenewsapi.com)
	EnableNewsData           bool   // NewsData.io - 7 years historical news
	NewsDataAPIKey           string // NewsData.io API key (get free at newsdata.io)
	EnableGNews              bool   // GNews - 6 years historical, 80k+ sources
	GNewsAPIKey              string // GNews API key (get free at gnews.io)
	EnableChroniclingAmerica bool   // Chronicling America - historic US newspapers 1756-1963 (NO KEY NEEDED)

	// Localization
	DefaultLanguage string
	DefaultRegion   string
}

// IsConfigured returns true if the knowledge agency is properly configured.
func (c KnowledgeConfig) IsConfigured() bool {
	if !c.Enabled {
		return false
	}
	switch c.DefaultProvider {
	case "tavily":
		return c.TavilyAPIKey != ""
	case "brave":
		return c.BraveAPIKey != ""
	case "bing":
		return c.BingAPIKey != ""
	case "ddg", "wikipedia", "pubmed", "arxiv", "semanticscholar", "semantic_scholar", "valyu", "crossref", "bgpt", "openalex", "gdelt", "wayback", "jina":
		return true
	case "youcom":
		return c.EnableYouCom && c.YouComAPIKey != ""
	case "context7":
		return c.EnableContext7 && c.Context7APIKey != ""
	case "thenewsapi":
		return c.EnableTheNewsAPI && c.TheNewsAPIAPIKey != ""
	case "newsdata":
		return c.EnableNewsData && c.NewsDataAPIKey != ""
	case "gnews":
		return c.EnableGNews && c.GNewsAPIKey != ""
	case "chroniclingamerica":
		return c.EnableChroniclingAmerica // No API key needed
	default:
		return false
	}
}

// DefaultKnowledgeConfig returns sensible defaults for knowledge agency configuration.
// SECURITY: API keys must be provided via environment variables, never hardcoded.
func DefaultKnowledgeConfig() KnowledgeConfig {
	return KnowledgeConfig{
		Enabled:           getEnvBool("ARIA_AGENCIES_KNOWLEDGE_ENABLED", true), // Enabled by default
		DefaultProvider:   getEnv("ARIA_KNOWLEDGE_DEFAULT_PROVIDER", "ddg"),    // DDG is free, no API key needed
		TavilyAPIKey:      getEnv("ARIA_KNOWLEDGE_TAVILY_API_KEY", ""),         // Must be set via env var
		BraveAPIKey:       getEnv("ARIA_KNOWLEDGE_BRAVE_API_KEY", ""),          // Must be set via env var
		BingAPIKey:        getEnv("ARIA_KNOWLEDGE_BING_API_KEY", ""),           // DEPRECATED - Bing Search API retired Mar 2025
		MaxSearchResults:  getEnvInt("ARIA_KNOWLEDGE_MAX_SEARCH_RESULTS", 10),
		SearchTimeoutMs:   getEnvInt("ARIA_KNOWLEDGE_SEARCH_TIMEOUT_MS", 30000),
		MaxRetries:        getEnvInt("ARIA_KNOWLEDGE_MAX_RETRIES", 2),
		RetryBaseDelayMs:  getEnvInt("ARIA_KNOWLEDGE_RETRY_BASE_DELAY_MS", 300),
		EnableMemory:      getEnvBool("ARIA_KNOWLEDGE_ENABLE_MEMORY", true),
		MemoryTopK:        getEnvInt("ARIA_KNOWLEDGE_MEMORY_TOP_K", 5),
		SaveEpisodes:      getEnvBool("ARIA_KNOWLEDGE_SAVE_EPISODES", true),
		SaveFacts:         getEnvBool("ARIA_KNOWLEDGE_SAVE_FACTS", true),
		EnableWikipedia:   getEnvBool("ARIA_KNOWLEDGE_ENABLE_WIKIPEDIA", true),
		EnableDDG:         getEnvBool("ARIA_KNOWLEDGE_ENABLE_DDG", true),   // Enabled by default (free!)
		EnableBing:        getEnvBool("ARIA_KNOWLEDGE_ENABLE_BING", false), // DISABLED - Bing Search API retired Mar 2025
		EnableDocumentPDF: getEnvBool("ARIA_KNOWLEDGE_ENABLE_DOCUMENT_PDF", false),
		// Academic providers (free!)
		EnablePubMed:          getEnvBool("ARIA_KNOWLEDGE_ENABLE_PUBMED", true),
		EnableArXiv:           getEnvBool("ARIA_KNOWLEDGE_ENABLE_ARXIV", true),
		EnableSemanticScholar: getEnvBool("ARIA_KNOWLEDGE_ENABLE_SEMANTIC_SCHOLAR", true),
		// Premium academic providers
		EnableValyu:    getEnvBool("ARIA_KNOWLEDGE_ENABLE_VALYU", false),
		ValyuAPIKey:    getEnv("ARIA_KNOWLEDGE_VALYU_API_KEY", ""),
		EnableCrossRef: getEnvBool("ARIA_KNOWLEDGE_ENABLE_CROSSREF", false),
		CrossRefEmail:  getEnv("ARIA_KNOWLEDGE_CROSSREF_EMAIL", "aria@example.com"),
		EnableBGPT:     getEnvBool("ARIA_KNOWLEDGE_ENABLE_BGPT", false),
		BGPTAPIKey:     getEnv("ARIA_KNOWLEDGE_BGPT_API_KEY", ""),
		// New free providers
		EnableOpenAlex: getEnvBool("ARIA_KNOWLEDGE_ENABLE_OPENALEX", true), // Free, 250M+ papers
		EnableGDELT:    getEnvBool("ARIA_KNOWLEDGE_ENABLE_GDELT", true),    // Free news/events
		EnableWayback:  getEnvBool("ARIA_KNOWLEDGE_ENABLE_WAYBACK", true),  // Free historical
		EnableJina:     getEnvBool("ARIA_KNOWLEDGE_ENABLE_JINA", true),     // Free URL extraction
		EnableYouCom:   getEnvBool("ARIA_KNOWLEDGE_ENABLE_YOUCOM", false),  // Requires API key
		YouComAPIKey:   getEnv("ARIA_KNOWLEDGE_YOUCOM_API_KEY", ""),
		EnableContext7: getEnvBool("ARIA_KNOWLEDGE_ENABLE_CONTEXT7", true), // Free tier available
		Context7APIKey: getEnv("ARIA_KNOWLEDGE_CONTEXT7_API_KEY", ""),      // Must be set via env var
		// News archive providers (free tier)
		EnableTheNewsAPI:         getEnvBool("ARIA_KNOWLEDGE_ENABLE_THENEWSAPI", true),         // 100% free!
		TheNewsAPIAPIKey:         getEnv("ARIA_KNOWLEDGE_THENEWSAPI_API_KEY", ""),              // Must be set via env var
		EnableNewsData:           getEnvBool("ARIA_KNOWLEDGE_ENABLE_NEWDATA", true),            // 7 years historical
		NewsDataAPIKey:           getEnv("ARIA_KNOWLEDGE_NEWDATA_API_KEY", ""),                 // Must be set via env var
		EnableGNews:              getEnvBool("ARIA_KNOWLEDGE_ENABLE_GNEWS", true),              // 6 years historical
		GNewsAPIKey:              getEnv("ARIA_KNOWLEDGE_GNEWS_API_KEY", ""),                   // Must be set via env var
		EnableChroniclingAmerica: getEnvBool("ARIA_KNOWLEDGE_ENABLE_CHRONICLINGAMERICA", true), // NO KEY NEEDED
		DefaultLanguage:          getEnv("ARIA_KNOWLEDGE_DEFAULT_LANGUAGE", "en"),
		DefaultRegion:            getEnv("ARIA_KNOWLEDGE_DEFAULT_REGION", "US"),
	}
}
