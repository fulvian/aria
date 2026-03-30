# Nutrition Agency Configuration Guide

## Overview

The Nutrition Agency provides nutrition analysis, recipe search, diet planning, and food safety monitoring capabilities. This guide covers configuration, rate limits, and operational details.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ARIA_AGENCIES_NUTRITION_ENABLED` | Enable/disable the nutrition agency | `false` |
| `ARIA_NUTRITION_USDA_API_KEY` | USDA FoodData Central API key | (required for USDA) |
| `ARIA_NUTRITION_OPENFOODFACTS_USER_AGENT` | User agent for Open Food Facts | `ARIA/1.0` |
| `ARIA_NUTRITION_MEALDB_API_KEY` | TheMealDB API key | `1` (free tier) |
| `ARIA_NUTRITION_OPENFDA_API_KEY` | openFDA API key | (required for FDA) |
| `ARIA_NUTRITION_DEFAULT_LOCALE` | Default locale | `en-US` |
| `ARIA_NUTRITION_DEFAULT_COUNTRY` | Default country code | `US` |
| `ARIA_NUTRITION_MAX_DAILY_PLANS` | Max diet plans per day | `20` |
| `ARIA_NUTRITION_ENABLE_MEDICAL_GUARDRAILS` | Enable medical disclaimer guardrails | `true` |

### Enabling the Agency

```bash
# Enable the nutrition agency
export ARIA_AGENCIES_NUTRITION_ENABLED=true

# Set USDA API key (required)
export ARIA_NUTRITION_USDA_API_KEY="your-usda-fdc-api-key"

# Set openFDA API key (required for food recalls)
export ARIA_NUTRITION_OPENFDA_API_KEY="your-openfda-api-key"
```

### Getting API Keys

#### USDA FoodData Central
1. Visit https://fdc.nal.usda.gov/api-key.html
2. Register for a free API key
3. Rate limit: ~1000 requests/hour

#### openFDA
1. Visit https://open.fda.gov/api/
2. No API key required for basic usage
3. Rate limit: 240 requests/minute

#### TheMealDB
1. Visit https://www.themealdb.com/api.php
2. Free tier available (use key: `1`)
3. Premium tier for higher rate limits

#### Open Food Facts
1. Visit https://world.openfoodfacts.org/
2. No API key required
3. Community-maintained, free to use

---

## Rate Limits

### Provider Rate Limits

| Provider | Product Lookup | Search | Notes |
|----------|---------------|--------|-------|
| **USDA FDC** | ~1000 req/hour | ~1000 req/hour | Requires API key |
| **Open Food Facts** | 100 req/min | 10 req/min | No key required |
| **TheMealDB** | Unlimited (free) | Unlimited (free) | Free tier: `1` |
| **openFDA** | 240 req/min | 240 req/min | No key required |

### Rate Limit Handling

The Nutrition Agency implements exponential backoff retry with:
- **Max Retries**: 3 attempts
- **Backoff Formula**: `attempt² * 100ms`
- **Example**: 100ms, 400ms, 900ms delays

### Best Practices

1. **Cache Results**: Enable caching to reduce API calls
2. **Batch Requests**: Group multiple food lookups
3. **Monitor Usage**: Track metrics to avoid hitting limits
4. **Use Fallbacks**: Open Food Facts can supplement USDA

---

## Metrics & Observability

### Available Metrics

The Nutrition Agency exposes detailed metrics via `metrics.GlobalMetrics`:

#### Provider Metrics
- `TotalRequests` - Total API requests made
- `SuccessCount` - Successful requests
- `ErrorCount` - Failed requests
- `FallbackCount` - Times fallback provider was used
- `CacheHitCount` / `CacheMissCount` - Cache performance
- `AvgLatencyMs` - Average response time
- `MinLatencyMs` / `MaxLatencyMs` - Latency range

#### Agency Metrics
- `TotalTasks` - Total tasks processed
- `SuccessfulTasks` / `FailedTasks` - Task outcomes
- `SkillCounts` - Breakdown by skill type

### Accessing Metrics

```go
import "github.com/fulvian/aria/internal/aria/agency/nutrition/metrics"

// Get provider stats
stats := metrics.GlobalMetrics.GetProviderStats("usda")
fmt.Printf("USDA Success Rate: %.2f%%\n", stats.SuccessRate*100)

// Get agency stats
agencyStats := metrics.GlobalMetrics.GetAgencyStats()
fmt.Printf("Total Tasks: %d\n", agencyStats.TotalTasks)

// Reset metrics
metrics.GlobalMetrics.Reset()
```

---

## Guardrails

### Medical Disclaimer Guardrails

When `ARIA_NUTRITION_ENABLE_MEDICAL_GUARDRAILS=true`:

1. **Diet Planning**: Results include disclaimer "Not a substitute for professional medical advice"
2. **Nutrition Analysis**: Clarifies this is informational, not medical diagnosis
3. **Supplement Warnings**: Flags when users ask about supplements vs food

### Recommended User Warnings

The agency outputs appropriate warnings for:

| Scenario | Warning |
|----------|---------|
| Diet planning | "Consult a healthcare provider before starting any diet" |
| Supplement questions | "Supplements should not replace whole foods" |
| Allergen concerns | "Always verify allergens with manufacturer" |
| Medical conditions | "This information is not a substitute for medical advice" |

---

## Troubleshooting

### Common Issues

#### USDA API Returns 403 Forbidden
- **Cause**: Invalid or expired API key
- **Fix**: Regenerate key at https://fdc.nal.usda.gov/api-key.html

#### Open Food Facts Rate Limited
- **Cause**: Too many requests
- **Fix**: Implement request throttling, use cache

#### MealDB Search Returns Empty
- **Cause**: API key issue or network problem
- **Fix**: Verify API key, check network connectivity

#### openFDA Errors
- **Cause**: Rate limit exceeded or service down
- **Fix**: Wait and retry, check https://open.fda.gov/status

### Debug Mode

Enable verbose logging:

```bash
export ARIA_LOG_LEVEL=debug
./aria -d
```

### Health Check

Verify agency is running:

```bash
./aria -p "check nutrition agency status"
```
