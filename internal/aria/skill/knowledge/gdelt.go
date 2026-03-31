package knowledge

import (
	"context"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// GDELTProvider implements SearchProvider for GDELT API.
// GDELT (Global Database of Events, Language, and Tone) monitors world events
// from news sources in 100+ languages across the globe.
//
// NOTE: GDELT API is slow (16+ seconds response time) and requires custom HTTP
// client with longer TLS handshake timeout. Default http.DefaultClient times out.
type GDELTProvider struct {
	timeout time.Duration
	baseURL string
	apiKey  string // Optional GDELT API key for higher limits
	client  *http.Client
}

// GDELTEvent represents an event in the GDELT database.
type GDELTEvent struct {
	GlobalEventID        string
	Day                  string
	MonthYear            string
	Year                 string
	Actor1Code           string
	Actor1Name           string
	Actor1CountryCode    string
	Actor1KnownGroupCode string
	Actor1Type1Code      string
	Actor2Code           string
	Actor2Name           string
	Actor2CountryCode    string
	Actor2KnownGroupCode string
	Actor2Type1Code      string
	IsRootEvent          string
	EventCode            string
	EventBaseCode        string
	EventRootCode        string
	QuadClass            string
	GoldsteinScale       string
	NumMentions          string
	NumSources           string
	NumArticles          string
	AvgTone              string
	Actor1GeoType        string
	Actor1GeoFullName    string
	Actor1GeoCountryCode string
	Actor1GeoADM1Code    string
	Actor1GeoADM2Code    string
	Actor1GeoLat         string
	Actor1GeoLong        string
	Actor2GeoType        string
	Actor2GeoFullName    string
	Actor2GeoCountryCode string
	Actor2GeoADM1Code    string
	Actor2GeoADM2Code    string
	Actor2GeoLat         string
	Actor2GeoLong        string
	DateAdded            string
	URL                  string
	SourceURL            string
}

// GDELTEventResponse represents the API response.
type GDELTEventResponse struct {
	Events  []GDELTEvent `json:"events"`
	Format  string       `json:"format"`
	Preview string       `json:"preview"`
}

// GDELTTranslation represents translation data.
type GDELTTranslation struct {
	TranslatedText string `json:"translatedText"`
	DetectedSource string `json:"detectedSource"`
}

// GDELTDocResponse represents the DOC 2.0 API response for full-text article search.
type GDELTDocResponse struct {
	Articles []GDELTArticle `json:"articles"`
}

// GDELTArticle represents a single article from GDELT DOC API.
type GDELTArticle struct {
	URL           string `json:"url"`
	Title         string `json:"title"`
	PublishDate   string `json:"seendate"`
	SourceCountry string `json:"sourcecountry"`
	Language      string `json:"language"`
	Domain        string `json:"domain"`
}

// NewGDELTProvider creates a new GDELT provider.
// GDELT is free but has slow response times (16+ seconds).
// Uses custom HTTP client with extended timeouts.
func NewGDELTProvider(timeout time.Duration) *GDELTProvider {
	return &GDELTProvider{
		timeout: timeout,
		baseURL: "https://api.gdeltproject.org/api/v2",
		client:  newGDELTHTTPClient(timeout),
	}
}

// NewGDELTProviderWithKey creates a GDELT provider with API key.
func NewGDELTProviderWithKey(apiKey string, timeout time.Duration) *GDELTProvider {
	return &GDELTProvider{
		timeout: timeout,
		baseURL: "https://api.gdeltproject.org/api/v2",
		apiKey:  apiKey,
		client:  newGDELTHTTPClient(timeout),
	}
}

// newGDELTHTTPClient creates an HTTP client with extended timeouts for GDELT's slow API.
// GDELT can take 50+ seconds to respond, so we use the full timeout for all operations.
func newGDELTHTTPClient(timeout time.Duration) *http.Client {
	return &http.Client{
		Transport: &http.Transport{
			TLSHandshakeTimeout:   timeout,
			ResponseHeaderTimeout: timeout,
			IdleConnTimeout:       90 * time.Second,
		},
	}
}

// Name returns the provider name.
func (p *GDELTProvider) Name() string {
	return "gdelt"
}

// IsConfigured returns true - GDELT requires no API key for basic usage.
func (p *GDELTProvider) IsConfigured() bool {
	return true
}

// Search performs a search using GDELT DOC 2.0 API.
//
// GDELT has NO official rate limits documented, but responses are slow (16+ seconds).
// The custom HTTP client handles TLS handshake and response timeouts.
// Retries only on actual 429 (Too Many Requests) responses.
func (p *GDELTProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	maxResults := req.MaxResults
	if maxResults == 0 {
		maxResults = 50
	}
	if maxResults > 250 {
		maxResults = 250
	}

	// Build query - GDELT DOC 2.0 API uses /doc/doc endpoint
	query := url.QueryEscape(req.Query)
	urlStr := fmt.Sprintf("%s/doc/doc?query=%s&mode=artlist&maxrecords=%d&format=json",
		p.baseURL, query, maxResults)

	if p.apiKey != "" {
		urlStr += "&key=" + p.apiKey
	}

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0")

	// Use custom client with extended timeouts (not http.DefaultClient)
	resp, err := p.client.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("GDELT request failed: %w", err)
	}
	defer resp.Body.Close()

	// Check for rate limiting (429) - retry is NOT automatic, let caller handle fallback
	if resp.StatusCode == http.StatusTooManyRequests {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("GDELT rate limited: %s", string(respBody))
	}

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("GDELT unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse JSON response
	var gdeltResp map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&gdeltResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse GDELT response: %w", err)
	}

	// Extract articles from response
	results := make([]SearchResult, 0)
	citations := make([]string, 0)
	sources := make([]string, 0)

	if articles, ok := gdeltResp["articles"].([]interface{}); ok {
		for _, art := range articles {
			if article, ok := art.(map[string]interface{}); ok {
				title := getStringValue(article, "title")
				if title == "" {
					continue
				}

				articleURL := getStringValue(article, "url")
				domain := getStringValue(article, "domain")
				published := getStringValue(article, "seendate")
				socialimage := getStringValue(article, "socialimage")
				language := getStringValue(article, "language")
				sourcecountry := getStringValue(article, "sourcecountry")
				urlMobile := getStringValue(article, "url_mobile")

				desc := fmt.Sprintf("%s | %s | %s", published, domain, language)
				if sourcecountry != "" {
					desc += " | " + sourcecountry
				}

				content := ""
				if socialimage != "" {
					content = fmt.Sprintf("[Image: %s]", socialimage)
				}

				results = append(results, SearchResult{
					Title:       title,
					URL:         articleURL,
					Description: desc,
					Content:     content,
					PublishedAt: published,
				})

				citations = append(citations, articleURL)
				if domain != "" {
					sources = append(sources, domain)
				}

				if urlMobile != "" {
					citations = append(citations, urlMobile)
				}
			}
		}
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d articles from GDELT", len(results)),
	}, nil
}

// SearchEvents searches for specific events using GDELT event API.
func (p *GDELTProvider) SearchEvents(ctx context.Context, req SearchRequest) ([]GDELTEvent, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	maxResults := req.MaxResults
	if maxResults == 0 {
		maxResults = 100
	}

	query := url.QueryEscape(req.Query)

	// Use CSV format for events
	urlStr := fmt.Sprintf("%s/events/events?search=%s&max-events=%d&format=csv",
		p.baseURL, query, maxResults)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "text/csv")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0")

	resp, err := p.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("GDELT events request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GDELT events unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse CSV response
	reader := csv.NewReader(resp.Body)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("failed to parse GDELT CSV: %w", err)
	}

	events := make([]GDELTEvent, 0, len(records)-1) // Skip header

	// Skip header row
	for i, record := range records {
		if i == 0 || len(record) < 5 {
			continue
		}

		event := parseGDELTEvent(record)
		events = append(events, event)
	}

	return events, nil
}

// GetTimeline generates a timeline of events for a query.
func (p *GDELTProvider) GetTimeline(ctx context.Context, query string, timelineType string) (map[string]interface{}, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	if timelineType == "" {
		timelineType = "timelinevol"
	}

	urlStr := fmt.Sprintf("%s/timeline/timeline?search=%s&mode=%s&format=json",
		p.baseURL, url.QueryEscape(query), timelineType)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0")

	resp, err := p.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("GDELT timeline request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GDELT timeline unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var timeline map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&timeline); err != nil {
		return nil, fmt.Errorf("failed to parse GDELT timeline: %w", err)
	}

	return timeline, nil
}

// parseGDELTEvent parses a CSV record into a GDELTEvent.
func parseGDELTEvent(record []string) GDELTEvent {
	event := GDELTEvent{}

	fields := []string{
		"GlobalEventID", "Day", "MonthYear", "Year",
		"Actor1Code", "Actor1Name", "Actor1CountryCode", "Actor1KnownGroupCode", "Actor1Type1Code",
		"Actor2Code", "Actor2Name", "Actor2CountryCode", "Actor2KnownGroupCode", "Actor2Type1Code",
		"IsRootEvent", "EventCode", "EventBaseCode", "EventRootCode",
		"QuadClass", "GoldsteinScale", "NumMentions", "NumSources", "NumArticles", "AvgTone",
		"Actor1GeoType", "Actor1GeoFullName", "Actor1GeoCountryCode", "Actor1GeoADM1Code", "Actor1GeoADM2Code", "Actor1GeoLat", "Actor1GeoLong",
		"Actor2GeoType", "Actor2GeoFullName", "Actor2GeoCountryCode", "Actor2GeoADM1Code", "Actor2GeoADM2Code", "Actor2GeoLat", "Actor2GeoLong",
		"DateAdded", "URL", "SourceURL",
	}

	for i, field := range fields {
		if i < len(record) {
			switch field {
			case "GlobalEventID":
				event.GlobalEventID = record[i]
			case "Day":
				event.Day = record[i]
			case "Year":
				event.Year = record[i]
			case "Actor1Name":
				event.Actor1Name = record[i]
			case "Actor2Name":
				event.Actor2Name = record[i]
			case "EventCode":
				event.EventCode = record[i]
			case "EventRootCode":
				event.EventRootCode = record[i]
			case "QuadClass":
				event.QuadClass = record[i]
			case "GoldsteinScale":
				event.GoldsteinScale = record[i]
			case "NumMentions":
				event.NumMentions = record[i]
			case "NumArticles":
				event.NumArticles = record[i]
			case "AvgTone":
				event.AvgTone = record[i]
			case "Actor1GeoFullName":
				event.Actor1GeoFullName = record[i]
			case "Actor2GeoFullName":
				event.Actor2GeoFullName = record[i]
			case "SourceURL":
				event.SourceURL = record[i]
			}
		}
	}

	return event
}

// getStringValue safely extracts a string from a map.
func getStringValue(m map[string]interface{}, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

// getFloatValue safely extracts a float from a map.
func getFloatValue(m map[string]interface{}, key string) float64 {
	if v, ok := m[key].(float64); ok {
		return v
	}
	return 0
}

// GetEventCategories returns the mapping of CAMEO event codes to categories.
func GetEventCategories() map[string]string {
	return map[string]string{
		"01": "Make public statement",
		"02": "Appeal",
		"03": "Express intent to cooperate",
		"04": "Consult",
		"05": "Engage in diplomatic cooperation",
		"06": "Engage in material cooperation",
		"07": "Provide aid",
		"08": "Yield",
		"09": "Investigate",
		"10": "Demand",
		"11": "Disapprove",
		"12": "Reject",
		"13": "Threaten",
		"14": "Protest",
		"15": "Exhibit military posture",
		"16": "Reduce relations",
		"17": "Coerce",
		"18": "Assault",
		"19": "Fight",
		"20": "Use unconventional mass violence",
	}
}

// FormatEventDescription formats a GDELT event into a readable description.
func FormatEventDescription(event GDELTEvent) string {
	var builder strings.Builder

	builder.WriteString(fmt.Sprintf("Event %s: %s → %s\n",
		event.GlobalEventID, event.Actor1Name, event.Actor2Name))

	builder.WriteString(fmt.Sprintf("Date: %s\n", event.Day))

	if event.Actor1GeoFullName != "" {
		builder.WriteString(fmt.Sprintf("Location: %s\n", event.Actor1GeoFullName))
	}

	if event.EventRootCode != "" {
		categories := GetEventCategories()
		if cat, ok := categories[event.EventRootCode]; ok {
			builder.WriteString(fmt.Sprintf("Category: %s (%s)\n", cat, event.EventRootCode))
		}
	}

	builder.WriteString(fmt.Sprintf("Tone: %s (scale: %s)\n", event.AvgTone, event.GoldsteinScale))
	builder.WriteString(fmt.Sprintf("Mentions: %s | Sources: %s | Articles: %s\n",
		event.NumMentions, event.NumSources, event.NumArticles))

	if event.SourceURL != "" {
		builder.WriteString(fmt.Sprintf("Source: %s\n", event.SourceURL))
	}

	return builder.String()
}

// GetQuadClassDescription returns human-readable quad class.
func GetQuadClassDescription(code string) string {
	switch code {
	case "1":
		return "Verbal Cooperation"
	case "2":
		return "Material Cooperation"
	case "3":
		return "Verbal Conflict"
	case "4":
		return "Material Conflict"
	default:
		return "Unknown"
	}
}
