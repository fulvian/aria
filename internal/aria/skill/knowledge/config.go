// Package knowledge provides common types for the knowledge agency.
package knowledge

// AgencyConfig holds configuration for the knowledge agency.
type AgencyConfig struct {
	Enabled           bool
	DefaultProvider   string
	TavilyAPIKey      string
	BraveAPIKey       string
	BingAPIKey        string // Bing Search API (free tier available)
	MaxSearchResults  int
	SearchTimeoutMs   int
	MaxRetries        int
	RetryBaseDelayMs  int
	EnableMemory      bool
	MemoryTopK        int
	SaveEpisodes      bool
	SaveFacts         bool
	EnableWikipedia   bool
	EnableDDG         bool // DuckDuckGo free search
	EnableBing        bool // Bing Search API
	EnableDocumentPDF bool // PDF document processing
	DefaultLanguage   string
	DefaultRegion     string
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
	ValyuAPIKey    string // Valyu API key
	EnableCrossRef bool   // CrossRef DOI/citations
	CrossRefEmail  string // CrossRef polite pool email (required)
	EnableBGPT     bool   // BGPT structured experimental data
	BGPTAPIKey     string // BGPT API key

	// LLM-optimized search providers
	EnableYouCom bool   // You.com LLM-optimized search
	YouComAPIKey string // You.com API key

	// Documentation search providers
	EnableContext7 bool   // Context7 library documentation search
	Context7APIKey string // Context7 API key

	// News/Historical archive providers (free tier)
	EnableTheNewsAPI         bool   // The News API - 100% free, 40k+ sources
	TheNewsAPIAPIKey         string // The News API key
	EnableNewsData           bool   // NewsData.io - 7 years historical
	NewsDataAPIKey           string // NewsData.io API key
	EnableGNews              bool   // GNews - 6 years historical, 80k+ sources
	GNewsAPIKey              string // GNews API key
	EnableChroniclingAmerica bool   // Chronicling America - historic US newspapers 1756-1963 (NO KEY NEEDED)
}

// SearchRequest represents a search request to a provider.
type SearchRequest struct {
	Query      string
	MaxResults int
	Language   string
	Region     string
}

// SearchResponse represents a response from a search provider.
type SearchResponse struct {
	Results   []SearchResult
	Sources   []string
	Citations []string
	Summary   string
	Error     string
}

// SearchResult represents a single search result.
type SearchResult struct {
	Title       string
	URL         string
	Description string
	Content     string
	PublishedAt string
}

// ErrorType represents the type of error encountered.
type ErrorType string

const (
	ErrorTypeAuth        ErrorType = "auth"
	ErrorTypeRateLimit   ErrorType = "rate_limit"
	ErrorTypeNetwork     ErrorType = "network"
	ErrorTypeTimeout     ErrorType = "timeout"
	ErrorTypeInvalidResp ErrorType = "invalid_response"
)

// ProviderError represents an error from a search provider.
type ProviderError struct {
	Type        ErrorType
	Message     string
	Recoverable bool
}
