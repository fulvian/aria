package page

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/table"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/fulvian/aria/internal/aria/scheduler"
	"github.com/fulvian/aria/internal/logging"
	"github.com/fulvian/aria/internal/tui/styles"
	"github.com/fulvian/aria/internal/tui/theme"
	"github.com/fulvian/aria/internal/tui/util"
)

// TasksPage is the page ID for the tasks page
var TasksPage PageID = "tasks"

// tasksPage implements the TUI page for task management
type tasksPage struct {
	scheduler  *scheduler.SchedulerService
	events     <-chan scheduler.TaskEvent
	width      int
	height     int
	tasks      []scheduler.Task
	selected   int
	filter     TaskFilter
	filterMenu bool
	eventList  []scheduler.TaskEvent
	tableModel table.Model
}

// TaskFilter represents filters for the task list
type TaskFilter struct {
	status string
	agency string
}

// TaskEventMsg is sent when a task event is received
type TaskEventMsg scheduler.TaskEvent

func (m *tasksPage) Init() tea.Cmd {
	m.loadTasks()
	m.subscribeToEvents()
	return nil
}

func (m *tasksPage) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd

	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, m.SetSize(msg.Width, msg.Height)

	case TaskEventMsg:
		// Refresh task list on any task event
		m.loadTasks()
		// If we have a selected task, reload its events
		if m.selected >= 0 && m.selected < len(m.tasks) {
			m.loadTaskEvents(m.tasks[m.selected].ID)
		}
		return m, nil

	case tea.KeyMsg:
		switch {
		case key.Matches(msg, key.NewBinding(key.WithKeys("q", "esc"))):
			return m, func() tea.Msg { return PageChangeMsg{ID: ChatPage} }

		case key.Matches(msg, key.NewBinding(key.WithKeys("c"))):
			if m.selected >= 0 && m.selected < len(m.tasks) {
				cmd := m.cancelSelected()
				if cmd != nil {
					return m, cmd
				}
			}

		case key.Matches(msg, key.NewBinding(key.WithKeys("p"))):
			if m.selected >= 0 && m.selected < len(m.tasks) {
				cmd := m.pauseSelected()
				if cmd != nil {
					return m, cmd
				}
			}

		case key.Matches(msg, key.NewBinding(key.WithKeys("r"))):
			if m.selected >= 0 && m.selected < len(m.tasks) {
				cmd := m.resumeSelected()
				if cmd != nil {
					return m, cmd
				}
			}

		case key.Matches(msg, key.NewBinding(key.WithKeys("f"))):
			m.filterMenu = !m.filterMenu

		case key.Matches(msg, key.NewBinding(key.WithKeys("up", "k"))):
			if m.selected > 0 {
				m.selected--
				m.tableModel.SetCursor(m.selected)
				m.loadTaskEvents(m.tasks[m.selected].ID)
			}

		case key.Matches(msg, key.NewBinding(key.WithKeys("down", "j"))):
			if m.selected < len(m.tasks)-1 {
				m.selected++
				m.tableModel.SetCursor(m.selected)
				m.loadTaskEvents(m.tasks[m.selected].ID)
			}

		case key.Matches(msg, key.NewBinding(key.WithKeys("1"))):
			m.filter.status = "all"
			m.loadTasks()

		case key.Matches(msg, key.NewBinding(key.WithKeys("2"))):
			m.filter.status = "running"
			m.loadTasks()

		case key.Matches(msg, key.NewBinding(key.WithKeys("3"))):
			m.filter.status = "queued"
			m.loadTasks()

		case key.Matches(msg, key.NewBinding(key.WithKeys("4"))):
			m.filter.status = "completed"
			m.loadTasks()

		case key.Matches(msg, key.NewBinding(key.WithKeys("5"))):
			m.filter.status = "failed"
			m.loadTasks()
		}
	}

	return m, tea.Batch(cmds...)
}

func (m *tasksPage) View() string {
	t := theme.CurrentTheme()

	// Build header
	header := m.renderHeader(t)

	// Build task list
	listView := m.renderTaskList(t)

	// Build detail panel
	detailView := m.renderDetail(t)

	// Build footer
	footer := m.renderFooter(t)

	// Combine views
	content := lipgloss.JoinVertical(lipgloss.Top,
		header,
		listView,
		detailView,
		footer,
	)

	style := styles.BaseStyle().Width(m.width).Height(m.height)
	return style.Render(content)
}

func (m *tasksPage) renderHeader(t theme.Theme) string {
	statusLabel := m.filter.status
	if statusLabel == "all" {
		statusLabel = "All Tasks"
	}
	title := styles.Bold().Render("Tasks")
	filterInfo := fmt.Sprintf("Filter: %s | Selected: %d/%d",
		statusLabel, m.selected+1, len(m.tasks))
	return fmt.Sprintf("%s %s\n", title, filterInfo)
}

func (m *tasksPage) renderTaskList(t theme.Theme) string {
	if len(m.tasks) == 0 {
		emptyStyle := lipgloss.NewStyle().
			Foreground(t.TextMuted()).
			Align(lipgloss.Center).
			Width(m.width)
		return emptyStyle.Render("\n\nNo tasks found.\n\nPress 'f' to change filter.")
	}

	// Calculate column widths
	colWidth := (m.width - 4) / 5
	if colWidth < 15 {
		colWidth = 15
	}

	columns := []table.Column{
		{Title: "Status", Width: 12},
		{Title: "Name", Width: colWidth * 2},
		{Title: "Agency", Width: colWidth},
		{Title: "Priority", Width: 10},
		{Title: "Created", Width: colWidth},
	}

	rows := make([]table.Row, 0, len(m.tasks))
	for _, task := range m.tasks {
		status := string(task.Status)
		if task.Status == scheduler.TaskStatusRunning {
			status = fmt.Sprintf("%s (%.0f%%)", task.Status, task.Progress*100)
		}
		priority := priorityLabel(task.Priority)
		created := task.CreatedAt.Format("15:04:05")
		if task.CreatedAt.IsZero() {
			created = "-"
		}

		row := table.Row{status, task.Name, task.Agency, priority, created}
		rows = append(rows, row)
	}

	// Build table model if not already done
	if !m.tableModel.Focused() {
		m.tableModel = table.New(
			table.WithColumns(columns),
			table.WithRows(rows),
			table.WithFocused(true),
		)
	} else {
		m.tableModel.SetRows(rows)
	}

	// Apply styling
	defaultStyles := table.DefaultStyles()
	defaultStyles.Selected = defaultStyles.Selected.
		Foreground(t.Primary()).
		Background(t.BackgroundSecondary())
	defaultStyles.Header = defaultStyles.Header.
		Foreground(t.TextMuted())
	m.tableModel.SetStyles(defaultStyles)

	// Highlight selected row
	if m.selected >= 0 && m.selected < len(rows) {
		m.tableModel.SetCursor(m.selected)
	}

	// Calculate height (留空间给其他部分)
	listHeight := m.height - 15
	if listHeight < 5 {
		listHeight = 5
	}
	m.tableModel.SetHeight(listHeight)

	return m.tableModel.View()
}

func (m *tasksPage) renderDetail(t theme.Theme) string {
	if m.selected < 0 || m.selected >= len(m.tasks) {
		emptyStyle := lipgloss.NewStyle().
			Foreground(t.TextMuted()).
			Width(m.width).
			Align(lipgloss.Center)
		return emptyStyle.Render("\n\nSelect a task to view details")
	}

	task := m.tasks[m.selected]

	detailStyle := lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(t.BorderNormal()).
		Width(m.width-2).
		Margin(0, 1)

	var sb strings.Builder

	// Task info
	sb.WriteString(fmt.Sprintf("Task: %s\n", task.Name))
	sb.WriteString(fmt.Sprintf("ID: %s\n", task.ID))
	sb.WriteString(fmt.Sprintf("Status: %s\n", task.Status))
	sb.WriteString(fmt.Sprintf("Type: %s\n", task.Type))
	sb.WriteString(fmt.Sprintf("Agency: %s\n", task.Agency))
	sb.WriteString(fmt.Sprintf("Agent: %s\n", task.Agent))

	if task.Progress > 0 {
		sb.WriteString(fmt.Sprintf("Progress: %.0f%%\n", task.Progress*100))
	}

	if task.StartedAt != nil {
		sb.WriteString(fmt.Sprintf("Started: %s\n", task.StartedAt.Format("15:04:05")))
	}
	if task.EndedAt != nil {
		sb.WriteString(fmt.Sprintf("Ended: %s\n", task.EndedAt.Format("15:04:05")))
	}

	// Result
	if task.Result != nil {
		sb.WriteString("\nResult:\n")
		resultJSON, _ := json.MarshalIndent(task.Result.Output, "", "  ")
		sb.WriteString(string(resultJSON))
		sb.WriteString("\n")
	}

	// Error
	if task.Error != nil {
		sb.WriteString(fmt.Sprintf("\nError: %s\n", task.Error.Message))
		if task.Error.Code != "" {
			sb.WriteString(fmt.Sprintf("Code: %s\n", task.Error.Code))
		}
	}

	// Events
	if len(m.eventList) > 0 {
		sb.WriteString("\nEvents:\n")
		for _, evt := range m.eventList {
			ts := evt.Timestamp.Format("15:04:05")
			progress := ""
			if evt.Progress > 0 {
				progress = fmt.Sprintf("(%.0f%%)", evt.Progress*100)
			}
			sb.WriteString(fmt.Sprintf("  [%s] %s %s %s\n", ts, evt.Type, progress, evt.Message))
		}
	}

	return detailStyle.Render(sb.String())
}

func (m *tasksPage) renderFooter(t theme.Theme) string {
	footerStyle := lipgloss.NewStyle().
		Foreground(t.TextMuted())

	var actions []string
	actions = append(actions, fmt.Sprintf("[c] Cancel  [p] Pause  [r] Resume"))
	actions = append(actions, fmt.Sprintf("[f] Filter  [1] All  [2] Running  [3] Queued  [4] Completed  [5] Failed"))
	actions = append(actions, fmt.Sprintf("[↑/↓] Select  [q] Back"))

	return footerStyle.Render(strings.Join(actions, "\n"))
}

func (m *tasksPage) loadTasks() {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	filter := scheduler.TaskFilter{
		Limit: 100,
	}

	switch m.filter.status {
	case "running":
		filter.Status = []scheduler.TaskStatus{scheduler.TaskStatusRunning}
	case "queued":
		filter.Status = []scheduler.TaskStatus{scheduler.TaskStatusQueued}
	case "completed":
		filter.Status = []scheduler.TaskStatus{scheduler.TaskStatusCompleted}
	case "failed":
		filter.Status = []scheduler.TaskStatus{scheduler.TaskStatusFailed}
	}

	tasks, err := m.scheduler.ListTasks(ctx, filter)
	if err != nil {
		logging.Error("failed to load tasks", "error", err)
		return
	}

	m.tasks = tasks

	// Ensure selected is within bounds
	if m.selected >= len(m.tasks) {
		m.selected = len(m.tasks) - 1
	}
	if m.selected < 0 && len(m.tasks) > 0 {
		m.selected = 0
	}

	// Load events for selected task
	if m.selected >= 0 && m.selected < len(m.tasks) {
		m.loadTaskEvents(m.tasks[m.selected].ID)
	}
}

func (m *tasksPage) loadTaskEvents(taskID scheduler.TaskID) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// Get task to build event list from task state
	task, err := m.scheduler.GetTask(ctx, taskID)
	if err != nil {
		m.eventList = nil
		return
	}

	// Build event list from task history
	m.eventList = nil

	// Create synthetic events based on task state
	m.eventList = append(m.eventList, scheduler.TaskEvent{
		TaskID:    task.ID,
		Type:      "created",
		Timestamp: task.CreatedAt,
	})

	if task.StartedAt != nil {
		m.eventList = append(m.eventList, scheduler.TaskEvent{
			TaskID:    task.ID,
			Type:      "started",
			Timestamp: *task.StartedAt,
		})
	}

	if task.Status == scheduler.TaskStatusCompleted {
		if task.EndedAt != nil {
			m.eventList = append(m.eventList, scheduler.TaskEvent{
				TaskID:    task.ID,
				Type:      "completed",
				Progress:  1.0,
				Timestamp: *task.EndedAt,
			})
		}
	} else if task.Status == scheduler.TaskStatusFailed {
		if task.EndedAt != nil {
			m.eventList = append(m.eventList, scheduler.TaskEvent{
				TaskID:    task.ID,
				Type:      "failed",
				Timestamp: *task.EndedAt,
				Message:   getErrorMessage(task.Error),
			})
		}
	}
}

func (m *tasksPage) subscribeToEvents() {
	ctx, cancel := context.WithCancel(context.Background())
	m.events = m.scheduler.Subscribe(ctx)
	go func() {
		defer cancel()
		for {
			select {
			case event, ok := <-m.events:
				if !ok {
					return
				}
				// Send event to update loop
				tea.Printf("%v", TaskEventMsg(event))
			case <-ctx.Done():
				return
			}
		}
	}()
}

func (m *tasksPage) cancelSelected() tea.Cmd {
	if m.selected < 0 || m.selected >= len(m.tasks) {
		return nil
	}

	task := m.tasks[m.selected]
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := m.scheduler.Cancel(ctx, task.ID)
	if err != nil {
		return util.ReportError(fmt.Errorf("failed to cancel task: %w", err))
	}

	m.loadTasks()
	return util.ReportInfo(fmt.Sprintf("Task '%s' cancelled", task.Name))
}

func (m *tasksPage) pauseSelected() tea.Cmd {
	if m.selected < 0 || m.selected >= len(m.tasks) {
		return nil
	}

	task := m.tasks[m.selected]
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := m.scheduler.Pause(ctx, task.ID)
	if err != nil {
		return util.ReportError(fmt.Errorf("failed to pause task: %w", err))
	}

	m.loadTasks()
	return util.ReportInfo(fmt.Sprintf("Task '%s' paused", task.Name))
}

func (m *tasksPage) resumeSelected() tea.Cmd {
	if m.selected < 0 || m.selected >= len(m.tasks) {
		return nil
	}

	task := m.tasks[m.selected]
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := m.scheduler.Resume(ctx, task.ID)
	if err != nil {
		return util.ReportError(fmt.Errorf("failed to resume task: %w", err))
	}

	m.loadTasks()
	return util.ReportInfo(fmt.Sprintf("Task '%s' resumed", task.Name))
}

// GetSize implements layout.Sizeable
func (m *tasksPage) GetSize() (int, int) {
	return m.width, m.height
}

// SetSize implements layout.Sizeable
func (m *tasksPage) SetSize(width int, height int) tea.Cmd {
	m.width = width
	m.height = height
	return nil
}

// BindingKeys returns the key bindings for this page
func (m *tasksPage) BindingKeys() []key.Binding {
	return []key.Binding{
		key.NewBinding(key.WithKeys("q"), key.WithHelp("q", "back")),
		key.NewBinding(key.WithKeys("c"), key.WithHelp("c", "cancel")),
		key.NewBinding(key.WithKeys("p"), key.WithHelp("p", "pause")),
		key.NewBinding(key.WithKeys("r"), key.WithHelp("r", "resume")),
		key.NewBinding(key.WithKeys("f"), key.WithHelp("f", "filter")),
		key.NewBinding(key.WithKeys("up", "k"), key.WithHelp("↑/k", "up")),
		key.NewBinding(key.WithKeys("down", "j"), key.WithHelp("↓/j", "down")),
	}
}

// NewTasksPage creates a new tasks page
func NewTasksPage(schedulerService *scheduler.SchedulerService) *tasksPage {
	return &tasksPage{
		scheduler: schedulerService,
		selected:  0,
		filter:    TaskFilter{status: "all"},
	}
}

// Helper functions

func priorityLabel(p scheduler.Priority) string {
	switch p {
	case scheduler.PriorityLow:
		return "Low"
	case scheduler.PriorityNormal:
		return "Normal"
	case scheduler.PriorityHigh:
		return "High"
	case scheduler.PriorityCritical:
		return "Critical"
	default:
		return "Normal"
	}
}

func getErrorMessage(err *scheduler.TaskError) string {
	if err == nil {
		return ""
	}
	return err.Message
}
