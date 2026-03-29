// Package permission provides the extended permission system for ARIA.
package permission

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewService(t *testing.T) {
	s := NewService()
	assert.NotNil(t, s)
}

func TestPermissionService_Request(t *testing.T) {
	ctx := context.Background()

	t.Run("valid request", func(t *testing.T) {
		s := NewService()
		req := Request{
			AgencyID: "agency-1",
			AgentID:  "agent-1",
			Action:   ActionRead,
			Resource: "/files/test.txt",
			Reason:   "testing",
		}

		resp, err := s.Request(ctx, req)
		require.NoError(t, err)
		assert.NotEmpty(t, resp.RequestID)
		assert.False(t, resp.Granted)
		assert.Equal(t, PermissionNone, resp.Level)
	})

	t.Run("missing agencyID", func(t *testing.T) {
		s := NewService()
		req := Request{
			AgentID:  "agent-1",
			Action:   ActionRead,
			Resource: "/files/test.txt",
		}

		_, err := s.Request(ctx, req)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "agencyID")
	})

	t.Run("missing agentID", func(t *testing.T) {
		s := NewService()
		req := Request{
			AgencyID: "agency-1",
			Action:   ActionRead,
			Resource: "/files/test.txt",
		}

		_, err := s.Request(ctx, req)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "agentID")
	})

	t.Run("missing action", func(t *testing.T) {
		s := NewService()
		req := Request{
			AgencyID: "agency-1",
			AgentID:  "agent-1",
			Resource: "/files/test.txt",
		}

		_, err := s.Request(ctx, req)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "action")
	})

	t.Run("missing resource", func(t *testing.T) {
		s := NewService()
		req := Request{
			AgencyID: "agency-1",
			AgentID:  "agent-1",
			Action:   ActionRead,
		}

		_, err := s.Request(ctx, req)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "resource")
	})
}

func TestPermissionService_Grant(t *testing.T) {
	ctx := context.Background()

	t.Run("grant request", func(t *testing.T) {
		s := NewService()
		req := Request{
			AgencyID: "agency-1",
			AgentID:  "agent-1",
			Action:   ActionWrite,
			Resource: "/files/test.txt",
			Reason:   "testing",
		}

		resp, err := s.Request(ctx, req)
		require.NoError(t, err)

		err = s.Grant(ctx, resp.RequestID, PermissionAuto, ScopePermanent)
		require.NoError(t, err)

		rules, err := s.GetRules(ctx, "agency-1")
		require.NoError(t, err)
		assert.Len(t, rules, 1)
		assert.Equal(t, ActionWrite, rules[0].Action)
		assert.Equal(t, PermissionAuto, rules[0].Level)
	})

	t.Run("grant non-existent request", func(t *testing.T) {
		s := NewService()
		err := s.Grant(ctx, "non-existent-id", PermissionAuto, ScopeSession)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "request not found")
	})
}

func TestPermissionService_Deny(t *testing.T) {
	ctx := context.Background()

	t.Run("deny request", func(t *testing.T) {
		s := NewService()
		req := Request{
			AgencyID: "agency-1",
			AgentID:  "agent-1",
			Action:   ActionDelete,
			Resource: "/files/test.txt",
			Reason:   "testing",
		}

		resp, err := s.Request(ctx, req)
		require.NoError(t, err)

		err = s.Deny(ctx, resp.RequestID, "not allowed")
		require.NoError(t, err)
	})

	t.Run("deny non-existent request", func(t *testing.T) {
		s := NewService()
		err := s.Deny(ctx, "non-existent-id", "not allowed")
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "request not found")
	})
}

func TestPermissionService_Check(t *testing.T) {
	ctx := context.Background()

	t.Run("check with no rules", func(t *testing.T) {
		s := NewService()
		allowed, err := s.Check(ctx, "agency-1", "agent-1", ActionRead, "/files/test.txt")
		require.NoError(t, err)
		assert.False(t, allowed)
	})

	t.Run("check with rule", func(t *testing.T) {
		s := NewService()
		rule := PermissionRule{
			Action: ActionRead,
			Level:  PermissionAsk,
			Scope:  ScopePermanent,
		}
		err := s.AddRule(ctx, rule)
		require.NoError(t, err)

		allowed, err := s.Check(ctx, "global", "agent-1", ActionRead, "/files/test.txt")
		require.NoError(t, err)
		assert.True(t, allowed)
	})
}

func TestPermissionService_GetRules(t *testing.T) {
	ctx := context.Background()

	t.Run("get rules for agency with no rules", func(t *testing.T) {
		s := NewService()
		rules, err := s.GetRules(ctx, "agency-1")
		require.NoError(t, err)
		assert.Empty(t, rules)
	})

	t.Run("get rules for agency with rules", func(t *testing.T) {
		s := NewService()
		rule := PermissionRule{
			Action: ActionExecute,
			Level:  PermissionAuto,
			Scope:  ScopePermanent,
		}
		err := s.AddRule(ctx, rule)
		require.NoError(t, err)

		rules, err := s.GetRules(ctx, "global")
		require.NoError(t, err)
		assert.Len(t, rules, 1)
		assert.Equal(t, ActionExecute, rules[0].Action)
	})

	t.Run("expired rules are filtered", func(t *testing.T) {
		s := NewService()
		past := time.Now().Add(-1 * time.Hour)
		rule := PermissionRule{
			Action:    ActionWrite,
			Level:     PermissionAuto,
			Scope:     ScopeTemporary,
			ExpiresAt: &past,
		}
		err := s.AddRule(ctx, rule)
		require.NoError(t, err)

		rules, err := s.GetRules(ctx, "global")
		require.NoError(t, err)
		found := false
		for _, r := range rules {
			if r.Action == ActionWrite {
				found = true
				break
			}
		}
		assert.False(t, found, "expired rule should be filtered")
	})
}

func TestPermissionService_AddRule(t *testing.T) {
	ctx := context.Background()

	t.Run("add valid rule", func(t *testing.T) {
		s := NewService()
		rule := PermissionRule{
			Action: ActionNetwork,
			Level:  PermissionNotify,
			Scope:  ScopeSession,
		}

		err := s.AddRule(ctx, rule)
		require.NoError(t, err)

		rules, err := s.GetRules(ctx, "global")
		require.NoError(t, err)
		assert.Len(t, rules, 1)
		assert.NotEmpty(t, rules[0].ID)
	})

	t.Run("add rule with generated ID", func(t *testing.T) {
		s := NewService()
		rule := PermissionRule{
			Action: ActionSchedule,
			Level:  PermissionAuto,
			Scope:  ScopePermanent,
		}

		err := s.AddRule(ctx, rule)
		require.NoError(t, err)

		rules, err := s.GetRules(ctx, "global")
		require.NoError(t, err)
		require.Len(t, rules, 1)
		assert.NotEmpty(t, rules[0].ID)
	})

	t.Run("add rule without action fails", func(t *testing.T) {
		s := NewService()
		rule := PermissionRule{
			Level: PermissionAuto,
		}

		err := s.AddRule(ctx, rule)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "action")
	})

	t.Run("add rule with PermissionNone fails", func(t *testing.T) {
		s := NewService()
		rule := PermissionRule{
			Action: ActionRead,
			Level:  PermissionNone,
		}

		err := s.AddRule(ctx, rule)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "permission level")
	})
}

func TestPermissionService_RemoveRule(t *testing.T) {
	ctx := context.Background()

	t.Run("remove existing rule", func(t *testing.T) {
		s := NewService()
		rule := PermissionRule{
			Action: ActionDelete,
			Level:  PermissionAuto,
			Scope:  ScopePermanent,
		}
		err := s.AddRule(ctx, rule)
		require.NoError(t, err)

		rules, err := s.GetRules(ctx, "global")
		require.NoError(t, err)
		require.Len(t, rules, 1)
		ruleID := rules[0].ID

		err = s.RemoveRule(ctx, ruleID)
		require.NoError(t, err)

		rules, err = s.GetRules(ctx, "global")
		require.NoError(t, err)
		assert.Empty(t, rules)
	})

	t.Run("remove non-existent rule", func(t *testing.T) {
		s := NewService()
		err := s.RemoveRule(ctx, "non-existent-id")
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "rule not found")
	})
}

func TestPermissionService_GetEffectiveLevel(t *testing.T) {
	ctx := context.Background()

	t.Run("no rules returns None", func(t *testing.T) {
		s := NewService()
		level, err := s.GetEffectiveLevel(ctx, "agency-1", "agent-1", ActionRead)
		require.NoError(t, err)
		assert.Equal(t, PermissionNone, level)
	})

	t.Run("returns highest matching level", func(t *testing.T) {
		s := NewService()
		rules := []PermissionRule{
			{Action: ActionRead, Level: PermissionAsk},
			{Action: ActionRead, Level: PermissionNotify},
			{Action: ActionWrite, Level: PermissionAuto},
		}
		for _, r := range rules {
			err := s.AddRule(ctx, r)
			require.NoError(t, err)
		}

		level, err := s.GetEffectiveLevel(ctx, "global", "agent-1", ActionRead)
		require.NoError(t, err)
		assert.Equal(t, PermissionNotify, level)
	})

	t.Run("expired rules not considered", func(t *testing.T) {
		s := NewService()
		past := time.Now().Add(-1 * time.Hour)
		rule := PermissionRule{
			Action:    ActionExecute,
			Level:     PermissionAuto,
			Scope:     ScopeTemporary,
			ExpiresAt: &past,
		}
		err := s.AddRule(ctx, rule)
		require.NoError(t, err)

		level, err := s.GetEffectiveLevel(ctx, "global", "agent-1", ActionExecute)
		require.NoError(t, err)
		assert.Equal(t, PermissionNone, level)
	})
}
