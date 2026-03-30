package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// OpenFDAParams for openFDA food enforcement queries
type OpenFDAParams struct {
	Operation      string `json:"operation"`      // search, get
	ID             string `json:"id"`             // Recall ID
	Status         string `json:"status"`         // On-Going, Terminated
	Classification string `json:"classification"` // Class I, II, III
	Limit          int    `json:"limit"`          // Results limit
}

type openFDATool struct {
	client *http.Client
}

const (
	FoodSafetyOpenFDAToolName        = "food_safety_openfda"
	foodSafetyOpenFDAToolDescription = `Fetches food recall information from openFDA Food Enforcement API.
This tool provides access to FDA food safety enforcement data including recalls, alerts, and safety notices.

HOW TO USE:
- Search food recalls with various filters
- Get specific recall by ID
- Filter by status (On-Going, Terminated)
- Filter by classification (Class I, II, III)

FEATURES:
- Search FDA food recall database
- Get detailed recall information
- Filter by recall status and classification
- Access voluntary and mandatory recalls
- View product distribution and hazard information

EXAMPLES:
- Search all: "operation": "search"
- Filter status: "operation": "search", "status": "On-Going"
- Filter classification: "operation": "search", "classification": "Class I"
- Get by ID: "operation": "get", "id": "R-05-2023"

NOTE: Public API, no key required. Rate limits apply.`
)

// openFDA API response structures
type fdaRecallSearchResponse struct {
	Meta struct {
		Results struct {
			Limit int `json:"limit"`
			Total int `json:"total"`
		} `json:"results"`
	} `json:"meta"`
	Results []struct {
		RecallNumber          string `json:"recall_number"`
		Classification        string `json:"classification"`
		Status                string `json:"status"`
		RecallingFirm         string `json:"recalling_firm"`
		ProductDescription    string `json:"product_description"`
		ProductQuantity       string `json:"product_quantity"`
		ReasonForRecall       string `json:"reason_for_recall"`
		DistributionPattern   string `json:"distribution_pattern"`
		ProductType           string `json:"product_type"`
		EventID               string `json:"event_id"`
		RecInitDate           string `json:"rec_init_date"`
		RecRecallCompleteDate string `json:"rec_recall_complete_date"`
		TerminationDate       string `json:"termination_date"`
		VoluntaryMandated     string `json:"voluntary_mandated"`
		State                 string `json:"state"`
		City                  string `json:"city"`
		Country               string `json:"country"`
	} `json:"results"`
}

type fdaRecallResponse struct {
	Meta struct {
		Results struct {
			Limit int `json:"limit"`
			Total int `json:"total"`
		} `json:"results"`
	} `json:"meta"`
	Results []struct {
		RecallNumber          string `json:"recall_number"`
		Classification        string `json:"classification"`
		Status                string `json:"status"`
		RecallingFirm         string `json:"recalling_firm"`
		ProductDescription    string `json:"product_description"`
		ProductQuantity       string `json:"product_quantity"`
		ReasonForRecall       string `json:"reason_for_recall"`
		DistributionPattern   string `json:"distribution_pattern"`
		ProductType           string `json:"product_type"`
		EventID               string `json:"event_id"`
		RecInitDate           string `json:"rec_init_date"`
		RecRecallCompleteDate string `json:"rec_recall_complete_date"`
		TerminationDate       string `json:"termination_date"`
		VoluntaryMandated     string `json:"voluntary_mandated"`
		State                 string `json:"state"`
		City                  string `json:"city"`
		Country               string `json:"country"`
	} `json:"results"`
}

func NewOpenFDATool() BaseTool {
	return &openFDATool{
		client: &http.Client{
			Timeout: 25 * time.Second,
		},
	}
}

func (t *openFDATool) Info() ToolInfo {
	return ToolInfo{
		Name:        FoodSafetyOpenFDAToolName,
		Description: foodSafetyOpenFDAToolDescription,
		Parameters: map[string]any{
			"operation": map[string]any{
				"type":        "string",
				"description": "Operation: search or get",
				"enum":        []string{"search", "get"},
			},
			"id": map[string]any{
				"type":        "string",
				"description": "Recall ID for get operation",
			},
			"status": map[string]any{
				"type":        "string",
				"description": "Filter by status: On-Going, Terminated",
			},
			"classification": map[string]any{
				"type":        "string",
				"description": "Filter by classification: Class I, Class II, Class III",
			},
			"limit": map[string]any{
				"type":        "number",
				"description": "Maximum number of results (default: 50, max: 100)",
			},
		},
		Required: []string{"operation"},
	}
}

func (t *openFDATool) Run(ctx context.Context, call ToolCall) (ToolResponse, error) {
	var params OpenFDAParams
	if err := json.Unmarshal([]byte(call.Input), &params); err != nil {
		return NewTextErrorResponse("invalid parameters: " + err.Error()), nil
	}

	if params.Operation == "" {
		return NewTextErrorResponse("operation is required"), nil
	}

	// Set defaults
	if params.Limit == 0 {
		params.Limit = 50
	}
	if params.Limit > 100 {
		params.Limit = 100
	}

	switch strings.ToLower(params.Operation) {
	case "search":
		return t.searchRecalls(ctx, params)

	case "get":
		if params.ID == "" {
			return NewTextErrorResponse("id is required for get operation"), nil
		}
		return t.getRecallByID(ctx, params.ID)

	default:
		return NewTextErrorResponse("unknown operation: " + params.Operation), nil
	}
}

func (t *openFDATool) searchRecalls(ctx context.Context, params OpenFDAParams) (ToolResponse, error) {
	baseURL := "https://api.fda.gov/food/enforcement.json"

	queryParams := url.Values{}
	queryParams.Set("limit", fmt.Sprintf("%d", params.Limit))

	// Build search query
	var searchTerms []string

	if params.Status != "" {
		searchTerms = append(searchTerms, fmt.Sprintf("status:\"%s\"", params.Status))
	}

	if params.Classification != "" {
		searchTerms = append(searchTerms, fmt.Sprintf("classification:\"%s\"", params.Classification))
	}

	if len(searchTerms) > 0 {
		queryParams.Set("search", strings.Join(searchTerms, "+"))
	}

	req, err := http.NewRequestWithContext(ctx, "GET", baseURL+"?"+queryParams.Encode(), nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-FoodSafety/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("search failed: " + err.Error()), nil
	}

	var resp fdaRecallSearchResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	recalls := make([]map[string]any, 0)
	for _, r := range resp.Results {
		recalls = append(recalls, map[string]any{
			"recallNumber":    r.RecallNumber,
			"classification":  r.Classification,
			"status":          r.Status,
			"recallingFirm":   r.RecallingFirm,
			"productDesc":     r.ProductDescription,
			"reasonForRecall": r.ReasonForRecall,
			"productType":     r.ProductType,
			"eventID":         r.EventID,
			"recInitDate":     r.RecInitDate,
		})
	}

	result := map[string]any{
		"type":         "openfda-recall-search",
		"totalResults": resp.Meta.Results.Total,
		"limit":        params.Limit,
		"filters": map[string]any{
			"status":         params.Status,
			"classification": params.Classification,
		},
		"recalls": recalls,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *openFDATool) getRecallByID(ctx context.Context, id string) (ToolResponse, error) {
	url := fmt.Sprintf("https://api.fda.gov/food/enforcement.json?search=recall_number:\"%s\"&limit=1", id)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-FoodSafety/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("get recall failed: " + err.Error()), nil
	}

	var resp fdaRecallResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	if len(resp.Results) == 0 {
		return NewTextErrorResponse(fmt.Sprintf("recall not found: %s", id)), nil
	}

	r := resp.Results[0]
	result := map[string]any{
		"type":                "openfda-recall",
		"recallNumber":        r.RecallNumber,
		"classification":      r.Classification,
		"status":              r.Status,
		"recallingFirm":       r.RecallingFirm,
		"productDescription":  r.ProductDescription,
		"productQuantity":     r.ProductQuantity,
		"reasonForRecall":     r.ReasonForRecall,
		"distributionPattern": r.DistributionPattern,
		"productType":         r.ProductType,
		"eventID":             r.EventID,
		"recInitDate":         r.RecInitDate,
		"recallCompleteDate":  r.RecRecallCompleteDate,
		"terminationDate":     r.TerminationDate,
		"voluntaryMandated":   r.VoluntaryMandated,
		"state":               r.State,
		"city":                r.City,
		"country":             r.Country,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *openFDATool) doRequestWithRetry(ctx context.Context, req *http.Request, maxRetries int) ([]byte, error) {
	var lastErr error

	for attempt := 0; attempt < maxRetries; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(attempt*attempt*100) * time.Millisecond
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
			}
		}

		resp, err := t.client.Do(req)
		if err != nil {
			lastErr = err
			continue
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			lastErr = fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
			continue
		}

		return io.ReadAll(resp.Body)
	}

	return nil, lastErr
}
