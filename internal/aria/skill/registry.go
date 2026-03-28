package skill

import (
	"fmt"
	"sync"
)

// DefaultSkillRegistry is the default implementation of SkillRegistry.
type DefaultSkillRegistry struct {
	mu     sync.RWMutex
	skills map[SkillName]Skill
}

// NewDefaultSkillRegistry creates a new default skill registry.
func NewDefaultSkillRegistry() *DefaultSkillRegistry {
	return &DefaultSkillRegistry{
		skills: make(map[SkillName]Skill),
	}
}

// Get returns a skill by name.
func (r *DefaultSkillRegistry) Get(name SkillName) (Skill, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	skill, ok := r.skills[name]
	if !ok {
		return nil, fmt.Errorf("skill not found: %s", name)
	}
	return skill, nil
}

// List returns all registered skills.
func (r *DefaultSkillRegistry) List() []Skill {
	r.mu.RLock()
	defer r.mu.RUnlock()
	skills := make([]Skill, 0, len(r.skills))
	for _, skill := range r.skills {
		skills = append(skills, skill)
	}
	return skills
}

// Register adds a skill to the registry.
func (r *DefaultSkillRegistry) Register(s Skill) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.skills[s.Name()] = s
	return nil
}

// Unregister removes a skill from the registry.
func (r *DefaultSkillRegistry) Unregister(name SkillName) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.skills, name)
	return nil
}

// FindByTool returns skills that require a specific tool.
func (r *DefaultSkillRegistry) FindByTool(tool ToolName) []Skill {
	r.mu.RLock()
	defer r.mu.RUnlock()
	var result []Skill
	for _, skill := range r.skills {
		for _, t := range skill.RequiredTools() {
			if t == tool {
				result = append(result, skill)
				break
			}
		}
	}
	return result
}

// FindByMCP returns skills that require a specific MCP.
func (r *DefaultSkillRegistry) FindByMCP(mcp MCPName) []Skill {
	r.mu.RLock()
	defer r.mu.RUnlock()
	var result []Skill
	for _, skill := range r.skills {
		for _, m := range skill.RequiredMCPs() {
			if m == mcp {
				result = append(result, skill)
				break
			}
		}
	}
	return result
}

// SetupDefaultSkills registers the default development skills.
func SetupDefaultSkills(r *DefaultSkillRegistry) error {
	skills := []Skill{
		NewCodeReviewSkill(),
		NewTDDSkill(),
		NewDebuggingSkill(),
	}

	for _, s := range skills {
		if err := r.Register(s); err != nil {
			return err
		}
	}

	return nil
}
