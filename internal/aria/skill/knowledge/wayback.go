package knowledge

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// WaybackProvider implements SearchProvider for Wayback Machine API.
// The Wayback Machine provides historical snapshots of web pages.
type WaybackProvider struct {
	timeout time.Duration
	baseURL string
}

// WaybackResponse represents a general Wayback API response.
type WaybackResponse struct {
	URL       string `json:"url"`
	ArcID     string `json:"arc_id"`
	Timestamp string `json:"timestamp"`
}

// WaybackCDXResponse represents the CDX API response (index of pages).
type WaybackCDXResponse []WaybackCDXEntry

// WaybackCDXEntry represents a single entry in the CDX index.
type WaybackCDXEntry struct {
	Original   string `json:"original"`
	Timestamp  string `json:"timestamp"`
	URL        string `json:"url"`
	Status     string `json:"status"`
	MimeType   string `json:"mime"`
	Length     string `json:"length"`
	Redirect   string `json:"redirect"`
	Digest     string `json:"digest"`
	RobotFlags string `json:"robotflags"`
}

// WaybackAvailabilityResponse represents availability API response.
type WaybackAvailabilityResponse struct {
	URL struct {
		ArchivedSnapshots struct {
			Closest *WaybackSnapshot `json:"closest"`
		} `json:"archived_snapshots"`
	} `json:"url"`
}

// WaybackSnapshot represents an archived snapshot.
type WaybackSnapshot struct {
	Status      string `json:"status"`
	Available   bool   `json:"available"`
	URL         string `json:"url"`
	Timestamp   string `json:"timestamp"`
	RedirectURL string `json:"redirect"`
}

// NewWaybackProvider creates a new Wayback Machine provider.
func NewWaybackProvider(timeout time.Duration) *WaybackProvider {
	return &WaybackProvider{
		timeout: timeout,
		baseURL: "https://web.archive.org",
	}
}

// Name returns the provider name.
func (p *WaybackProvider) Name() string {
	return "wayback"
}

// IsConfigured returns true - Wayback Machine requires no API key.
func (p *WaybackProvider) IsConfigured() bool {
	return true
}

// Search performs a search using Wayback Machine CDX API.
func (p *WaybackProvider) Search(ctx context.Context, req SearchRequest) (SearchResponse, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Build CDX API URL
	// CDX API provides index of all pages ever archived for a domain/URL
	urlStr := fmt.Sprintf("%s/cdx/search/cdx?url=%s&output=json&limit=%d&fl=original,timestamp,status,mime,length",
		p.baseURL, url.QueryEscape(req.Query), req.MaxResults)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0")

	// Execute request
	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return SearchResponse{}, fmt.Errorf("Wayback request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return SearchResponse{}, fmt.Errorf("Wayback unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	// Parse JSON array response (first entry is header)
	var cdxResp WaybackCDXResponse
	if err := json.NewDecoder(resp.Body).Decode(&cdxResp); err != nil {
		return SearchResponse{}, fmt.Errorf("failed to parse Wayback response: %w", err)
	}

	// Skip header row if present
	entries := cdxResp
	if len(entries) > 0 && entries[0].Original == "original" {
		entries = entries[1:]
	}

	// Convert to SearchResponse
	results := make([]SearchResult, 0, len(entries))
	citations := make([]string, 0)
	sources := make([]string, 0)

	for _, entry := range entries {
		if entry.Original == "original" { // Skip header
			continue
		}

		// Format timestamp to readable date
		timestamp := formatWaybackTimestamp(entry.Timestamp)

		// Build Wayback URL for this snapshot
		waybackURL := buildWaybackURL(entry.Original, entry.Timestamp)

		desc := fmt.Sprintf("Archived: %s | Status: %s | Type: %s",
			timestamp, entry.Status, entry.MimeType)

		results = append(results, SearchResult{
			Title:       entry.Original,
			URL:         waybackURL,
			Description: desc,
			Content: fmt.Sprintf("Original URL: %s\nArchived: %s\nStatus: %s\nContent-Type: %s\nSize: %s bytes",
				entry.Original, timestamp, entry.Status, entry.MimeType, entry.Length),
			PublishedAt: timestamp,
		})

		citations = append(citations, waybackURL)
		sources = append(sources, fmt.Sprintf("https://web.archive.org/web/%s/%s", entry.Timestamp, entry.Original))
	}

	return SearchResponse{
		Results:   results,
		Sources:   sources,
		Citations: citations,
		Summary:   fmt.Sprintf("Found %d archived snapshots from Wayback Machine", len(results)),
	}, nil
}

// GetSnapshot retrieves the closest available snapshot for a URL.
func (p *WaybackProvider) GetSnapshot(ctx context.Context, targetURL string) (*WaybackSnapshot, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Use availability API
	apiURL := fmt.Sprintf("%s/wayback/available?url=%s", p.baseURL, url.QueryEscape(targetURL))

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", apiURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("Wayback availability request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Wayback availability unexpected status: %d, body: %s", resp.StatusCode, string(respBody))
	}

	var availResp WaybackAvailabilityResponse
	if err := json.NewDecoder(resp.Body).Decode(&availResp); err != nil {
		return nil, fmt.Errorf("failed to parse Wayback response: %w", err)
	}

	return availResp.URL.ArchivedSnapshots.Closest, nil
}

// GetHistoricalSnapshot retrieves a snapshot from a specific timestamp.
func (p *WaybackProvider) GetHistoricalSnapshot(ctx context.Context, targetURL, timestamp string) (string, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	// Validate timestamp format (should be 14 digits: YYYYMMDDHHMMSS)
	if len(timestamp) != 14 {
		return "", fmt.Errorf("invalid timestamp format, expected 14 digits (YYYYMMDDHHMMSS)")
	}

	// Build Wayback URL for specific timestamp
	waybackURL := fmt.Sprintf("%s/web/%s/%s", p.baseURL, timestamp, targetURL)

	// Verify the snapshot exists
	httpReq, err := http.NewRequestWithContext(reqCtx, http.MethodHead, waybackURL, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("Wayback snapshot request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK || resp.StatusCode == http.StatusFound {
		return waybackURL, nil
	}

	// Return URL anyway - Wayback will redirect if not available
	return waybackURL, nil
}

// GetTimeline generates a timeline of snapshots for a URL.
func (p *WaybackProvider) GetTimeline(ctx context.Context, targetURL string, maxResults int) ([]SearchResult, error) {
	reqCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	if maxResults == 0 {
		maxResults = 20
	}

	// CDX API with from/to for timeline
	urlStr := fmt.Sprintf("%s/cdx/search/cdx?url=%s&output=json&limit=%d&fl=original,timestamp,status,mime&from=1996&to=2026",
		p.baseURL, url.QueryEscape(targetURL), maxResults)

	httpReq, err := http.NewRequestWithContext(reqCtx, "GET", urlStr, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("User-Agent", "ARIA-Knowledge-Agency/1.0")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("Wayback timeline request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Wayback timeline unexpected status: %d", resp.StatusCode)
	}

	var cdxResp WaybackCDXResponse
	if err := json.NewDecoder(resp.Body).Decode(&cdxResp); err != nil {
		return nil, fmt.Errorf("failed to parse Wayback response: %w", err)
	}

	// Skip header
	entries := cdxResp
	if len(entries) > 0 && entries[0].Original == "original" {
		entries = entries[1:]
	}

	results := make([]SearchResult, 0, len(entries))
	for _, entry := range entries {
		if entry.Original == "original" {
			continue
		}
		timestamp := formatWaybackTimestamp(entry.Timestamp)
		waybackURL := buildWaybackURL(entry.Original, entry.Timestamp)

		results = append(results, SearchResult{
			Title:       entry.Original,
			URL:         waybackURL,
			Description: fmt.Sprintf("Archived: %s | Status: %s", timestamp, entry.Status),
			PublishedAt: timestamp,
		})
	}

	return results, nil
}

// formatWaybackTimestamp converts 14-digit timestamp to readable date.
func formatWaybackTimestamp(ts string) string {
	if len(ts) < 14 {
		return ts
	}
	year := ts[0:4]
	month := ts[4:6]
	day := ts[6:8]
	hour := ts[8:10]
	min := ts[10:12]
	sec := ts[12:14]
	return fmt.Sprintf("%s-%s-%s %s:%s:%s", year, month, day, hour, min, sec)
}

// buildWaybackURL constructs a Wayback URL for a specific snapshot.
func buildWaybackURL(original, timestamp string) string {
	return fmt.Sprintf("https://web.archive.org/web/%s/%s", timestamp, original)
}
