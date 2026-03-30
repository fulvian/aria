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

// MealDBParams for TheMealDB API queries
type MealDBParams struct {
	Operation string `json:"operation"` // search, lookup, random, filter, categories, areas, ingredients
	Query     string `json:"query"`     // Search query for meal name
	ID        int    `json:"id"`        // Meal ID for lookup
	Letter    string `json:"letter"`    // Single letter for filter
}

type mealDBTool struct {
	client *http.Client
}

const (
	MealDBToolName        = "recipes_mealdb"
	mealDBToolDescription = `Fetches meal recipes from TheMealDB API.
This tool provides access to thousands of recipes from around the world.

HOW TO USE:
- Search meals by name using operation "search"
- Get meal details by ID using operation "lookup"
- Get a random meal using operation "random"
- Filter meals by first letter using operation "filter"
- List categories, areas, or ingredients

FEATURES:
- Search thousands of recipes by name
- Full recipe details with instructions
- Ingredient measurements and quantities
- Category and area (cuisine) filtering
- Random recipe suggestions

EXAMPLES:
- Search: "operation": "search", "query": "pizza"
- Lookup: "operation": "lookup", "id": 52772
- Random: "operation": "random"
- Filter: "operation": "filter", "letter": "c"
- Categories: "operation": "categories"

NOTE: Free tier limited to 1 request/second.`
)

// TheMealDB API response structures
type mealDBSearchResponse struct {
	Meals []struct {
		IDMeal      string `json:"idMeal"`
		StrMeal     string `json:"strMeal"`
		StrCategory string `json:"strCategory"`
		StrArea     string `json:"strArea"`
	} `json:"meals"`
}

type mealDBMealResponse struct {
	Meals []struct {
		IDMeal          string `json:"idMeal"`
		StrMeal         string `json:"strMeal"`
		StrCategory     string `json:"strCategory"`
		StrArea         string `json:"strArea"`
		StrInstructions string `json:"strInstructions"`
		StrMealThumb    string `json:"strMealThumb"`
		StrTags         string `json:"strTags"`
		StrYoutube      string `json:"strYoutube"`
		StrSource       string `json:"strSource"`
		Ingredients     []struct {
			Name    string `json:"name"`
			Measure string `json:"measure"`
		} `json:"ingredients"`
	} `json:"meals"`
}

type mealDBCategoryResponse struct {
	Categories []struct {
		IDCategory             string `json:"idCategory"`
		StrCategory            string `json:"strCategory"`
		StrCategoryThumb       string `json:"strCategoryThumb"`
		StrCategoryDescription string `json:"strCategoryDescription"`
	} `json:"categories"`
}

type mealDBAreaResponse struct {
	Meals []struct {
		StrArea string `json:"strArea"`
	} `json:"meals"`
}

type mealDBIngredientResponse struct {
	Meals []struct {
		IDIngredient   string `json:"idIngredient"`
		StrIngredient  string `json:"strIngredient"`
		StrDescription string `json:"strDescription"`
	} `json:"meals"`
}

func NewMealDBTool() BaseTool {
	return &mealDBTool{
		client: &http.Client{
			Timeout: 25 * time.Second,
		},
	}
}

func (t *mealDBTool) Info() ToolInfo {
	return ToolInfo{
		Name:        MealDBToolName,
		Description: mealDBToolDescription,
		Parameters: map[string]any{
			"operation": map[string]any{
				"type":        "string",
				"description": "Operation: search, lookup, random, filter, categories, areas, ingredients",
				"enum":        []string{"search", "lookup", "random", "filter", "categories", "areas", "ingredients"},
			},
			"query": map[string]any{
				"type":        "string",
				"description": "Search query for meal name",
			},
			"id": map[string]any{
				"type":        "number",
				"description": "Meal ID for lookup operation",
			},
			"letter": map[string]any{
				"type":        "string",
				"description": "Single letter to filter meals by first letter",
			},
		},
		Required: []string{"operation"},
	}
}

func (t *mealDBTool) Run(ctx context.Context, call ToolCall) (ToolResponse, error) {
	var params MealDBParams
	if err := json.Unmarshal([]byte(call.Input), &params); err != nil {
		return NewTextErrorResponse("invalid parameters: " + err.Error()), nil
	}

	if params.Operation == "" {
		return NewTextErrorResponse("operation is required"), nil
	}

	switch strings.ToLower(params.Operation) {
	case "search":
		if params.Query == "" {
			return NewTextErrorResponse("query is required for search operation"), nil
		}
		return t.searchMeals(ctx, params.Query)

	case "lookup":
		if params.ID <= 0 {
			return NewTextErrorResponse("id is required for lookup operation"), nil
		}
		return t.lookupMeal(ctx, params.ID)

	case "random":
		return t.getRandomMeal(ctx)

	case "filter":
		if params.Letter == "" {
			return NewTextErrorResponse("letter is required for filter operation"), nil
		}
		if len(params.Letter) != 1 {
			return NewTextErrorResponse("letter must be a single character"), nil
		}
		return t.filterMealsByLetter(ctx, params.Letter)

	case "categories":
		return t.listCategories(ctx)

	case "areas":
		return t.listAreas(ctx)

	case "ingredients":
		return t.listIngredients(ctx)

	default:
		return NewTextErrorResponse("unknown operation: " + params.Operation), nil
	}
}

func (t *mealDBTool) searchMeals(ctx context.Context, query string) (ToolResponse, error) {
	url := fmt.Sprintf("https://www.themealdb.com/api/json/v1/1/search.php?s=%s", url.QueryEscape(query))

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-Recipes/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("search failed: " + err.Error()), nil
	}

	var resp mealDBSearchResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	meals := make([]map[string]any, 0)
	if resp.Meals != nil {
		for _, m := range resp.Meals {
			meals = append(meals, map[string]any{
				"id":       m.IDMeal,
				"name":     m.StrMeal,
				"category": m.StrCategory,
				"area":     m.StrArea,
			})
		}
	}

	result := map[string]any{
		"type":  "mealdb-search",
		"query": query,
		"count": len(meals),
		"meals": meals,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *mealDBTool) lookupMeal(ctx context.Context, id int) (ToolResponse, error) {
	url := fmt.Sprintf("https://www.themealdb.com/api/json/v1/1/lookup.php?i=%d", id)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-Recipes/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("lookup failed: " + err.Error()), nil
	}

	var resp mealDBMealResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	if len(resp.Meals) == 0 {
		return NewTextErrorResponse(fmt.Sprintf("meal not found with id: %d", id)), nil
	}

	meal := resp.Meals[0]
	// Parse ingredients
	ingredients := make([]struct {
		Name    string `json:"name"`
		Measure string `json:"measure"`
	}, 0)
	for i := 1; i <= 20; i++ {
		ingredientField := fmt.Sprintf("StrIngredient%d", i)
		measureField := fmt.Sprintf("StrMeasure%d", i)

		var ingredient, measure string
		// Use reflection-like approach with json
		mealJSON, _ := json.Marshal(meal)
		var mealMap map[string]interface{}
		json.Unmarshal(mealJSON, &mealMap)

		if v, ok := mealMap[ingredientField].(string); ok && v != "" {
			ingredient = v
		}
		if v, ok := mealMap[measureField].(string); ok && v != "" {
			measure = v
		}
		if ingredient != "" {
			ingredients = append(ingredients, struct {
				Name    string `json:"name"`
				Measure string `json:"measure"`
			}{ingredient, measure})
		}
	}

	result := map[string]any{
		"type":         "mealdb-meal",
		"id":           meal.IDMeal,
		"name":         meal.StrMeal,
		"category":     meal.StrCategory,
		"area":         meal.StrArea,
		"thumbnail":    meal.StrMealThumb,
		"instructions": meal.StrInstructions,
		"tags":         meal.StrTags,
		"youtube":      meal.StrYoutube,
		"source":       meal.StrSource,
		"ingredients":  ingredients,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *mealDBTool) getRandomMeal(ctx context.Context) (ToolResponse, error) {
	url := "https://www.themealdb.com/api/json/v1/1/random.php"

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-Recipes/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("random meal failed: " + err.Error()), nil
	}

	var resp mealDBMealResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	if len(resp.Meals) == 0 {
		return NewTextErrorResponse("no random meal returned"), nil
	}

	meal := resp.Meals[0]
	result := map[string]any{
		"type":     "mealdb-random",
		"id":       meal.IDMeal,
		"name":     meal.StrMeal,
		"category": meal.StrCategory,
		"area":     meal.StrArea,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *mealDBTool) filterMealsByLetter(ctx context.Context, letter string) (ToolResponse, error) {
	url := fmt.Sprintf("https://www.themealdb.com/api/json/v1/1/filter.php?f=%s", letter)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-Recipes/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("filter failed: " + err.Error()), nil
	}

	var resp mealDBSearchResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	meals := make([]map[string]any, 0)
	if resp.Meals != nil {
		for _, m := range resp.Meals {
			meals = append(meals, map[string]any{
				"id":   m.IDMeal,
				"name": m.StrMeal,
			})
		}
	}

	result := map[string]any{
		"type":   "mealdb-filter",
		"letter": letter,
		"count":  len(meals),
		"meals":  meals,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *mealDBTool) listCategories(ctx context.Context) (ToolResponse, error) {
	url := "https://www.themealdb.com/api/json/v1/1/categories.php"

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-Recipes/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("list categories failed: " + err.Error()), nil
	}

	var resp mealDBCategoryResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	categories := make([]map[string]any, 0)
	for _, c := range resp.Categories {
		categories = append(categories, map[string]any{
			"id":          c.IDCategory,
			"name":        c.StrCategory,
			"thumbnail":   c.StrCategoryThumb,
			"description": c.StrCategoryDescription,
		})
	}

	result := map[string]any{
		"type":       "mealdb-categories",
		"categories": categories,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *mealDBTool) listAreas(ctx context.Context) (ToolResponse, error) {
	url := "https://www.themealdb.com/api/json/v1/1/list.php?a=list"

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-Recipes/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("list areas failed: " + err.Error()), nil
	}

	var resp mealDBAreaResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	areas := make([]string, 0)
	for _, a := range resp.Meals {
		areas = append(areas, a.StrArea)
	}

	result := map[string]any{
		"type":  "mealdb-areas",
		"areas": areas,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *mealDBTool) listIngredients(ctx context.Context) (ToolResponse, error) {
	url := "https://www.themealdb.com/api/json/v1/1/list.php?i=list"

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return NewTextErrorResponse("failed to create request: " + err.Error()), nil
	}
	req.Header.Set("User-Agent", "ARIA-Recipes/1.0")

	data, err := t.doRequestWithRetry(ctx, req, 3)
	if err != nil {
		return NewTextErrorResponse("list ingredients failed: " + err.Error()), nil
	}

	var resp mealDBIngredientResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	ingredients := make([]map[string]any, 0)
	for _, i := range resp.Meals {
		ingredients = append(ingredients, map[string]any{
			"id":          i.IDIngredient,
			"name":        i.StrIngredient,
			"description": i.StrDescription,
		})
	}

	result := map[string]any{
		"type":        "mealdb-ingredients",
		"count":       len(ingredients),
		"ingredients": ingredients,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *mealDBTool) doRequestWithRetry(ctx context.Context, req *http.Request, maxRetries int) ([]byte, error) {
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
