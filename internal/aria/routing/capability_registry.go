package routing

import (
	"fmt"
	"sync"
)

// AgencyName identifies a specific agency.
type AgencyName string

// AgentName identifies a specific agent.
type AgentName string

// SkillName identifies a skill.
type SkillName string

// CapabilityRegistry registers and matches agency/agent capabilities.
type CapabilityRegistry interface {
	RegisterAgency(cap AgencyCapability) error
	RegisterAgent(agencyName string, cap AgentCapability) error
	FindAgents(req CapabilityRequest) []AgentCapability
	FindAgencies(req CapabilityRequest) []AgencyCapability
	GetHealth() HealthStatus
}

// AgencyCapability represents the capabilities of an agency.
type AgencyCapability struct {
	Name     AgencyName
	Domain   DomainName
	Skills   []SkillName
	Agents   []AgentName
	CostHint CostHint
	RiskClass RiskClass
	Health   HealthIndicator
}

// AgentCapability represents the capabilities of an agent.
type AgentCapability struct {
	Name     AgentName
	Agency   AgencyName
	Skills   []SkillName
	Tools    []string
	CostHint CostHint
	RiskClass RiskClass
	Health   HealthIndicator
}

// CapabilityRequest defines requirements for matching.
type CapabilityRequest struct {
	Domain    DomainName
	Skills    []SkillName
	MinHealth HealthLevel
	MaxCost   CostHint
	MaxRisk   RiskClass
}

// CostHint provides cost indication.
type CostHint struct {
	TokenBudget  int
	TimeBudgetMs int
}

// RiskClass risk classification.
type RiskClass string

const (
	RiskClassLow    RiskClass = "low"
	RiskClassMedium RiskClass = "medium"
	RiskClassHigh   RiskClass = "high"
)

// HealthLevel health level.
type HealthLevel string

const (
	HealthLevelHealthy     HealthLevel = "healthy"
	HealthLevelDegraded    HealthLevel = "degraded"
	HealthLevelUnavailable HealthLevel = "unavailable"
)

// HealthIndicator health indicator.
type HealthIndicator struct {
	Level      HealthLevel
	Score      int    // 0-100
	Message    string
	LastUpdate int64  // unix timestamp
}

// HealthStatus overall registry health status.
type HealthStatus struct {
	Overall  HealthLevel
	Agencies map[string]HealthIndicator
	Agents   map[string]HealthIndicator
}

// defaultCapabilityRegistry is the default implementation of CapabilityRegistry.
type defaultCapabilityRegistry struct {
	mu       sync.RWMutex
	agencies map[AgencyName]AgencyCapability
	agents   map[AgentName]AgentCapability
}

// NewCapabilityRegistry creates a new defaultCapabilityRegistry.
func NewCapabilityRegistry() *defaultCapabilityRegistry {
	return &defaultCapabilityRegistry{
		agencies: make(map[AgencyName]AgencyCapability),
		agents:   make(map[AgentName]AgentCapability),
	}
}

// RegisterAgency registers an agency's capabilities.
func (r *defaultCapabilityRegistry) RegisterAgency(cap AgencyCapability) error {
	if cap.Name == "" {
		return fmt.Errorf("agency name cannot be empty")
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	r.agencies[cap.Name] = cap
	return nil
}

// RegisterAgent registers an agent's capabilities.
func (r *defaultCapabilityRegistry) RegisterAgent(agencyName string, cap AgentCapability) error {
	if cap.Name == "" {
		return fmt.Errorf("agent name cannot be empty")
	}
	if agencyName == "" {
		return fmt.Errorf("agency name cannot be empty")
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	// Ensure agency exists before registering agent
	found := false
	for name := range r.agencies {
		if string(name) == agencyName {
			found = true
			break
		}
	}
	if !found {
		return fmt.Errorf("agency %q not found in registry", agencyName)
	}

	r.agents[cap.Name] = cap
	return nil
}

// FindAgents finds agents matching the request criteria.
func (r *defaultCapabilityRegistry) FindAgents(req CapabilityRequest) []AgentCapability {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var matches []AgentCapability

	for _, agent := range r.agents {
		if r.agentMatches(agent, req) {
			matches = append(matches, agent)
		}
	}

	// Sort by fitness (higher score = better match)
	sortAgentMatches(matches)

	return matches
}

// FindAgencies finds agencies matching the request criteria.
func (r *defaultCapabilityRegistry) FindAgencies(req CapabilityRequest) []AgencyCapability {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var matches []AgencyCapability

	for _, agency := range r.agencies {
		if r.agencyMatches(agency, req) {
			matches = append(matches, agency)
		}
	}

	// Sort by fitness
	sortAgencyMatches(matches)

	return matches
}

// GetHealth returns aggregated health status.
func (r *defaultCapabilityRegistry) GetHealth() HealthStatus {
	r.mu.RLock()
	defer r.mu.RUnlock()

	status := HealthStatus{
		Overall:   HealthLevelHealthy,
		Agencies:  make(map[string]HealthIndicator),
		Agents:    make(map[string]HealthIndicator),
	}

	// Aggregate agency health
	minLevel := HealthLevelHealthy
	for name, agency := range r.agencies {
		status.Agencies[string(name)] = agency.Health
		if healthLevelToInt(agency.Health.Level) < healthLevelToInt(minLevel) {
			minLevel = agency.Health.Level
		}
	}

	// Aggregate agent health
	for name, agent := range r.agents {
		status.Agents[string(name)] = agent.Health
		if healthLevelToInt(agent.Health.Level) < healthLevelToInt(minLevel) {
			minLevel = agent.Health.Level
		}
	}

	status.Overall = minLevel
	return status
}

// agentMatches checks if an agent matches the request criteria.
func (r *defaultCapabilityRegistry) agentMatches(agent AgentCapability, req CapabilityRequest) bool {
	// Check agency domain if domain filter is specified
	if req.Domain != "" {
		agency, found := r.agencies[agent.Agency]
		if !found || agency.Domain != req.Domain {
			return false
		}
	}

	// Check health level
	if req.MinHealth != "" {
		if healthLevelToInt(agent.Health.Level) < healthLevelToInt(req.MinHealth) {
			return false
		}
	}

	// Check risk class
	if req.MaxRisk != "" {
		if riskClassToInt(agent.RiskClass) > riskClassToInt(req.MaxRisk) {
			return false
		}
	}

	// Check cost
	if req.MaxCost.TokenBudget > 0 {
		if agent.CostHint.TokenBudget > req.MaxCost.TokenBudget {
			return false
		}
	}
	if req.MaxCost.TimeBudgetMs > 0 {
		if agent.CostHint.TimeBudgetMs > req.MaxCost.TimeBudgetMs {
			return false
		}
	}

	// Check skills (agent must have at least one of the requested skills)
	if len(req.Skills) > 0 {
		hasSkill := false
		for _, reqSkill := range req.Skills {
			for _, agentSkill := range agent.Skills {
				if reqSkill == agentSkill {
					hasSkill = true
					break
				}
			}
			if hasSkill {
				break
			}
		}
		if !hasSkill {
			return false
		}
	}

	return true
}

// agencyMatches checks if an agency matches the request criteria.
func (r *defaultCapabilityRegistry) agencyMatches(agency AgencyCapability, req CapabilityRequest) bool {
	// Check domain
	if req.Domain != "" && agency.Domain != req.Domain {
		return false
	}

	// Check health level
	if req.MinHealth != "" {
		if healthLevelToInt(agency.Health.Level) < healthLevelToInt(req.MinHealth) {
			return false
		}
	}

	// Check risk class
	if req.MaxRisk != "" {
		if riskClassToInt(agency.RiskClass) > riskClassToInt(req.MaxRisk) {
			return false
		}
	}

	// Check cost
	if req.MaxCost.TokenBudget > 0 {
		if agency.CostHint.TokenBudget > req.MaxCost.TokenBudget {
			return false
		}
	}
	if req.MaxCost.TimeBudgetMs > 0 {
		if agency.CostHint.TimeBudgetMs > req.MaxCost.TimeBudgetMs {
			return false
		}
	}

	// Check skills (agency must have at least one of the requested skills)
	if len(req.Skills) > 0 {
		hasSkill := false
		for _, reqSkill := range req.Skills {
			for _, agencySkill := range agency.Skills {
				if reqSkill == agencySkill {
					hasSkill = true
					break
				}
			}
			if hasSkill {
				break
			}
		}
		if !hasSkill {
			return false
		}
	}

	return true
}

// sortAgentMatches sorts agents by fitness score (higher = better).
func sortAgentMatches(agents []AgentCapability) {
	// Simple scoring: lower risk = higher fitness, lower cost = higher fitness
	// We use a basic sort by risk class first, then by skill count
	for i := 0; i < len(agents)-1; i++ {
		for j := i + 1; j < len(agents); j++ {
			scoreI := agentFitnessScore(agents[i])
			scoreJ := agentFitnessScore(agents[j])
			if scoreI < scoreJ {
				agents[i], agents[j] = agents[j], agents[i]
			}
		}
	}
}

// sortAgencyMatches sorts agencies by fitness score.
func sortAgencyMatches(agencies []AgencyCapability) {
	for i := 0; i < len(agencies)-1; i++ {
		for j := i + 1; j < len(agencies); j++ {
			scoreI := agencyFitnessScore(agencies[i])
			scoreJ := agencyFitnessScore(agencies[j])
			if scoreI < scoreJ {
				agencies[i], agencies[j] = agencies[j], agencies[i]
			}
		}
	}
}

// agentFitnessScore calculates a fitness score for an agent.
func agentFitnessScore(agent AgentCapability) int {
	score := 0

	// Lower risk = higher score
	switch agent.RiskClass {
	case RiskClassLow:
		score += 30
	case RiskClassMedium:
		score += 20
	case RiskClassHigh:
		score += 10
	}

	// Healthier = higher score
	switch agent.Health.Level {
	case HealthLevelHealthy:
		score += 30
	case HealthLevelDegraded:
		score += 15
	case HealthLevelUnavailable:
		score += 0
	}

	// More skills = higher score
	score += len(agent.Skills) * 5

	// Lower cost = higher score
	if agent.CostHint.TokenBudget > 0 {
		score += 1000 - min(agent.CostHint.TokenBudget/100, 100)
	}

	return score
}

// agencyFitnessScore calculates a fitness score for an agency.
func agencyFitnessScore(agency AgencyCapability) int {
	score := 0

	// Lower risk = higher score
	switch agency.RiskClass {
	case RiskClassLow:
		score += 30
	case RiskClassMedium:
		score += 20
	case RiskClassHigh:
		score += 10
	}

	// Healthier = higher score
	switch agency.Health.Level {
	case HealthLevelHealthy:
		score += 30
	case HealthLevelDegraded:
		score += 15
	case HealthLevelUnavailable:
		score += 0
	}

	// More skills = higher score
	score += len(agency.Skills) * 5

	// More agents = higher score (usually indicates more capability)
	score += len(agency.Agents) * 3

	return score
}

// healthLevelToInt converts health level to numeric value.
func healthLevelToInt(level HealthLevel) int {
	switch level {
	case HealthLevelHealthy:
		return 3
	case HealthLevelDegraded:
		return 2
	case HealthLevelUnavailable:
		return 1
	default:
		return 0
	}
}

// riskClassToInt converts risk class to numeric value (higher = more risky).
func riskClassToInt(risk RiskClass) int {
	switch risk {
	case RiskClassLow:
		return 1
	case RiskClassMedium:
		return 2
	case RiskClassHigh:
		return 3
	default:
		return 0
	}
}

// min returns the minimum of two integers.
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
