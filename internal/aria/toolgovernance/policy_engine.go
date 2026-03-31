package toolgovernance

import (
	"strings"
)

// Decision represents a tool policy decision
type Decision string

const (
	DecisionAllow Decision = "allow"
	DecisionAsk   Decision = "ask"
	DecisionDeny  Decision = "deny"
)

// PolicyRiskLevel represents tool risk classification for agent policies
type PolicyRiskLevel int

const (
	PolicyRiskLow      PolicyRiskLevel = 0
	PolicyRiskMedium   PolicyRiskLevel = 1
	PolicyRiskHigh     PolicyRiskLevel = 2
	PolicyRiskCritical PolicyRiskLevel = 3
)

// AccessPolicy defines access rules for tools
type AccessPolicy struct {
	AllowList []string // Tools always allowed
	AskList   []string // Tools requiring confirmation
	DenyList  []string // Tools always denied
}

// DefaultPolicies returns default policies for unknown agents
func DefaultPolicies() *AccessPolicy {
	return &AccessPolicy{
		AllowList: []string{"read", "view", "get", "list", "search", "fetch", "grep", "glob"},
		AskList:   []string{"bash", "exec", "write", "edit", "patch", "delete", "sudo"},
		DenyList:  []string{"rm", "drop", "truncate", "shutdown", "reboot"},
	}
}

// AgentAccessPolicies returns default policies per agent type
func AgentAccessPolicies() map[string]*AccessPolicy {
	return map[string]*AccessPolicy{
		"researcher": {
			AllowList: []string{"fetch", "search", "read", "view", "grep", "glob", "list"},
			AskList:   []string{"bash"},
			DenyList:  []string{"write", "edit", "delete"},
		},
		"coder": {
			AllowList: []string{"read", "view", "grep", "glob", "list", "bash", "write", "edit", "patch"},
			AskList:   []string{"sudo", "delete"},
			DenyList:  []string{"rm"},
		},
		"critic": {
			AllowList: []string{"read", "view", "grep", "glob", "list", "fetch"},
			AskList:   []string{},
			DenyList:  []string{"bash", "write", "edit", "delete", "exec"},
		},
		"planner": {
			AllowList: []string{"read", "view", "list", "search"},
			AskList:   []string{"fetch", "bash"},
			DenyList:  []string{"write", "edit", "delete", "exec"},
		},
	}
}

// PolicyEngine makes tool invocation decisions based on agent profiles
type PolicyEngine struct {
	agentPolicies  map[string]*AccessPolicy
	riskClassifier *RiskClassifier
	defaultPolicy  *AccessPolicy
}

// NewPolicyEngine creates a new policy engine
func NewPolicyEngine() *PolicyEngine {
	return &PolicyEngine{
		agentPolicies:  AgentAccessPolicies(),
		riskClassifier: NewRiskClassifier(),
		defaultPolicy:  DefaultPolicies(),
	}
}

// CheckTool returns the decision for a tool invocation
func (e *PolicyEngine) CheckTool(tool string, agent string) (Decision, error) {
	policy, ok := e.agentPolicies[agent]
	if !ok {
		policy = e.defaultPolicy
	}

	toolLower := strings.ToLower(tool)

	// Check deny list first
	for _, t := range policy.DenyList {
		if strings.Contains(toolLower, strings.ToLower(t)) {
			return DecisionDeny, nil
		}
	}

	// Check ask list
	for _, t := range policy.AskList {
		if strings.Contains(toolLower, strings.ToLower(t)) {
			return DecisionAsk, nil
		}
	}

	// Check allow list
	for _, t := range policy.AllowList {
		if strings.Contains(toolLower, strings.ToLower(t)) {
			return DecisionAllow, nil
		}
	}

	// Unknown tool - use risk classifier
	risk := e.riskClassifier.Classify(tool)
	if risk >= PolicyRiskHigh {
		return DecisionAsk, nil
	}

	return DecisionAllow, nil
}

// SetPolicy sets a custom policy for an agent
func (e *PolicyEngine) SetPolicy(agent string, policy *AccessPolicy) {
	e.agentPolicies[agent] = policy
}

// GetPolicy gets the policy for an agent
func (e *PolicyEngine) GetPolicy(agent string) *AccessPolicy {
	if policy, ok := e.agentPolicies[agent]; ok {
		return policy
	}
	return e.defaultPolicy
}

// RiskClassifier determines risk level for unknown tools using heuristics
type RiskClassifier struct{}

// NewRiskClassifier creates a new risk classifier
func NewRiskClassifier() *RiskClassifier {
	return &RiskClassifier{}
}

// Classify determines the risk level of a tool
func (c *RiskClassifier) Classify(tool string) PolicyRiskLevel {
	toolLower := strings.ToLower(tool)

	// Critical risk patterns
	critical := []string{"rm", "drop", "truncate", "delete", "shutdown", "reboot", "sudo", "chmod", "chown"}
	for _, t := range critical {
		if strings.Contains(toolLower, t) {
			return PolicyRiskCritical
		}
	}

	// High risk patterns
	high := []string{"bash", "exec", "write", "edit", "patch", "run", "spawn", "kill"}
	for _, t := range high {
		if strings.Contains(toolLower, t) {
			return PolicyRiskHigh
		}
	}

	// Medium risk patterns
	medium := []string{"fetch", "download", "upload", "copy", "move", "rename"}
	for _, t := range medium {
		if strings.Contains(toolLower, t) {
			return PolicyRiskMedium
		}
	}

	return PolicyRiskLow
}

// String returns string representation of PolicyRiskLevel
func (r PolicyRiskLevel) String() string {
	switch r {
	case PolicyRiskLow:
		return "low"
	case PolicyRiskMedium:
		return "medium"
	case PolicyRiskHigh:
		return "high"
	case PolicyRiskCritical:
		return "critical"
	default:
		return "unknown"
	}
}
