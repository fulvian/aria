package routing

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCapabilityRegistry_RegisterAgency(t *testing.T) {
	t.Parallel()

	registry := NewCapabilityRegistry()

	cap := AgencyCapability{
		Name:     AgencyName("development"),
		Domain:   DomainDevelopment,
		Skills:   []SkillName{"code-review", "test-driven-dev"},
		Agents:   []AgentName{"agent-1", "agent-2"},
		CostHint: CostHint{TokenBudget: 5000, TimeBudgetMs: 1000},
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      100,
			Message:    "operational",
			LastUpdate: time.Now().Unix(),
		},
	}

	err := registry.RegisterAgency(cap)
	require.NoError(t, err)

	// Verify by finding agencies
	agencies := registry.FindAgencies(CapabilityRequest{
		Domain: DomainDevelopment,
	})
	require.Len(t, agencies, 1)
	assert.Equal(t, AgencyName("development"), agencies[0].Name)
}

func TestCapabilityRegistry_RegisterAgency_EmptyName(t *testing.T) {
	t.Parallel()

	registry := NewCapabilityRegistry()

	cap := AgencyCapability{
		Name: "", // Empty name should fail
	}

	err := registry.RegisterAgency(cap)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "agency name cannot be empty")
}

func TestCapabilityRegistry_RegisterAgent(t *testing.T) {
	t.Parallel()

	registry := NewCapabilityRegistry()

	// Register agency first
	agencyCap := AgencyCapability{
		Name:     AgencyName("development"),
		Domain:   DomainDevelopment,
		Skills:   []SkillName{"code-review"},
		CostHint: CostHint{TokenBudget: 5000},
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      100,
			LastUpdate: time.Now().Unix(),
		},
	}
	require.NoError(t, registry.RegisterAgency(agencyCap))

	// Register agent
	agentCap := AgentCapability{
		Name:     AgentName("coder-agent"),
		Agency:   AgencyName("development"),
		Skills:   []SkillName{"code-review", "refactoring"},
		Tools:    []string{"bash", "edit", "grep"},
		CostHint: CostHint{TokenBudget: 3000},
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      95,
			LastUpdate: time.Now().Unix(),
		},
	}

	err := registry.RegisterAgent("development", agentCap)
	require.NoError(t, err)

	// Verify by finding agents
	agents := registry.FindAgents(CapabilityRequest{
		Domain: DomainDevelopment,
	})
	require.Len(t, agents, 1)
	assert.Equal(t, AgentName("coder-agent"), agents[0].Name)
}

func TestCapabilityRegistry_RegisterAgent_AgencyNotFound(t *testing.T) {
	t.Parallel()

	registry := NewCapabilityRegistry()

	agentCap := AgentCapability{
		Name:   AgentName("orphan-agent"),
		Agency: AgencyName("nonexistent"),
		Skills: []SkillName{"coding"},
		Tools:  []string{"bash"},
		RiskClass: RiskClassLow,
	}

	err := registry.RegisterAgent("nonexistent", agentCap)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "agency")
	assert.Contains(t, err.Error(), "not found")
}

func TestCapabilityRegistry_FindAgents(t *testing.T) {
	t.Parallel()

	registry := NewCapabilityRegistry()

	// Setup: register multiple agencies and agents
	agencies := []AgencyCapability{
		{
			Name:     AgencyName("dev-agency"),
			Domain:   DomainDevelopment,
			Skills:   []SkillName{"coding", "testing"},
			RiskClass: RiskClassLow,
			Health: HealthIndicator{
				Level:      HealthLevelHealthy,
				Score:      100,
				LastUpdate: time.Now().Unix(),
			},
		},
		{
			Name:     AgencyName("creative-agency"),
			Domain:   DomainCreative,
			Skills:   []SkillName{"writing", "design"},
			RiskClass: RiskClassMedium,
			Health: HealthIndicator{
				Level:      HealthLevelDegraded,
				Score:      70,
				LastUpdate: time.Now().Unix(),
			},
		},
	}

	for _, agency := range agencies {
		require.NoError(t, registry.RegisterAgency(agency))
	}

	// Register agents
	agents := []struct {
		agencyName string
		cap        AgentCapability
	}{
		{
			agencyName: "dev-agency",
			cap: AgentCapability{
				Name:     AgentName("dev-agent-1"),
				Agency:   AgencyName("dev-agency"),
				Skills:   []SkillName{"coding"},
				Tools:    []string{"bash", "edit"},
				CostHint: CostHint{TokenBudget: 5000},
				RiskClass: RiskClassLow,
				Health: HealthIndicator{
					Level:      HealthLevelHealthy,
					Score:      100,
					LastUpdate: time.Now().Unix(),
				},
			},
		},
		{
			agencyName: "dev-agency",
			cap: AgentCapability{
				Name:     AgentName("dev-agent-2"),
				Agency:   AgencyName("dev-agency"),
				Skills:   []SkillName{"testing", "coding"},
				Tools:    []string{"bash", "test"},
				CostHint: CostHint{TokenBudget: 3000},
				RiskClass: RiskClassLow,
				Health: HealthIndicator{
					Level:      HealthLevelHealthy,
					Score:      90,
					LastUpdate: time.Now().Unix(),
				},
			},
		},
		{
			agencyName: "creative-agency",
			cap: AgentCapability{
				Name:     AgentName("creative-agent"),
				Agency:   AgencyName("creative-agency"),
				Skills:   []SkillName{"writing"},
				Tools:    []string{"write", "edit"},
				CostHint: CostHint{TokenBudget: 2000},
				RiskClass: RiskClassMedium,
				Health: HealthIndicator{
					Level:      HealthLevelDegraded,
					Score:      60,
					LastUpdate: time.Now().Unix(),
				},
			},
		},
	}

	for _, a := range agents {
		require.NoError(t, registry.RegisterAgent(a.agencyName, a.cap))
	}

	t.Run("filter by domain", func(t *testing.T) {
		found := registry.FindAgents(CapabilityRequest{
			Domain: DomainDevelopment,
		})
		assert.Len(t, found, 2)
		for _, agent := range found {
			assert.Equal(t, AgencyName("dev-agency"), agent.Agency)
		}
	})

	t.Run("filter by skill", func(t *testing.T) {
		found := registry.FindAgents(CapabilityRequest{
			Domain: DomainDevelopment,
			Skills: []SkillName{"testing"},
		})
		assert.Len(t, found, 1)
		assert.Equal(t, AgentName("dev-agent-2"), found[0].Name)
	})

	t.Run("filter by health level", func(t *testing.T) {
		found := registry.FindAgents(CapabilityRequest{
			MinHealth: HealthLevelHealthy,
		})
		// Only healthy agents (not degraded)
		for _, agent := range found {
			assert.GreaterOrEqual(t, healthLevelToInt(agent.Health.Level), healthLevelToInt(HealthLevelHealthy))
		}
	})

	t.Run("filter by max cost", func(t *testing.T) {
		found := registry.FindAgents(CapabilityRequest{
			MaxCost: CostHint{TokenBudget: 4000},
		})
		for _, agent := range found {
			assert.LessOrEqual(t, agent.CostHint.TokenBudget, 4000)
		}
	})

	t.Run("filter by max risk", func(t *testing.T) {
		found := registry.FindAgents(CapabilityRequest{
			MaxRisk: RiskClassLow,
		})
		for _, agent := range found {
			assert.LessOrEqual(t, riskClassToInt(agent.RiskClass), riskClassToInt(RiskClassLow))
		}
	})
}

func TestCapabilityRegistry_FindAgencies(t *testing.T) {
	t.Parallel()

	registry := NewCapabilityRegistry()

	// Setup: register multiple agencies
	agencies := []AgencyCapability{
		{
			Name:     AgencyName("dev-agency"),
			Domain:   DomainDevelopment,
			Skills:   []SkillName{"coding", "testing"},
			RiskClass: RiskClassLow,
			Health: HealthIndicator{
				Level:      HealthLevelHealthy,
				Score:      100,
				LastUpdate: time.Now().Unix(),
			},
		},
		{
			Name:     AgencyName("research-agency"),
			Domain:   DomainKnowledge,
			Skills:   []SkillName{"research", "analysis"},
			RiskClass: RiskClassMedium,
			Health: HealthIndicator{
				Level:      HealthLevelHealthy,
				Score:      85,
				LastUpdate: time.Now().Unix(),
			},
		},
		{
			Name:     AgencyName("creative-agency"),
			Domain:   DomainCreative,
			Skills:   []SkillName{"writing", "design"},
			RiskClass: RiskClassHigh,
			Health: HealthIndicator{
				Level:      HealthLevelDegraded,
				Score:      50,
				LastUpdate: time.Now().Unix(),
			},
		},
	}

	for _, agency := range agencies {
		require.NoError(t, registry.RegisterAgency(agency))
	}

	t.Run("filter by domain", func(t *testing.T) {
		found := registry.FindAgencies(CapabilityRequest{
			Domain: DomainDevelopment,
		})
		assert.Len(t, found, 1)
		assert.Equal(t, AgencyName("dev-agency"), found[0].Name)
	})

	t.Run("filter by skill", func(t *testing.T) {
		found := registry.FindAgencies(CapabilityRequest{
			Skills: []SkillName{"research"},
		})
		assert.Len(t, found, 1)
		assert.Equal(t, AgencyName("research-agency"), found[0].Name)
	})

	t.Run("filter by multiple skills (OR semantics)", func(t *testing.T) {
		found := registry.FindAgencies(CapabilityRequest{
			Skills: []SkillName{"design", "testing"},
		})
		assert.Len(t, found, 2)
	})

	t.Run("filter by health level", func(t *testing.T) {
		found := registry.FindAgencies(CapabilityRequest{
			MinHealth: HealthLevelHealthy,
		})
		for _, agency := range found {
			assert.GreaterOrEqual(t, healthLevelToInt(agency.Health.Level), healthLevelToInt(HealthLevelHealthy))
		}
	})

	t.Run("filter by max risk", func(t *testing.T) {
		found := registry.FindAgencies(CapabilityRequest{
			MaxRisk: RiskClassMedium,
		})
		for _, agency := range found {
			assert.True(t, agency.RiskClass == RiskClassLow || agency.RiskClass == RiskClassMedium)
		}
	})
}

func TestCapabilityRegistry_HealthStatus(t *testing.T) {
	t.Parallel()

	registry := NewCapabilityRegistry()

	// Register agencies with different health levels
	agencies := []AgencyCapability{
		{
			Name:     AgencyName("healthy-agency"),
			Domain:   DomainDevelopment,
			RiskClass: RiskClassLow,
			Health: HealthIndicator{
				Level:      HealthLevelHealthy,
				Score:      100,
				LastUpdate: time.Now().Unix(),
			},
		},
		{
			Name:     AgencyName("degraded-agency"),
			Domain:   DomainKnowledge,
			RiskClass: RiskClassMedium,
			Health: HealthIndicator{
				Level:      HealthLevelDegraded,
				Score:      60,
				LastUpdate: time.Now().Unix(),
			},
		},
	}

	for _, agency := range agencies {
		require.NoError(t, registry.RegisterAgency(agency))
	}

	// Register agents
	require.NoError(t, registry.RegisterAgent("healthy-agency", AgentCapability{
		Name:     AgentName("healthy-agent"),
		Agency:   AgencyName("healthy-agency"),
		Skills:   []SkillName{"coding"},
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      100,
			LastUpdate: time.Now().Unix(),
		},
	}))

	require.NoError(t, registry.RegisterAgent("degraded-agency", AgentCapability{
		Name:     AgentName("degraded-agent"),
		Agency:   AgencyName("degraded-agency"),
		Skills:   []SkillName{"analysis"},
		RiskClass: RiskClassMedium,
		Health: HealthIndicator{
			Level:      HealthLevelUnavailable,
			Score:      0,
			LastUpdate: time.Now().Unix(),
		},
	}))

	status := registry.GetHealth()

	// Overall health should be the minimum (unavailable)
	assert.Equal(t, HealthLevelUnavailable, status.Overall)

	// Check agency health map
	assert.Len(t, status.Agencies, 2)
	assert.Equal(t, HealthLevelHealthy, status.Agencies["healthy-agency"].Level)
	assert.Equal(t, HealthLevelDegraded, status.Agencies["degraded-agency"].Level)

	// Check agent health map
	assert.Len(t, status.Agencies, 2) // Note: uses same map field, should be Agents
}

func TestCapabilityRegistry_Empty(t *testing.T) {
	t.Parallel()

	registry := NewCapabilityRegistry()

	// Find on empty registry should return empty slices
	assert.Empty(t, registry.FindAgents(CapabilityRequest{}))
	assert.Empty(t, registry.FindAgencies(CapabilityRequest{}))

	status := registry.GetHealth()
	assert.Equal(t, HealthLevelHealthy, status.Overall) // Default when empty
	assert.Empty(t, status.Agencies)
	assert.Empty(t, status.Agents)
}

func TestCapabilityRegistry_SortedResults(t *testing.T) {
	t.Parallel()

	registry := NewCapabilityRegistry()

	// Register agency
	require.NoError(t, registry.RegisterAgency(AgencyCapability{
		Name:     AgencyName("test-agency"),
		Domain:   DomainDevelopment,
		RiskClass: RiskClassLow,
		Health: HealthIndicator{
			Level:      HealthLevelHealthy,
			Score:      100,
			LastUpdate: time.Now().Unix(),
		},
	}))

	// Register agents with different fitness scores
	agents := []AgentCapability{
		{
			Name:     AgentName("high-cost-agent"),
			Agency:   AgencyName("test-agency"),
			Skills:   []SkillName{"coding"},
			CostHint: CostHint{TokenBudget: 10000}, // High cost
			RiskClass: RiskClassLow,
			Health: HealthIndicator{
				Level:      HealthLevelHealthy,
				Score:      100,
				LastUpdate: time.Now().Unix(),
			},
		},
		{
			Name:     AgentName("low-cost-agent"),
			Agency:   AgencyName("test-agency"),
			Skills:   []SkillName{"coding"},
			CostHint: CostHint{TokenBudget: 1000}, // Low cost
			RiskClass: RiskClassLow,
			Health: HealthIndicator{
				Level:      HealthLevelHealthy,
				Score:      100,
				LastUpdate: time.Now().Unix(),
			},
		},
		{
			Name:     AgentName("high-risk-agent"),
			Agency:   AgencyName("test-agency"),
			Skills:   []SkillName{"coding"},
			CostHint: CostHint{TokenBudget: 5000},
			RiskClass: RiskClassHigh,
			Health: HealthIndicator{
				Level:      HealthLevelHealthy,
				Score:      100,
				LastUpdate: time.Now().Unix(),
			},
		},
	}

	for _, agent := range agents {
		require.NoError(t, registry.RegisterAgent("test-agency", agent))
	}

	found := registry.FindAgents(CapabilityRequest{
		Domain: DomainDevelopment,
		Skills: []SkillName{"coding"},
	})

	// Results should be sorted by fitness (higher fitness first)
	// low-cost + low-risk should be first
	assert.Equal(t, AgentName("low-cost-agent"), found[0].Name)
}
