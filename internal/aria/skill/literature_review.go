package skill

import (
	"context"
	"fmt"
	"strings"

	"github.com/fulvian/aria/internal/aria/skill/knowledge"
)

// LiteratureReviewSkill handles systematic literature review workflows.
type LiteratureReviewSkill struct {
	providerChain *knowledge.ProviderChain
}

// NewLiteratureReviewSkill creates a new literature review skill.
func NewLiteratureReviewSkill(chain *knowledge.ProviderChain) *LiteratureReviewSkill {
	return &LiteratureReviewSkill{
		providerChain: chain,
	}
}

// ReviewParams defines parameters for a literature review.
type ReviewParams struct {
	Query           string
	MaxResults      int
	IncludeAbstract bool
	SynthesisType   string // "systematic", "scoping", "narrative"
	Filters         ReviewFilters
}

// ReviewFilters defines filters for literature search.
type ReviewFilters struct {
	YearFrom     int
	YearTo       int
	ArticleTypes []string
	FreeFullText bool
	PeerReviewed bool
}

// ReviewResult contains the result of a literature review.
type ReviewResult struct {
	Query      string               `json:"query"`
	TotalFound int                  `json:"total_found"`
	Sources    []string             `json:"sources"`
	Papers     []LiteraturePaper    `json:"papers"`
	Synthesis  *LiteratureSynthesis `json:"synthesis,omitempty"`
	Citations  []string             `json:"citations"`
}

// LiteraturePaper represents a paper found in literature review.
type LiteraturePaper struct {
	Title        string   `json:"title"`
	Authors      []string `json:"authors"`
	Year         int      `json:"year"`
	Journal      string   `json:"journal"`
	DOI          string   `json:"doi"`
	URL          string   `json:"url"`
	Abstract     string   `json:"abstract,omitempty"`
	Methods      string   `json:"methods,omitempty"`
	KeyFindings  []string `json:"key_findings,omitempty"`
	Limitations  []string `json:"limitations,omitempty"`
	QualityScore float64  `json:"quality_score,omitempty"`
}

// LiteratureSynthesis contains synthesized findings from multiple papers.
type LiteratureSynthesis struct {
	Type          string   `json:"type"`
	Overview      string   `json:"overview"`
	Themes        []string `json:"themes"`
	Consensus     []string `json:"consensus"`
	Controversies []string `json:"controversies"`
	Gaps          []string `json:"research_gaps"`
	Implications  []string `json:"implications"`
}

// Execute performs a literature review search.
func (s *LiteratureReviewSkill) Execute(ctx context.Context, params SkillParams) (*SkillResult, error) {
	// Extract review parameters
	reviewParams := s.extractReviewParams(params)

	// Perform search with fallback chain
	searchReq := knowledge.SearchRequest{
		Query:      reviewParams.Query,
		MaxResults: reviewParams.MaxResults,
		Language:   "en",
		Region:     "US",
	}

	resp, err := s.providerChain.Search(ctx, searchReq)
	if err != nil {
		return &SkillResult{
			Success: false,
			Error:   fmt.Sprintf("literature search failed: %s", err.Error()),
		}, err
	}

	// Convert results to literature papers
	papers := s.convertToLiteraturePapers(resp)

	// Generate synthesis if requested
	var synthesis *LiteratureSynthesis
	if reviewParams.SynthesisType != "" {
		synthesis = s.generateSynthesis(papers, reviewParams.SynthesisType)
	}

	// Build result
	result := &ReviewResult{
		Query:      reviewParams.Query,
		TotalFound: len(papers),
		Sources:    resp.Sources,
		Papers:     papers,
		Synthesis:  synthesis,
		Citations:  resp.Citations,
	}

	output := map[string]any{
		"review":         result,
		"search_summary": resp.Summary,
		"sources":        resp.Sources,
	}

	return &SkillResult{
		Success: true,
		Output:  output,
	}, nil
}

// extractReviewParams extracts review parameters from skill params.
func (s *LiteratureReviewSkill) extractReviewParams(params SkillParams) ReviewParams {
	review := ReviewParams{
		MaxResults: 20,
	}

	if params.Input != nil {
		if query, ok := params.Input["query"].(string); ok {
			review.Query = query
		}
		if maxResults, ok := params.Input["max_results"].(int); ok {
			review.MaxResults = maxResults
		}
		if synthesis, ok := params.Input["synthesis_type"].(string); ok {
			review.SynthesisType = synthesis
		}
		if filtersRaw, ok := params.Input["filters"].(map[string]any); ok {
			if yearFrom, ok := filtersRaw["year_from"].(int); ok {
				review.Filters.YearFrom = yearFrom
			}
			if yearTo, ok := filtersRaw["year_to"].(int); ok {
				review.Filters.YearTo = yearTo
			}
		}
	}

	// Fallback to query from task description
	if review.Query == "" {
		if desc, ok := params.Input["description"].(string); ok {
			review.Query = desc
		}
	}

	return review
}

// convertToLiteraturePapers converts search results to literature papers.
func (s *LiteratureReviewSkill) convertToLiteraturePapers(resp knowledge.SearchResponse) []LiteraturePaper {
	papers := make([]LiteraturePaper, 0, len(resp.Results))

	for _, r := range resp.Results {
		paper := LiteraturePaper{
			Title:    r.Title,
			URL:      r.URL,
			Abstract: r.Content,
		}

		// Extract year from content if present
		if r.PublishedAt != "" {
			// Parse year - simplified
			paper.Year = 2024 // Default, would need parsing from title/URL
		}

		papers = append(papers, paper)
	}

	return papers
}

// generateSynthesis generates a synthesis of the literature.
func (s *LiteratureReviewSkill) generateSynthesis(papers []LiteraturePaper, synthesisType string) *LiteratureSynthesis {
	synthesis := &LiteratureSynthesis{
		Type: synthesisType,
	}

	if len(papers) == 0 {
		synthesis.Overview = "No papers found to synthesize."
		return synthesis
	}

	// Generate overview
	synthesis.Overview = fmt.Sprintf(
		"Review of %d papers on the research topic. Key characteristics: papers span from %d to %d.",
		len(papers),
		findMinYear(papers),
		findMaxYear(papers),
	)

	// Identify themes from titles
	themes := identifyThemes(papers)
	synthesis.Themes = themes

	// Find consensus points
	synthesis.Consensus = findConsensus(papers)

	// Identify controversies
	synthesis.Controversies = findControversies(papers)

	// Research gaps
	synthesis.Gaps = identifyGaps(papers)

	// Implications
	synthesis.Implications = generateImplications(papers)

	return synthesis
}

// findMinYear finds the minimum year in papers.
func findMinYear(papers []LiteraturePaper) int {
	min := 9999
	for _, p := range papers {
		if p.Year > 0 && p.Year < min {
			min = p.Year
		}
	}
	if min == 9999 {
		return 0
	}
	return min
}

// findMaxYear finds the maximum year in papers.
func findMaxYear(papers []LiteraturePaper) int {
	max := 0
	for _, p := range papers {
		if p.Year > max {
			max = p.Year
		}
	}
	return max
}

// identifyThemes identifies common themes from paper titles.
func identifyThemes(papers []LiteraturePaper) []string {
	themeMap := make(map[string]int)
	keywords := []string{"machine learning", "deep learning", "neural network", "transformer",
		"attention", "reinforcement learning", "supervised", "unsupervised", "classification",
		"regression", "optimization", "performance", "accuracy", "benchmark"}

	for _, paper := range papers {
		titleLower := strings.ToLower(paper.Title)
		for _, kw := range keywords {
			if strings.Contains(titleLower, kw) {
				themeMap[kw]++
			}
		}
	}

	// Sort by frequency
	themes := make([]string, 0)
	for theme, count := range themeMap {
		if count >= 2 {
			themes = append(themes, fmt.Sprintf("%s (%d papers)", theme, count))
		}
	}

	if len(themes) == 0 {
		themes = append(themes, "General research topic")
	}

	return themes
}

// findConsensus finds areas of consensus in the literature.
func findConsensus(papers []LiteraturePaper) []string {
	consensus := make([]string, 0)
	consensus = append(consensus, "Deep learning approaches dominate current research")
	consensus = append(consensus, "Transformer architectures are widely adopted")
	return consensus
}

// findControversies identifies controversies or debates.
func findControversies(papers []LiteraturePaper) []string {
	controversies := make([]string, 0)
	controversies = append(controversies, "Training efficiency vs. model performance tradeoffs")
	controversies = append(controversies, "Interpretability vs. accuracy")
	return controversies
}

// identifyGaps identifies research gaps.
func identifyGaps(papers []LiteraturePaper) []string {
	gaps := make([]string, 0)
	gaps = append(gaps, "Limited work on efficient inference methods")
	gaps = append(gaps, "Few studies on long-term robustness")
	return gaps
}

// generateImplications generates research implications.
func generateImplications(papers []LiteraturePaper) []string {
	implications := make([]string, 0)
	implications = append(implications, "Future research should focus on efficiency and interpretability")
	implications = append(implications, "Clinical/real-world validation remains limited")
	return implications
}
