package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// OpenFoodFactsParams for Open Food Facts queries
type OpenFoodFactsParams struct {
	Barcode  string `json:"barcode"`  // Product barcode
	Name     string `json:"name"`     // Search name
	PageSize int    `json:"pageSize"` // Results per page
	Page     int    `json:"page"`     // Page number
}

type openFoodFactsTool struct {
	client *http.Client
}

const (
	OpenFoodFactsToolName        = "nutrition_openfoodfacts"
	openFoodFactsToolDescription = `Fetches product information from Open Food Facts database.
This tool provides crowd-sourced food product information including ingredients, nutrition, and packaging data.

HOW TO USE:
- Search products by barcode or name
- Get detailed product information by barcode
- Access ingredient lists and nutrition facts
- View product packaging and labeling information

FEATURES:
- Barcode lookup for packaged foods
- Ingredient lists with allergen warnings
- Nutrition facts per 100g / serving
- Eco-score and Nova group classification
- Open source, crowd-verified data

EXAMPLES:
- By barcode: "barcode": "3017620422003"
- Search: "name": "oreo cookies"

NOTE: This is a free, open-source API. Rate limits apply.`
)

// Open Food Facts API response structures
type offProductResponse struct {
	Status        int    `json:"status"`
	StatusVerbose string `json:"status_verbose"`
	Product       *struct {
		Code        string `json:"code"`
		ProductName string `json:"product_name"`
		Brands      string `json:"brands"`
		Categories  string `json:"categories"`
		Ingredients []struct {
			ID   string `json:"id"`
			Text string `json:"text"`
			Rank int    `json:"rank"`
		} `json:"ingredients"`
		Nutriments  map[string]any `json:"nutriments"`
		Nutriscore  string         `json:"nutriscore_grade"`
		NovaGroup   string         `json:"nova_group"`
		EcoScore    string         `json:"ecoscore_grade"`
		ServingSize string         `json:"serving_size"`
		Packaging   string         `json:"packaging"`
	} `json:"product"`
}

type offSearchResponse struct {
	Count    int `json:"count"`
	Page     int `json:"page"`
	PageSize int `json:"page_size"`
	Products []struct {
		Code        string `json:"code"`
		ProductName string `json:"product_name"`
		Brands      string `json:"brands"`
		Categories  string `json:"categories"`
		Nutriscore  string `json:"nutriscore_grade"`
		NovaGroup   string `json:"nova_group"`
	} `json:"products"`
}

func NewOpenFoodFactsTool() BaseTool {
	return &openFoodFactsTool{
		client: &http.Client{
			Timeout: 25 * time.Second,
		},
	}
}

func (t *openFoodFactsTool) Info() ToolInfo {
	return ToolInfo{
		Name:        OpenFoodFactsToolName,
		Description: openFoodFactsToolDescription,
		Parameters: map[string]any{
			"barcode": map[string]any{
				"type":        "string",
				"description": "Product barcode (ean/upc)",
			},
			"name": map[string]any{
				"type":        "string",
				"description": "Product name to search for",
			},
			"pageSize": map[string]any{
				"type":        "number",
				"description": "Number of results per page (default: 20, max: 100)",
			},
			"page": map[string]any{
				"type":        "number",
				"description": "Page number for pagination",
			},
		},
		Required: []string{},
	}
}

func (t *openFoodFactsTool) Run(ctx context.Context, call ToolCall) (ToolResponse, error) {
	var params OpenFoodFactsParams
	if err := json.Unmarshal([]byte(call.Input), &params); err != nil {
		return NewTextErrorResponse("invalid parameters: " + err.Error()), nil
	}

	// Set defaults
	if params.PageSize == 0 {
		params.PageSize = 20
	}
	if params.PageSize > 100 {
		params.PageSize = 100
	}
	if params.Page == 0 {
		params.Page = 1
	}

	// If barcode is provided, get product by barcode
	if params.Barcode != "" {
		return t.getProductByBarcode(ctx, params.Barcode)
	}

	// Otherwise search by name
	if params.Name == "" {
		return NewTextErrorResponse("either barcode or name is required"), nil
	}

	return t.searchProducts(ctx, params)
}

func (t *openFoodFactsTool) getProductByBarcode(ctx context.Context, barcode string) (ToolResponse, error) {
	url := fmt.Sprintf("https://world.openfoodfacts.org/api/v2/product/%s.json", barcode)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-Nutrition/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("failed to get product: " + err.Error()), nil
	}

	var resp offProductResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	if resp.Status != 1 || resp.Product == nil {
		return NewTextErrorResponse(fmt.Sprintf("product not found: %s", resp.StatusVerbose)), nil
	}

	product := resp.Product
	result := map[string]any{
		"type":        "openfoodfacts-product",
		"barcode":     product.Code,
		"productName": product.ProductName,
		"brands":      product.Brands,
		"categories":  product.Categories,
		"ingredients": product.Ingredients,
		"nutriments":  product.Nutriments,
		"nutriscore":  product.Nutriscore,
		"novaGroup":   product.NovaGroup,
		"ecoScore":    product.EcoScore,
		"servingSize": product.ServingSize,
		"packaging":   product.Packaging,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *openFoodFactsTool) searchProducts(ctx context.Context, params OpenFoodFactsParams) (ToolResponse, error) {
	baseURL := "https://world.openfoodfacts.org/cgi/search.pl"

	queryParams := url.Values{}
	queryParams.Set("search_terms", params.Name)
	queryParams.Set("search_simple", "1")
	queryParams.Set("action", "process")
	queryParams.Set("json", "1")
	queryParams.Set("page_size", fmt.Sprintf("%d", params.PageSize))
	queryParams.Set("page", fmt.Sprintf("%d", params.Page))

	req, err := http.NewRequestWithContext(ctx, "GET", baseURL+"?"+queryParams.Encode(), nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-Nutrition/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("search failed: " + err.Error()), nil
	}

	var resp offSearchResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	products := make([]map[string]any, 0, len(resp.Products))
	for _, p := range resp.Products {
		products = append(products, map[string]any{
			"code":        p.Code,
			"productName": p.ProductName,
			"brands":      p.Brands,
			"categories":  p.Categories,
			"nutriscore":  p.Nutriscore,
			"novaGroup":   p.NovaGroup,
		})
	}

	result := map[string]any{
		"type":     "openfoodfacts-search",
		"query":    params.Name,
		"count":    resp.Count,
		"pageSize": resp.PageSize,
		"page":     resp.Page,
		"products": products,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *openFoodFactsTool) doRequestWithRetry(ctx context.Context, req *http.Request, maxRetries int) ([]byte, error) {
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

		// Handle rate limiting
		if resp.StatusCode == http.StatusTooManyRequests || resp.StatusCode == 429 {
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
