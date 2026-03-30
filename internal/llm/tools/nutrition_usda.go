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

// USDAParams for USDA food queries
type USDAParams struct {
	Query      string   `json:"query"`      // Search query
	FDC_ID     int      `json:"fdcId"`      // FDC ID (for direct lookup)
	DataType   []string `json:"dataType"`   // Foundation, Branded, etc.
	PageSize   int      `json:"pageSize"`   // Results per page
	PageNumber int      `json:"pageNumber"` // Page number
}

type usdaTool struct {
	client *http.Client
	apiKey string
}

const (
	NutritionUSDAToolName        = "nutrition_usda"
	nutritionUSDAToolDescription = `Fetches food nutrition data from USDA FoodData Central API.
This tool provides access to comprehensive nutrition information for foods.

HOW TO USE:
- Search foods by name or description using the query parameter
- Get specific food by FDC ID for detailed nutrient information
- Filter by data type (Foundation, Branded, SR Legacy, etc.)

FEATURES:
- Search thousands of foods in USDA database
- Get detailed nutrient composition for any food
- Access Foundation foods with precise data
- Find branded food products with labels

EXAMPLES:
- Search: "query": "chicken breast"
- By ID: "fdcId": 171534

NOTE: Requires USDA FDC API key (free at https://fdc.nal.usda.gov/api-key.html)`
)

// USDA API response structures
type usdaSearchResponse struct {
	Foods []struct {
		FDC_ID        int    `json:"fdcId"`
		Description   string `json:"description"`
		DataType      string `json:"dataType"`
		FoodNutrients []struct {
			NutrientID   int     `json:"nutrientId"`
			NutrientName string  `json:"nutrientName"`
			Value        float64 `json:"value"`
			UnitName     string  `json:"unitName"`
		} `json:"foodNutrients,omitempty"`
	} `json:"foods"`
	TotalHits int `json:"totalHits"`
}

type usdaFoodResponse struct {
	FDC_ID       int    `json:"fdcId"`
	Description  string `json:"description"`
	DataType     string `json:"dataType"`
	FoodPortions []struct {
		GramWeight float64 `json:"gramWeight"`
		Amount     float64 `json:"amount"`
		Modifier   string  `json:"modifier"`
	} `json:"foodPortions,omitempty"`
	FoodNutrients []struct {
		NutrientID   int     `json:"nutrientId"`
		NutrientName string  `json:"nutrientName"`
		Value        float64 `json:"value"`
		UnitName     string  `json:"unitName"`
	} `json:"foodNutrients,omitempty"`
}

func NewUSDATool(apiKey string) BaseTool {
	return &usdaTool{
		client: &http.Client{
			Timeout: 25 * time.Second,
		},
		apiKey: apiKey,
	}
}

func (t *usdaTool) Info() ToolInfo {
	return ToolInfo{
		Name:        NutritionUSDAToolName,
		Description: nutritionUSDAToolDescription,
		Parameters: map[string]any{
			"query": map[string]any{
				"type":        "string",
				"description": "Search query for foods",
			},
			"fdcId": map[string]any{
				"type":        "number",
				"description": "FDC ID for direct food lookup",
			},
			"dataType": map[string]any{
				"type":        "array",
				"description": "Filter by data type (Foundation, Branded, SR Legacy, Survey)",
			},
			"pageSize": map[string]any{
				"type":        "number",
				"description": "Number of results per page (default: 10, max: 50)",
			},
			"pageNumber": map[string]any{
				"type":        "number",
				"description": "Page number for pagination",
			},
		},
		Required: []string{},
	}
}

func (t *usdaTool) Run(ctx context.Context, call ToolCall) (ToolResponse, error) {
	var params USDAParams
	if err := json.Unmarshal([]byte(call.Input), &params); err != nil {
		return NewTextErrorResponse("invalid parameters: " + err.Error()), nil
	}

	// Set defaults
	if params.PageSize == 0 {
		params.PageSize = 10
	}
	if params.PageSize > 50 {
		params.PageSize = 50
	}
	if params.PageNumber == 0 {
		params.PageNumber = 1
	}

	// If FDC_ID is provided, get food by ID
	if params.FDC_ID > 0 {
		return t.getFoodByID(ctx, params.FDC_ID)
	}

	// Otherwise search by query
	if params.Query == "" {
		return NewTextErrorResponse("either query or fdcId is required"), nil
	}

	return t.searchFoods(ctx, params)
}

func (t *usdaTool) searchFoods(ctx context.Context, params USDAParams) (ToolResponse, error) {
	baseURL := "https://api.nal.usda.gov/fdc/v1/foods/search"

	queryParams := url.Values{}
	queryParams.Set("api_key", t.apiKey)
	queryParams.Set("query", params.Query)
	queryParams.Set("pageSize", fmt.Sprintf("%d", params.PageSize))
	queryParams.Set("pageNumber", fmt.Sprintf("%d", params.PageNumber))

	if len(params.DataType) > 0 {
		queryParams.Set("dataType", strings.Join(params.DataType, ","))
	}

	req, err := http.NewRequestWithContext(ctx, "GET", baseURL+"?"+queryParams.Encode(), nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "aria-nutrition-tool/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("search failed: " + err.Error()), nil
	}

	var resp usdaSearchResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	// Format results
	foods := make([]map[string]any, 0, len(resp.Foods))
	for _, food := range resp.Foods {
		f := map[string]any{
			"fdcId":       food.FDC_ID,
			"description": food.Description,
			"dataType":    food.DataType,
			"nutrients":   food.FoodNutrients,
		}
		foods = append(foods, f)
	}

	result := map[string]any{
		"type":       "usda-search",
		"query":      params.Query,
		"totalHits":  resp.TotalHits,
		"pageSize":   params.PageSize,
		"pageNumber": params.PageNumber,
		"foods":      foods,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *usdaTool) getFoodByID(ctx context.Context, fdcID int) (ToolResponse, error) {
	url := fmt.Sprintf("https://api.nal.usda.gov/fdc/v1/food/%d?api_key=%s", fdcID, t.apiKey)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "aria-nutrition-tool/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("failed to get food: " + err.Error()), nil
	}

	var resp usdaFoodResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	result := map[string]any{
		"type":          "usda-food",
		"fdcId":         resp.FDC_ID,
		"description":   resp.Description,
		"dataType":      resp.DataType,
		"foodPortions":  resp.FoodPortions,
		"foodNutrients": resp.FoodNutrients,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *usdaTool) doRequestWithRetry(ctx context.Context, req *http.Request, maxRetries int) ([]byte, error) {
	var lastErr error

	for attempt := 0; attempt < maxRetries; attempt++ {
		if attempt > 0 {
			// Exponential backoff
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

		if resp.StatusCode == http.StatusTooManyRequests {
			lastErr = fmt.Errorf("rate limited")
			continue
		}

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			lastErr = fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
			continue
		}

		return io.ReadAll(resp.Body)
	}

	return nil, lastErr
}
