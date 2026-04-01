package startup

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"
)

// TUI colors matching ARIA's theme
var (
	healthyStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#50FA7B")).Bold(true)
	degradedStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#F1FA8C")).Bold(true)
	unhealthyStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#FF5555")).Bold(true)
	pendingStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#6272A4"))
	checkingStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#8BE9FD"))
	unknownStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#6272A4"))
)

// StartupStatusView renders the startup status as a string for TUI display.
type StartupStatusView struct {
	tracker *StatusTracker
}

// NewStartupStatusView creates a new StartupStatusView.
func NewStartupStatusView(tracker *StatusTracker) *StartupStatusView {
	return &StartupStatusView{
		tracker: tracker,
	}
}

// Render renders the current startup status as a formatted string.
func (v *StartupStatusView) Render() string {
	var lines []string

	lines = append(lines, "╔════════════════════════════════════════════════════════════╗")
	lines = append(lines, "║                    ARIA Startup Status                      ║")
	lines = append(lines, "╠════════════════════════════════════════════════════════════╣")

	statuses := v.tracker.GetAllStatuses()

	// Group by phase
	preFlight := []string{}
	coreServices := []string{}
	ariaComponents := []string{}
	optional := []string{}

	for name, state := range statuses {
		statusStr := v.formatStatus(state.Status)
		line := fmt.Sprintf("  %-20s %s", name, statusStr)

		priority := v.getPriority(name)
		switch {
		case priority < 100:
			preFlight = append(preFlight, line)
		case priority < 200:
			coreServices = append(coreServices, line)
		case priority < 300:
			ariaComponents = append(ariaComponents, line)
		default:
			optional = append(optional, line)
		}
	}

	if len(preFlight) > 0 {
		lines = append(lines, "║ PRE-FLIGHT                                                    ║")
		for _, l := range preFlight {
			lines = append(lines, fmt.Sprintf("║%s║", v.pad(l, 62)))
		}
	}

	if len(coreServices) > 0 {
		lines = append(lines, "║ CORE SERVICES                                                  ║")
		for _, l := range coreServices {
			lines = append(lines, fmt.Sprintf("║%s║", v.pad(l, 62)))
		}
	}

	if len(ariaComponents) > 0 {
		lines = append(lines, "║ ARIA COMPONENTS                                                ║")
		for _, l := range ariaComponents {
			lines = append(lines, fmt.Sprintf("║%s║", v.pad(l, 62)))
		}
	}

	if len(optional) > 0 {
		lines = append(lines, "║ OPTIONAL SERVICES                                              ║")
		for _, l := range optional {
			lines = append(lines, fmt.Sprintf("║%s║", v.pad(l, 62)))
		}
	}

	lines = append(lines, "╚════════════════════════════════════════════════════════════╝")

	return strings.Join(lines, "\n")
}

// RenderCompact renders a compact single-line status summary.
func (v *StartupStatusView) RenderCompact() string {
	statuses := v.tracker.GetAllStatuses()

	var healthy, degraded, unhealthy, unknown int
	for _, state := range statuses {
		switch state.Status {
		case StatusHealthy:
			healthy++
		case StatusDegraded:
			degraded++
		case StatusUnhealthy:
			unhealthy++
		default:
			unknown++
		}
	}

	var statusStr string
	switch {
	case unhealthy > 0:
		statusStr = unhealthyStyle.Render(fmt.Sprintf("✗ %d unhealthy", unhealthy))
	case degraded > 0:
		statusStr = degradedStyle.Render(fmt.Sprintf("⚠ %d degraded", degraded))
	case healthy > 0 && unknown == 0:
		statusStr = healthyStyle.Render("✓ healthy")
	default:
		statusStr = checkingStyle.Render(fmt.Sprintf("⟳ %d checking...", healthy+unknown))
	}

	return fmt.Sprintf("ARIA [%s]", statusStr)
}

// RenderSummary renders a one-line summary for status bar.
func (v *StartupStatusView) RenderSummary() string {
	return v.RenderCompact()
}

// formatStatus formats a status value with appropriate styling.
func (v *StartupStatusView) formatStatus(status ServiceStatus) string {
	switch status {
	case StatusHealthy:
		return healthyStyle.Render("● healthy")
	case StatusDegraded:
		return degradedStyle.Render("◐ degraded")
	case StatusUnhealthy:
		return unhealthyStyle.Render("○ unhealthy")
	case StatusPending:
		return pendingStyle.Render("○ pending")
	case StatusChecking:
		return checkingStyle.Render("◐ checking")
	case StatusRecovering:
		return checkingStyle.Render("◐ recovering")
	default:
		return unknownStyle.Render("○ unknown")
	}
}

// getPriority returns the priority for a service name.
func (v *StartupStatusView) getPriority(name string) int {
	// Map service names to their priorities
	priorities := map[string]int{
		"config":           10,
		"data-directory":   20,
		"database":         30,
		"session":          110,
		"message":          120,
		"history":          130,
		"permission":       140,
		"llm-provider":     150,
		"skill-registry":   210,
		"memory":           220,
		"memory-embedding": 225,
		"development":      230,
		"knowledge":        240,
		"weather":          250,
		"nutrition":        250,
		"orchestrator":     260,
		"scheduler":        270,
		"guardrail":        280,
		"lsp":              310,
		"mcp":              320,
	}

	if p, ok := priorities[name]; ok {
		return p
	}
	return 0
}

// pad pads a string to fit within a given width.
func (v *StartupStatusView) pad(s string, width int) string {
	if len(s) >= width {
		return s[:width]
	}
	return s + strings.Repeat(" ", width-len(s))
}

// ProgressView shows a progress bar during startup.
type ProgressView struct {
	total int
	done  int
	start time.Time
	mu    int
}

// NewProgressView creates a new ProgressView.
func NewProgressView(total int) *ProgressView {
	return &ProgressView{
		total: total,
		start: time.Now(),
	}
}

// Increment increments the done counter.
func (p *ProgressView) Increment() {
	p.mu++
	p.done++
}

// SetDone sets the number of completed items.
func (p *ProgressView) SetDone(done int) {
	p.mu++
	p.done = done
}

// Render renders the progress bar.
func (p *ProgressView) Render() string {
	p.mu++

	elapsed := time.Since(p.start)
	percent := float64(p.done) / float64(p.total) * 100

	barWidth := 40
	filled := int(float64(barWidth) * float64(p.done) / float64(p.total))
	bar := strings.Repeat("█", filled) + strings.Repeat("░", barWidth-filled)

	eta := time.Duration(0)
	if p.done > 0 {
		avgTime := elapsed / time.Duration(p.done)
		remaining := p.total - p.done
		eta = avgTime * time.Duration(remaining)
	}

	return fmt.Sprintf("[%s] %d/%d (%.0f%%) ETA: %s",
		bar, p.done, p.total, percent, eta.Round(time.Second))
}

// StatusBarComponent provides a compact view for TUI status bar.
type StatusBarComponent struct {
	tracker *StatusTracker
}

// NewStatusBarComponent creates a new StatusBarComponent.
func NewStatusBarComponent(tracker *StatusTracker) *StatusBarComponent {
	return &StatusBarComponent{
		tracker: tracker,
	}
}

// Render renders the status bar component.
func (c *StatusBarComponent) Render() string {
	statuses := c.tracker.GetAllStatuses()

	var issues []string
	var healthyCount int

	for name, state := range statuses {
		switch state.Status {
		case StatusUnhealthy:
			issues = append(issues, fmt.Sprintf("%s: %s", name, state.Error))
		case StatusDegraded:
			issues = append(issues, fmt.Sprintf("%s: degraded", name))
		case StatusHealthy:
			healthyCount++
		}
	}

	if len(issues) > 0 {
		return lipgloss.NewStyle().
			Foreground(lipgloss.Color("#FF5555")).
			Render(fmt.Sprintf("⚠ %d issues", len(issues)))
	}

	return lipgloss.NewStyle().
		Foreground(lipgloss.Color("#50FA7B")).
		Render(fmt.Sprintf("✓ %d services", healthyCount))
}
