// Package agency provides the Knowledge Agency implementation.
package agency

import (
	"context"
	"strings"
)

// SimpleEmbedder uses keyword-based scoring as a fallback embedding mechanism.
// It creates simple TF-IDF-like vectors based on keyword matching.
// Production implementations would use proper embeddings via OpenAI, local models,
// or specialized embedding services.
type SimpleEmbedder struct {
	// dimensionKeywords maps each dimension index to its associated keywords
	// including both English and Italian terms for multilingual support
	dimensionKeywords [][]string
}

// NewSimpleEmbedder creates a new SimpleEmbedder with default dimensions and keywords.
func NewSimpleEmbedder() *SimpleEmbedder {
	return &SimpleEmbedder{
		// Each dimension has multiple associated keywords in English and Italian
		dimensionKeywords: [][]string{
			// 0: academic - academic, research, paper, scientific, journal, doi, arxiv, pubmed
			{"academic", "research", "paper", "scientific", "journal", "doi", "arxiv", "pubmed", "studio", "ricerca", "cartaceo", "pubblicazione", "machine learning", "ml", "deep learning", "neural", "algoritmo"},
			// 1: news - news, current events, headlines, newspaper, reuters, bbc
			{"news", "current", "events", "headlines", "newspaper", "reuters", "bbc", "notizie", "attualità", "cronaca", "giornale", "recenti", "latest", "today", "breaking", "headlines"},
			// 2: code - code, programming, api, github, function, library, sdk
			{"code", "programming", "api", "github", "function", "library", "sdk", "codice", "programmazione", "funzione", "codice sorgente", "software", "script", "debug", "repository"},
			// 3: research - research, study, analysis (overlaps with academic)
			{"research", "study", "analysis", "analisi", "studio", "indagine", "investigate", "survey"},
			// 4: search - search, find, look up
			{"search", "find", "look up", "cerca", "trova", "cercalo", "ricerca", "informazioni", "lookup", "dammi", "cerca", "trovare"},
			// 5: historical - archive, historical, wayback, past, chronicling
			{"archive", "historical", "wayback", "past", "chronicling", "storico", "archivio", "storia", "passato", "vecchio", "antico", "archivi"},
			// 6: document - document, pdf, article
			{"document", "pdf", "article", "documento", "articolo", "pdf", "file", "report", "paper"},
			// 7: web - web, internet, online
			{"web", "internet", "online", "web", "rete", "in rete", "site", "url", "pagina"},
			// 8: analysis - analysis, analyze, compare
			{"analysis", "analyze", "compare", "analisi", "confronta", "comparare", "differenza", "confronta", "analizzare"},
			// 9: learn - learn, understand, explain, teach
			{"learn", "understand", "explain", "teach", "impara", "capire", "spiega", "insegnamento", "cos'è", "come funziona", "perché", "dammi"},
		},
	}
}

// Encode converts text into a embedding vector using keyword-based scoring.
// Returns a vector where each dimension value is between 0.0 and 1.0
// based on how strongly the text matches each keyword dimension.
func (e *SimpleEmbedder) Encode(ctx context.Context, text string) ([]float32, error) {
	lower := strings.ToLower(text)
	vec := make([]float32, len(e.dimensionKeywords))

	for i, keywords := range e.dimensionKeywords {
		vec[i] = 0.2 // default value
		for _, keyword := range keywords {
			if strings.Contains(lower, keyword) {
				vec[i] = 0.8
				break
			}
		}
	}

	return vec, nil
}

// EncodeWithContext encodes text with additional context words for better matching.
func (e *SimpleEmbedder) EncodeWithContext(ctx context.Context, text string, contextWords []string) ([]float32, error) {
	lower := strings.ToLower(text)
	vec := make([]float32, len(e.dimensionKeywords))

	// Build extended text with context words
	extended := lower
	for _, cw := range contextWords {
		extended += " " + strings.ToLower(cw)
	}

	for i, keywords := range e.dimensionKeywords {
		vec[i] = 0.2 // default value
		for _, keyword := range keywords {
			if strings.Contains(extended, keyword) {
				vec[i] = 0.8
				break
			}
		}
	}

	return vec, nil
}
