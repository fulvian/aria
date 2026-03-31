package toolgovernance

import (
	"testing"
)

// TestDecisionConstants verifies decision constants are defined correctly
func TestDecisionConstants(t *testing.T) {
	t.Parallel()

	tests := []struct {
		decision Decision
		want     string
	}{
		{DecisionAllow, "allow"},
		{DecisionAsk, "ask"},
		{DecisionDeny, "deny"},
	}

	for _, tt := range tests {
		t.Run(tt.want, func(t *testing.T) {
			if string(tt.decision) != tt.want {
				t.Errorf("Decision %v = %q, want %q", tt.decision, string(tt.decision), tt.want)
			}
		})
	}
}

// TestPolicyRiskLevelConstants verifies risk level constants are defined correctly
func TestPolicyRiskLevelConstants(t *testing.T) {
	t.Parallel()

	tests := []struct {
		level PolicyRiskLevel
		want  int
	}{
		{PolicyRiskLow, 0},
		{PolicyRiskMedium, 1},
		{PolicyRiskHigh, 2},
		{PolicyRiskCritical, 3},
	}

	for _, tt := range tests {
		t.Run(tt.level.String(), func(t *testing.T) {
			if int(tt.level) != tt.want {
				t.Errorf("PolicyRiskLevel %v = %d, want %d", tt.level, int(tt.level), tt.want)
			}
		})
	}
}

// TestPolicyRiskLevelString verifies String() method for PolicyRiskLevel
func TestPolicyRiskLevelString(t *testing.T) {
	t.Parallel()

	tests := []struct {
		level PolicyRiskLevel
		want  string
	}{
		{PolicyRiskLow, "low"},
		{PolicyRiskMedium, "medium"},
		{PolicyRiskHigh, "high"},
		{PolicyRiskCritical, "critical"},
		{PolicyRiskLevel(99), "unknown"},
	}

	for _, tt := range tests {
		t.Run(tt.want, func(t *testing.T) {
			if got := tt.level.String(); got != tt.want {
				t.Errorf("PolicyRiskLevel(%d).String() = %q, want %q", int(tt.level), got, tt.want)
			}
		})
	}
}

// TestRiskClassifier_Classify tests the risk classifier
func TestRiskClassifier_Classify(t *testing.T) {
	t.Parallel()

	classifier := NewRiskClassifier()

	tests := []struct {
		name string
		tool string
		want PolicyRiskLevel
	}{
		// Critical risk
		{"rm command", "rm", PolicyRiskCritical},
		{"drop command", "drop", PolicyRiskCritical},
		{"truncate command", "truncate", PolicyRiskCritical},
		{"delete command", "delete", PolicyRiskCritical},
		{"shutdown command", "shutdown", PolicyRiskCritical},
		{"reboot command", "reboot", PolicyRiskCritical},
		{"sudo command", "sudo", PolicyRiskCritical},
		{"chmod command", "chmod", PolicyRiskCritical},
		{"chown command", "chown", PolicyRiskCritical},

		// High risk
		{"bash command", "bash", PolicyRiskHigh},
		{"exec command", "exec", PolicyRiskHigh},
		{"write command", "write", PolicyRiskHigh},
		{"edit command", "edit", PolicyRiskHigh},
		{"patch command", "patch", PolicyRiskHigh},
		{"run command", "run", PolicyRiskHigh},
		{"spawn command", "spawn", PolicyRiskHigh},
		{"kill command", "kill", PolicyRiskHigh},

		// Medium risk
		{"fetch command", "fetch", PolicyRiskMedium},
		{"download command", "download", PolicyRiskMedium},
		{"upload command", "upload", PolicyRiskMedium},
		{"copy command", "copy", PolicyRiskMedium},
		{"move command", "move", PolicyRiskMedium},
		{"rename command", "rename", PolicyRiskMedium},

		// Low risk (default)
		{"read command", "read", PolicyRiskLow},
		{"view command", "view", PolicyRiskLow},
		{"list command", "list", PolicyRiskLow},
		{"search command", "search", PolicyRiskLow},
		{"grep command", "grep", PolicyRiskLow},
		{"glob command", "glob", PolicyRiskLow},
		{"unknown tool", "foobar", PolicyRiskLow},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := classifier.Classify(tt.tool); got != tt.want {
				t.Errorf("RiskClassifier.Classify(%q) = %v, want %v", tt.tool, got, tt.want)
			}
		})
	}
}

// TestRiskClassifier_Classify_CaseInsensitive tests case insensitivity
func TestRiskClassifier_Classify_CaseInsensitive(t *testing.T) {
	t.Parallel()

	classifier := NewRiskClassifier()

	tests := []struct {
		tool string
		want PolicyRiskLevel
	}{
		{"BASH", PolicyRiskHigh},
		{"Bash", PolicyRiskHigh},
		{"EXEC", PolicyRiskHigh},
		{"Write", PolicyRiskHigh},
		{"FETCH", PolicyRiskMedium},
		{"Read", PolicyRiskLow},
	}

	for _, tt := range tests {
		t.Run(tt.tool, func(t *testing.T) {
			if got := classifier.Classify(tt.tool); got != tt.want {
				t.Errorf("RiskClassifier.Classify(%q) = %v, want %v", tt.tool, got, tt.want)
			}
		})
	}
}

// TestDefaultPolicies verifies default policies are correctly defined
func TestDefaultPolicies(t *testing.T) {
	t.Parallel()

	policy := DefaultPolicies()

	// Check allow list
	wantAllow := []string{"read", "view", "get", "list", "search", "fetch", "grep", "glob"}
	if len(policy.AllowList) != len(wantAllow) {
		t.Errorf("DefaultPolicies AllowList len = %d, want %d", len(policy.AllowList), len(wantAllow))
	}
	for i, w := range wantAllow {
		if policy.AllowList[i] != w {
			t.Errorf("DefaultPolicies AllowList[%d] = %q, want %q", i, policy.AllowList[i], w)
		}
	}

	// Check ask list
	wantAsk := []string{"bash", "exec", "write", "edit", "patch", "delete", "sudo"}
	if len(policy.AskList) != len(wantAsk) {
		t.Errorf("DefaultPolicies AskList len = %d, want %d", len(policy.AskList), len(wantAsk))
	}
	for i, w := range wantAsk {
		if policy.AskList[i] != w {
			t.Errorf("DefaultPolicies AskList[%d] = %q, want %q", i, policy.AskList[i], w)
		}
	}

	// Check deny list
	wantDeny := []string{"rm", "drop", "truncate", "shutdown", "reboot"}
	if len(policy.DenyList) != len(wantDeny) {
		t.Errorf("DefaultPolicies DenyList len = %d, want %d", len(policy.DenyList), len(wantDeny))
	}
	for i, w := range wantDeny {
		if policy.DenyList[i] != w {
			t.Errorf("DefaultPolicies DenyList[%d] = %q, want %q", i, policy.DenyList[i], w)
		}
	}
}

// TestAgentAccessPolicies verifies agent-specific policies
func TestAgentAccessPolicies(t *testing.T) {
	t.Parallel()

	policies := AgentAccessPolicies()

	// Test researcher policy
	researcher, ok := policies["researcher"]
	if !ok {
		t.Fatal("AgentAccessPolicies() missing 'researcher' key")
	}
	if len(researcher.AllowList) == 0 {
		t.Error("researcher AllowList is empty")
	}
	if len(researcher.DenyList) == 0 {
		t.Error("researcher DenyList is empty")
	}

	// Test coder policy
	coder, ok := policies["coder"]
	if !ok {
		t.Fatal("AgentAccessPolicies() missing 'coder' key")
	}
	if len(coder.AllowList) == 0 {
		t.Error("coder AllowList is empty")
	}

	// Test critic policy - should deny bash
	critic, ok := policies["critic"]
	if !ok {
		t.Fatal("AgentAccessPolicies() missing 'critic' key")
	}
	// Critic should have deny for bash
	foundBashDeny := false
	for _, tool := range critic.DenyList {
		if tool == "bash" || tool == "exec" {
			foundBashDeny = true
			break
		}
	}
	if !foundBashDeny {
		t.Error("critic policy should deny bash/exec")
	}

	// Test planner policy
	planner, ok := policies["planner"]
	if !ok {
		t.Fatal("AgentAccessPolicies() missing 'planner' key")
	}
	if len(planner.AllowList) == 0 {
		t.Error("planner AllowList is empty")
	}
}

// TestNewPolicyEngine creates a policy engine and verifies initial state
func TestNewPolicyEngine(t *testing.T) {
	t.Parallel()

	engine := NewPolicyEngine()
	if engine == nil {
		t.Fatal("NewPolicyEngine() returned nil")
	}
	if engine.agentPolicies == nil {
		t.Error("NewPolicyEngine() agentPolicies is nil")
	}
	if engine.defaultPolicy == nil {
		t.Error("NewPolicyEngine() defaultPolicy is nil")
	}
	if engine.riskClassifier == nil {
		t.Error("NewPolicyEngine() riskClassifier is nil")
	}
}

// TestPolicyEngine_CheckTool_Researcher tests CheckTool for researcher agent
func TestPolicyEngine_CheckTool_Researcher(t *testing.T) {
	t.Parallel()

	engine := NewPolicyEngine()

	tests := []struct {
		tool string
		want Decision
	}{
		// Allowed tools for researcher
		{"fetch", DecisionAllow},
		{"search", DecisionAllow},
		{"read", DecisionAllow},
		{"view", DecisionAllow},
		{"grep", DecisionAllow},
		{"glob", DecisionAllow},
		{"list", DecisionAllow},
		// Ask tools for researcher
		{"bash", DecisionAsk},
		// Denied tools for researcher
		{"write", DecisionDeny},
		{"edit", DecisionDeny},
		{"delete", DecisionDeny},
	}

	for _, tt := range tests {
		t.Run("researcher/"+tt.tool, func(t *testing.T) {
			got, err := engine.CheckTool(tt.tool, "researcher")
			if err != nil {
				t.Errorf("CheckTool(%q, researcher) error = %v", tt.tool, err)
				return
			}
			if got != tt.want {
				t.Errorf("CheckTool(%q, researcher) = %v, want %v", tt.tool, got, tt.want)
			}
		})
	}
}

// TestPolicyEngine_CheckTool_Coder tests CheckTool for coder agent
func TestPolicyEngine_CheckTool_Coder(t *testing.T) {
	t.Parallel()

	engine := NewPolicyEngine()

	tests := []struct {
		tool string
		want Decision
	}{
		// Allowed tools for coder
		{"read", DecisionAllow},
		{"view", DecisionAllow},
		{"grep", DecisionAllow},
		{"glob", DecisionAllow},
		{"list", DecisionAllow},
		{"bash", DecisionAllow},
		{"write", DecisionAllow},
		{"edit", DecisionAllow},
		{"patch", DecisionAllow},
		// Ask tools for coder
		{"sudo", DecisionAsk},
		{"delete", DecisionAsk},
		// Denied tools for coder
		{"rm", DecisionDeny},
	}

	for _, tt := range tests {
		t.Run("coder/"+tt.tool, func(t *testing.T) {
			got, err := engine.CheckTool(tt.tool, "coder")
			if err != nil {
				t.Errorf("CheckTool(%q, coder) error = %v", tt.tool, err)
				return
			}
			if got != tt.want {
				t.Errorf("CheckTool(%q, coder) = %v, want %v", tt.tool, got, tt.want)
			}
		})
	}
}

// TestPolicyEngine_CheckTool_Critic tests CheckTool for critic agent
func TestPolicyEngine_CheckTool_Critic(t *testing.T) {
	t.Parallel()

	engine := NewPolicyEngine()

	tests := []struct {
		tool string
		want Decision
	}{
		// Allowed tools for critic
		{"read", DecisionAllow},
		{"view", DecisionAllow},
		{"grep", DecisionAllow},
		{"glob", DecisionAllow},
		{"list", DecisionAllow},
		{"fetch", DecisionAllow},
		// Denied tools for critic (no ask list per spec)
		{"bash", DecisionDeny},
		{"write", DecisionDeny},
		{"edit", DecisionDeny},
		{"delete", DecisionDeny},
		{"exec", DecisionDeny},
	}

	for _, tt := range tests {
		t.Run("critic/"+tt.tool, func(t *testing.T) {
			got, err := engine.CheckTool(tt.tool, "critic")
			if err != nil {
				t.Errorf("CheckTool(%q, critic) error = %v", tt.tool, err)
				return
			}
			if got != tt.want {
				t.Errorf("CheckTool(%q, critic) = %v, want %v", tt.tool, got, tt.want)
			}
		})
	}
}

// TestPolicyEngine_CheckTool_DefaultPolicy tests fallback to default policy
func TestPolicyEngine_CheckTool_DefaultPolicy(t *testing.T) {
	t.Parallel()

	engine := NewPolicyEngine()

	// Unknown agent should use default policy
	tests := []struct {
		tool string
		want Decision
	}{
		{"read", DecisionAllow},
		{"view", DecisionAllow},
		{"bash", DecisionAsk},
		{"rm", DecisionDeny},
	}

	for _, tt := range tests {
		t.Run("unknown/"+tt.tool, func(t *testing.T) {
			got, err := engine.CheckTool(tt.tool, "unknown_agent")
			if err != nil {
				t.Errorf("CheckTool(%q, unknown_agent) error = %v", tt.tool, err)
				return
			}
			if got != tt.want {
				t.Errorf("CheckTool(%q, unknown_agent) = %v, want %v", tt.tool, got, tt.want)
			}
		})
	}
}

// TestPolicyEngine_CheckTool_UnknownTool tests handling of unknown tools
func TestPolicyEngine_CheckTool_UnknownTool(t *testing.T) {
	t.Parallel()

	engine := NewPolicyEngine()

	tests := []struct {
		tool     string
		agent    string
		wantRisk PolicyRiskLevel
	}{
		// Unknown tools use risk classifier - tools with actual risk patterns
		{"foobar", "researcher", PolicyRiskLow},            // Truly unknown - low
		{"mybash_script", "researcher", PolicyRiskHigh},    // Contains "bash" - high
		{"myrm_command", "researcher", PolicyRiskCritical}, // Contains "rm" - critical
	}

	for _, tt := range tests {
		t.Run(tt.agent+"/"+tt.tool, func(t *testing.T) {
			risk := engine.riskClassifier.Classify(tt.tool)
			if risk != tt.wantRisk {
				t.Errorf("riskClassifier.Classify(%q) = %v, want %v", tt.tool, risk, tt.wantRisk)
			}
		})
	}
}

// TestPolicyEngine_SetPolicy tests setting custom policies
func TestPolicyEngine_SetPolicy(t *testing.T) {
	t.Parallel()

	engine := NewPolicyEngine()

	// Set custom policy for new agent
	customPolicy := &AccessPolicy{
		AllowList: []string{"custom_tool"},
		AskList:   []string{},
		DenyList:  []string{"restricted"},
	}
	engine.SetPolicy("custom_agent", customPolicy)

	// Verify custom policy is returned
	got := engine.GetPolicy("custom_agent")
	if got != customPolicy {
		t.Errorf("GetPolicy(custom_agent) = %v, want %v", got, customPolicy)
	}

	// Verify CheckTool respects custom policy
	decision, err := engine.CheckTool("custom_tool", "custom_agent")
	if err != nil {
		t.Errorf("CheckTool error: %v", err)
	}
	if decision != DecisionAllow {
		t.Errorf("CheckTool(custom_tool, custom_agent) = %v, want %v", decision, DecisionAllow)
	}

	decision, err = engine.CheckTool("restricted", "custom_agent")
	if err != nil {
		t.Errorf("CheckTool error: %v", err)
	}
	if decision != DecisionDeny {
		t.Errorf("CheckTool(restricted, custom_agent) = %v, want %v", decision, DecisionDeny)
	}
}

// TestPolicyEngine_GetPolicy tests GetPolicy method
func TestPolicyEngine_GetPolicy(t *testing.T) {
	t.Parallel()

	engine := NewPolicyEngine()

	// Get existing agent policy
	policy := engine.GetPolicy("researcher")
	if policy == nil {
		t.Error("GetPolicy(researcher) returned nil")
	}

	// Get unknown agent should return default policy
	defaultPolicy := engine.GetPolicy("nonexistent")
	if defaultPolicy == nil {
		t.Error("GetPolicy(nonexistent) returned nil")
	}
	if defaultPolicy != engine.defaultPolicy {
		t.Error("GetPolicy(nonexistent) should return defaultPolicy")
	}
}

// TestPolicyEngine_CheckTool_SubstringMatching tests substring matching
func TestPolicyEngine_CheckTool_SubstringMatching(t *testing.T) {
	t.Parallel()

	engine := NewPolicyEngine()

	// Tools should match on substrings
	decision, _ := engine.CheckTool("bash -c ls", "researcher")
	if decision != DecisionAsk {
		t.Errorf("CheckTool('bash -c ls', researcher) = %v, want %v", decision, DecisionAsk)
	}

	decision, _ = engine.CheckTool("my_exec_tool", "researcher")
	if decision != DecisionAsk {
		t.Errorf("CheckTool('my_exec_tool', researcher) = %v, want %v", decision, DecisionAsk)
	}

	// rmrf contains 'rm' which is a critical risk pattern, so it returns Ask
	decision, _ = engine.CheckTool("rmrf", "researcher")
	if decision != DecisionAsk {
		t.Errorf("CheckTool('rmrf', researcher) = %v, want %v", decision, DecisionAsk)
	}
}
