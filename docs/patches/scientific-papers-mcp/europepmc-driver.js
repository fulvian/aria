/**
 * Europe PMC Driver - Week 3 Implementation
 *
 * Provides access to Europe PMC's collection of life science literature
 * Uses REST API with full-text filtering capabilities
 */
import axios from "axios";
import { BaseDriver } from "./base-driver.js";
import { logInfo, logError, logWarn } from "../core/logger.js";
import { HtmlExtractor } from "../extractors/html-extractor.js";
import { DEFAULT_TEXT_EXTRACTION_CONFIG } from "../config/constants.js";
export class EuropePMCDriver extends BaseDriver {
    textExtractor;
    apiBase = "https://www.ebi.ac.uk/europepmc/webservices/rest";
    // Europe PMC subject categories
    europePMCCategories = [
        {
            id: "life_sciences",
            name: "Life Sciences",
            description: "General life science research",
        },
        {
            id: "medicine",
            name: "Medicine",
            description: "Medical and clinical research",
        },
        { id: "biology", name: "Biology", description: "Biological sciences" },
        {
            id: "biochemistry",
            name: "Biochemistry",
            description: "Biochemical studies",
        },
        { id: "genetics", name: "Genetics", description: "Genetic research" },
        {
            id: "molecular_biology",
            name: "Molecular Biology",
            description: "Molecular biological studies",
        },
        {
            id: "cell_biology",
            name: "Cell Biology",
            description: "Cellular research",
        },
        {
            id: "neuroscience",
            name: "Neuroscience",
            description: "Neurological studies",
        },
        {
            id: "immunology",
            name: "Immunology",
            description: "Immune system research",
        },
        {
            id: "cancer",
            name: "Cancer Research",
            description: "Oncological studies",
        },
        {
            id: "pharmacology",
            name: "Pharmacology",
            description: "Drug research and development",
        },
        {
            id: "bioinformatics",
            name: "Bioinformatics",
            description: "Computational biology",
        },
        {
            id: "structural_biology",
            name: "Structural Biology",
            description: "Protein and molecular structure",
        },
        {
            id: "ecology",
            name: "Ecology",
            description: "Environmental and ecological studies",
        },
    ];
    constructor(rateLimiter) {
        super(rateLimiter, "europepmc");
        this.textExtractor = new HtmlExtractor(DEFAULT_TEXT_EXTRACTION_CONFIG);
    }
    /**
     * List Europe PMC categories
     */
    async listCategories() {
        logInfo("Fetching Europe PMC categories");
        return this.europePMCCategories;
    }
    /**
     * Fetch latest papers from Europe PMC for a given category
     */
    async fetchLatest(category, count) {
        if (!this.checkRateLimit()) {
            const retryAfter = this.getRetryAfter();
            logWarn("Rate limited when fetching latest Europe PMC papers", {
                retryAfter,
                category,
            });
            throw new Error(`Rate limited. Retry after ${retryAfter} seconds`);
        }
        try {
            logInfo("Fetching latest Europe PMC papers", { category, count });
            // Build search query with full-text filter
            const searchQuery = this.buildSearchQuery(category);
            const response = await axios.get(`${this.apiBase}/search`, {
                params: {
                    query: `${searchQuery} AND has_fulltext:y`, // Filter for full-text availability
                    format: "json",
                    pageSize: Math.min(count, 100), // Europe PMC allows up to 100 results per page
                    sort: "date desc", // Sort by publication date, newest first
                    resultType: "core",
                },
                timeout: 15000,
                headers: {
                    "User-Agent": "SciHarvester-MCP/0.1.27 (mailto:contact@sciharvestermcp.org); Europe-PMC-client",
                },
            });
            console.error("EPMC_DEBUG searchQuery:", JSON.stringify(response.config.params.query));
            console.error("EPMC_DEBUG status:", response.status);
            console.error("EPMC_DEBUG data keys:", Object.keys(response.data || {}));
            console.error("EPMC_DEBUG has resultList:", !!(response.data && response.data.resultList));
            console.error("EPMC_DEBUG has resultList.result:", !!(response.data && response.data.resultList && response.data.resultList.result));
            console.error("EPMC_DEBUG result count:", response.data && response.data.resultList && response.data.resultList.result ? response.data.resultList.result.length : 0);
            console.error("EPMC_DEBUG first result:", JSON.stringify(response.data && response.data.resultList && response.data.resultList.result ? response.data.resultList.result[0] : null).substring(0, 500));
            if (!response.data ||
                !response.data.resultList ||
                !response.data.resultList.result) {
                logWarn("Europe PMC API returned unexpected response format", {
                    category,
                    searchQuery,
                    responseData: response.data,
                });
                return [];
            }
            const results = response.data.resultList.result;
            if (results.length === 0) {
                logWarn("No Europe PMC papers found for category", {
                    category,
                    searchQuery,
                });
                return [];
            }
            // Convert results to PaperMetadata format (metadata only)
            // FIXED v2: hasFullText is often '?' (unknown), not just 'Y'
            // Filtering only 'Y' was too aggressive and discarded valid results
            const validResults = results.filter((result) => result.title && result.hasFullText !== "N" && result.hasFullText !== "n");
            const papers = await Promise.all(validResults.map((result) => this.convertResultToPaper(result, false)));
            logInfo("Successfully fetched Europe PMC latest papers", {
                count: papers.length,
                category,
            });
            return papers;
        }
        catch (error) {
            logError("Failed to fetch latest Europe PMC papers", {
                error: error instanceof Error ? error.message : error,
                category,
                count,
            });
            if (axios.isAxiosError(error)) {
                if (error.response?.status === 429) {
                    throw new Error("Rate limited by Europe PMC API");
                }
                if (error.response?.status && error.response.status >= 500) {
                    throw new Error("Europe PMC API server error");
                }
            }
            throw error;
        }
    }
    /**
     * Fetch content for a specific Europe PMC paper by ID
     */
    async fetchContent(id) {
        if (!this.checkRateLimit()) {
            const retryAfter = this.getRetryAfter();
            logWarn("Rate limited when fetching Europe PMC paper content", {
                retryAfter,
                id,
            });
            throw new Error(`Rate limited. Retry after ${retryAfter} seconds`);
        }
        try {
            logInfo("Fetching Europe PMC paper content", { id });
            // Determine source and clean ID
            const { source, cleanId } = this.parseId(id);
            // Fetch paper details
            const detailsUrl = `${this.apiBase}/search`;
            const response = await axios.get(detailsUrl, {
                params: {
                    query: `${source}:${cleanId}`,
                    format: "json",
                    resultType: "core",
                },
                timeout: 15000,
                headers: {
                    "User-Agent": "SciHarvester-MCP/0.1.27 (mailto:contact@sciharvestermcp.org); Europe-PMC-client",
                },
            });
            const results = response.data.resultList.result;
            if (results.length === 0) {
                throw new Error(`Paper with ID ${id} not found in Europe PMC`);
            }
            const result = results[0];
            // Convert to paper format with full text extraction
            const paper = await this.convertResultToPaper(result, true);
            logInfo("Successfully fetched Europe PMC paper content", {
                id,
                title: paper.title,
            });
            return paper;
        }
        catch (error) {
            logError("Failed to fetch Europe PMC paper content", {
                error: error instanceof Error ? error.message : error,
                id,
            });
            if (axios.isAxiosError(error)) {
                if (error.response?.status === 404) {
                    throw new Error(`Paper with ID ${id} not found in Europe PMC`);
                }
                if (error.response?.status === 429) {
                    throw new Error("Rate limited by Europe PMC API");
                }
                if (error.response?.status && error.response.status >= 500) {
                    throw new Error("Europe PMC API server error");
                }
            }
            throw error;
        }
    }
    /**
     * Convert Europe PMC result to PaperMetadata format
     */
    async convertResultToPaper(result, includeText = false) {
        // Extract authors
        let authors = [];
        if (result.authorList?.author) {
            authors = result.authorList.author.map((author) => author.fullName ||
                `${author.firstName || ""} ${author.lastName || ""}`.trim());
        }
        else if (result.authorString) {
            // Fallback to author string, split by common delimiters
            authors = result.authorString
                .split(/[,;]|\sand\s/)
                .map((author) => author.trim())
                .filter((author) => author.length > 0);
        }
        // Format date
        const date = result.pubYear
            ? `${result.pubYear}-01-01`
            : new Date().toISOString().split("T")[0];
        // Determine ID (prefer PMC, then PMID, then source ID)
        const paperId = result.pmcid || result.pmid || result.id;
        // Build URLs
        const baseUrl = "https://europepmc.org/article";
        let pdf_url;
        let landingUrl;
        if (result.pmcid) {
            landingUrl = `${baseUrl}/PMC/${result.pmcid.replace("PMC", "")}`;
            pdf_url = `${baseUrl}/PMC/${result.pmcid.replace("PMC", "")}/pdf`;
        }
        else if (result.pmid) {
            landingUrl = `${baseUrl}/MED/${result.pmid}`;
        }
        else {
            landingUrl = `${baseUrl}/${result.source.toUpperCase()}/${result.id}`;
        }
        // Create base paper object
        const paper = {
            id: paperId,
            title: result.title || "Untitled",
            authors,
            date,
            pdf_url,
            text: "", // Always include text field, empty for metadata-only
        };
        // Only extract text if requested (for fetch_content)
        if (includeText) {
            let textTruncated = false;
            let textExtractionFailed = false;
            try {
                if (this.checkRateLimit()) {
                    // Extract from Europe PMC landing page
                    const extractionResult = await this.textExtractor.extractText(landingUrl);
                    if (extractionResult.extractionSuccess) {
                        paper.text = extractionResult.text;
                        textTruncated = extractionResult.truncated;
                        logInfo("Text extraction successful from Europe PMC landing page", {
                            id: paperId,
                            url: landingUrl,
                            textLength: paper.text.length,
                            truncated: textTruncated,
                        });
                    }
                    else {
                        textExtractionFailed = true;
                        logWarn("Text extraction failed from Europe PMC landing page", {
                            id: paperId,
                        });
                    }
                }
                else {
                    textExtractionFailed = true;
                    logWarn("Rate limited for text extraction", { id: paperId });
                }
            }
            catch (error) {
                textExtractionFailed = true;
                logError("Error during text extraction for Europe PMC paper", {
                    id: paperId,
                    error: error instanceof Error ? error.message : error,
                });
            }
            // Add warning flags if needed
            if (textTruncated) {
                paper.textTruncated = true;
            }
            if (textExtractionFailed) {
                paper.textExtractionFailed = true;
            }
        }
        return paper;
    }
    /**
     * Parse query into quoted phrases and individual terms.
     * Handles queries like: "state space model" Mamba efficient transformer
     */
    _parseQuery(q) {
        const phrases = [];
        const terms = [];
        let i = 0;
        while (i < q.length) {
            if (q[i] === '"') {
                const end = q.indexOf('"', i + 1);
                if (end > i + 1) {
                    const phrase = q.substring(i + 1, end).trim();
                    if (phrase) phrases.push(phrase);
                    i = end + 1;
                } else {
                    i++;
                }
            } else if (q[i] !== ' ') {
                const end = q.indexOf(' ', i);
                const term = (end > i ? q.substring(i, end) : q.substring(i)).trim();
                if (term) terms.push(term);
                i = end > i ? end + 1 : q.length;
            } else {
                i++;
            }
        }
        return { phrases, terms };
    }

    /**
     * Search for papers with query and field-specific options
     *
     * FIXED v2: Properly handles multi-term queries with Boolean AND.
     * Previously wrapped entire query in quotes causing phrase-only search.
     * Now extracts quoted phrases + individual terms and joins with AND.
     */
    async searchPapers(query, field, count, sortBy) {
        if (!this.checkRateLimit()) {
            const retryAfter = this.getRetryAfter();
            logWarn("Rate limited when searching Europe PMC papers", {
                retryAfter,
                query,
                field,
            });
            throw new Error(`Rate limited. Retry after ${retryAfter} seconds`);
        }
        try {
            logInfo("Searching Europe PMC papers", { query, field, count, sortBy });
            // Build search query based on field
            // FIXED v2: Use Boolean AND for multi-term searches
            // Old: "query" — wrapped entire query in quotes causing phrase-only match
            let searchQuery;
            switch (field) {
                case "title": {
                    const parsed = this._parseQuery(query);
                    const parts = [
                        ...parsed.phrases.map((p) => `TITLE:"${p}"`),
                        ...parsed.terms.map((t) => `TITLE:"${t}"`),
                    ];
                    searchQuery = parts.length > 0 ? parts.join(" AND ") : `TITLE:"${query}"`;
                    break;
                }
                case "abstract": {
                    const parsed = this._parseQuery(query);
                    const parts = [
                        ...parsed.phrases.map((p) => `ABSTRACT:"${p}"`),
                        ...parsed.terms.map((t) => `ABSTRACT:"${t}"`),
                    ];
                    searchQuery = parts.length > 0 ? parts.join(" AND ") : `ABSTRACT:"${query}"`;
                    break;
                }
                case "author":
                    searchQuery = `AUTH:"${query}"`;
                    break;
                case "fulltext":
                    searchQuery = `FULL_TEXT:"${query}"`;
                    break;
                case "all":
                default: {
                    // EuropePMC searches all fields by default
                    // Use parsed query with AND boolean for best results
                    const parsed = this._parseQuery(query);
                    const parts = [
                        ...parsed.phrases.map((p) => `"${p}"`),
                        ...parsed.terms.map((t) => t),
                    ];
                    searchQuery = parts.length > 0 ? parts.join(" AND ") : query;
                    break;
                }
            }
            // Add full-text filter for better results
            searchQuery += " AND has_fulltext:y";
            // Map sortBy to Europe PMC API parameters
            // FIXED v2: EuropePMC's sort parameter uses different values.
            // 'relevance' (lowercase) breaks the API - returns 0 hits.
            // Omitting sort param defaults to relevance ordering.
            let responseParams = {
                query: searchQuery,
                format: "json",
                pageSize: Math.min(count, 100),
                resultType: "core",
            };
            switch (sortBy) {
                case "date":
                    responseParams.sort = "date desc";
                    break;
                case "citations":
                    responseParams.sort = "citedby desc";
                    break;
                case "relevance":
                default:
                    // Do not send sort param — EuropePMC defaults to relevance
                    break;
            }
            const response = await axios.get(`${this.apiBase}/search`, {
                params: responseParams,
                timeout: 15000,
                headers: {
                    "User-Agent": "SciHarvester-MCP/0.1.27 (mailto:contact@sciharvestermcp.org); Europe-PMC-client",
                },
            });
            console.error("EPMC_DEBUG searchQuery:", JSON.stringify(response.config.params.query));
            console.error("EPMC_DEBUG status:", response.status);
            console.error("EPMC_DEBUG data keys:", Object.keys(response.data || {}));
            console.error("EPMC_DEBUG has resultList:", !!(response.data && response.data.resultList));
            console.error("EPMC_DEBUG has resultList.result:", !!(response.data && response.data.resultList && response.data.resultList.result));
            console.error("EPMC_DEBUG result count:", response.data && response.data.resultList && response.data.resultList.result ? response.data.resultList.result.length : 0);
            console.error("EPMC_DEBUG first result:", JSON.stringify(response.data && response.data.resultList && response.data.resultList.result ? response.data.resultList.result[0] : null).substring(0, 500));
            if (!response.data ||
                !response.data.resultList ||
                !response.data.resultList.result) {
                logWarn("Europe PMC API returned unexpected response format", {
                    query,
                    field,
                    searchQuery,
                    responseData: response.data,
                });
                return [];
            }
            const results = response.data.resultList.result;
            if (results.length === 0) {
                logWarn("No Europe PMC papers found for search", {
                    query,
                    field,
                    searchQuery,
                });
                return [];
            }
            // Convert results to PaperMetadata format (metadata only)
            // FIXED v2: hasFullText is often '?' (unknown), not just 'Y'
            // Filtering only 'Y' was too aggressive and discarded valid results
            const validResults = results.filter((result) => result.title && result.hasFullText !== "N" && result.hasFullText !== "n");
            const papers = await Promise.all(validResults.map((result) => this.convertResultToPaper(result, false)));
            logInfo("Successfully searched Europe PMC papers", {
                query,
                field,
                count: papers.length,
                sortBy,
            });
            return papers;
        }
        catch (error) {
            logError("Failed to search Europe PMC papers", {
                error: error instanceof Error ? error.message : error,
                query,
                field,
                count,
                sortBy,
            });
            if (axios.isAxiosError(error)) {
                if (error.response?.status === 429) {
                    throw new Error("Rate limited by Europe PMC API");
                }
                if (error.response?.status && error.response.status >= 500) {
                    throw new Error("Europe PMC API server error");
                }
            }
            throw error;
        }
    }
    /**
     * Build search query for Europe PMC based on category
     */
    buildSearchQuery(category) {
        const categoryMapping = {
            life_sciences: '(MESH:"Life Sciences" OR "life science*")',
            medicine: '(MESH:"Medicine" OR "medical" OR "clinical")',
            biology: '(MESH:"Biology" OR "biological science*")',
            biochemistry: '(MESH:"Biochemistry" OR "biochemical")',
            genetics: '(MESH:"Genetics" OR "genetic*")',
            molecular_biology: '(MESH:"Molecular Biology" OR "molecular biological")',
            cell_biology: '(MESH:"Cell Biology" OR "cellular")',
            neuroscience: '(MESH:"Neurosciences" OR "neuroscience" OR "neurological")',
            immunology: '(MESH:"Immunology" OR "immune*" OR "immunological")',
            cancer: '(MESH:"Neoplasms" OR "cancer" OR "oncology" OR "tumor")',
            pharmacology: '(MESH:"Pharmacology" OR "drug*" OR "pharmaceutical")',
            bioinformatics: '("bioinformatics" OR "computational biology")',
            structural_biology: '("structural biology" OR "protein structure")',
            ecology: '(MESH:"Ecology" OR "ecological" OR "environmental")',
        };
        // Use predefined mapping or fallback to general search
        return categoryMapping[category.toLowerCase()] || `"${category}"`;
    }
    /**
     * Parse ID to determine source and clean format
     */
    parseId(id) {
        if (id.startsWith("PMC")) {
            return { source: "PMC", cleanId: id.replace("PMC", "") };
        }
        else if (/^\d+$/.test(id)) {
            return { source: "MED", cleanId: id }; // Assume PMID if all digits
        }
        else if (id.includes("10.")) {
            return { source: "DOI", cleanId: id };
        }
        else {
            return { source: "EXT", cleanId: id };
        }
    }
}
//# sourceMappingURL=europepmc-driver.js.map