package chat

import (
	"context"
	"encoding/base64"
	"fmt"
	"math"
	"os"

	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/fulvian/aria/internal/app"
	"github.com/fulvian/aria/internal/message"
	"github.com/fulvian/aria/internal/pubsub"
	"github.com/fulvian/aria/internal/session"
	"github.com/fulvian/aria/internal/tui/components/dialog"
	"github.com/fulvian/aria/internal/tui/styles"
	"github.com/fulvian/aria/internal/tui/theme"
	"github.com/fulvian/aria/internal/tui/util"
)

type cacheItem struct {
	width   int
	content []uiMessage
}

// SelectionModeMsg toggles keyboard selection mode
type SelectionModeMsg bool

// CopySelectedMsg triggers copy of the currently selected message
type CopySelectedMsg struct{}

type messagesCmp struct {
	app           *app.App
	width, height int
	viewport      viewport.Model
	session       session.Session
	messages      []message.Message
	uiMessages    []uiMessage
	currentMsgID  string
	cachedContent map[string]cacheItem
	spinner       spinner.Model
	rendering     bool
	attachments   viewport.Model

	// Text selection state
	selectionMode   bool // True when keyboard selection is active (Tab pressed)
	selectedIndex   int  // Index of the selected message in uiMessages
	selecting       bool
	selectionStartY int
	selectionEndY   int
}
type renderFinishedMsg struct{}

type MessageKeys struct {
	PageDown     key.Binding
	PageUp       key.Binding
	HalfPageUp   key.Binding
	HalfPageDown key.Binding
	Up           key.Binding
	Down         key.Binding
	SelectPrev   key.Binding
	SelectNext   key.Binding
	CopySelected key.Binding
}

var messageKeys = MessageKeys{
	PageDown: key.NewBinding(
		key.WithKeys("pgdown"),
		key.WithHelp("f/pgdn", "page down"),
	),
	PageUp: key.NewBinding(
		key.WithKeys("pgup"),
		key.WithHelp("b/pgup", "page up"),
	),
	HalfPageUp: key.NewBinding(
		key.WithKeys("ctrl+u"),
		key.WithHelp("ctrl+u", "½ page up"),
	),
	HalfPageDown: key.NewBinding(
		key.WithKeys("ctrl+d", "ctrl+d"),
		key.WithHelp("ctrl+d", "½ page down"),
	),
	Up: key.NewBinding(
		key.WithKeys("up", "k"),
		key.WithHelp("↑/k", "scroll up"),
	),
	Down: key.NewBinding(
		key.WithKeys("down", "j"),
		key.WithHelp("↓/j", "scroll down"),
	),
	SelectPrev: key.NewBinding(
		key.WithKeys("shift+up"),
		key.WithHelp("shift+↑", "prev"),
	),
	SelectNext: key.NewBinding(
		key.WithKeys("shift+down"),
		key.WithHelp("shift+↓", "next"),
	),
	CopySelected: key.NewBinding(
		key.WithKeys("c"),
		key.WithHelp("c", "copy"),
	),
}

func (m *messagesCmp) Init() tea.Cmd {
	return tea.Batch(m.viewport.Init(), m.spinner.Tick)
}

func (m *messagesCmp) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd
	switch msg := msg.(type) {
	case dialog.ThemeChangedMsg:
		m.rerender()
		return m, nil
	case SessionSelectedMsg:
		if msg.ID != m.session.ID {
			cmd := m.SetSession(msg)
			return m, cmd
		}
		return m, nil
	case SessionClearedMsg:
		m.session = session.Session{}
		m.messages = make([]message.Message, 0)
		m.currentMsgID = ""
		m.rendering = false
		m.selectionMode = false
		m.selectedIndex = -1
		return m, nil

	case SelectionModeMsg:
		m.selectionMode = bool(msg)
		if m.selectionMode && len(m.uiMessages) > 0 {
			// Start with the last message selected
			m.selectedIndex = len(m.uiMessages) - 1
		} else {
			m.selectedIndex = -1
		}
		return m, nil

	case CopySelectedMsg:
		if m.selectedIndex >= 0 && m.selectedIndex < len(m.uiMessages) {
			uiMsg := m.uiMessages[m.selectedIndex]
			plainText := uiMsg.plainContent
			if plainText == "" {
				plainText = stripANSI(uiMsg.content)
			}
			if plainText != "" {
				cmds = append(cmds, copyToClipboardCmd(plainText))
			}
		}
		return m, tea.Batch(cmds...)

	case tea.KeyMsg:
		// Handle selection mode keys first (only when selectionMode is active)
		if m.selectionMode {
			switch {
			case key.Matches(msg, messageKeys.SelectPrev):
				// Move selection to previous message
				if m.selectedIndex > 0 {
					m.selectedIndex--
					// Scroll to show selected message
					m.scrollToSelected()
				}
				return m, nil
			case key.Matches(msg, messageKeys.SelectNext):
				// Move selection to next message
				if m.selectedIndex < len(m.uiMessages)-1 {
					m.selectedIndex++
					// Scroll to show selected message
					m.scrollToSelected()
				}
				return m, nil
			case key.Matches(msg, messageKeys.CopySelected):
				// Copy the selected message
				if m.selectedIndex >= 0 && m.selectedIndex < len(m.uiMessages) {
					uiMsg := m.uiMessages[m.selectedIndex]
					plainText := uiMsg.plainContent
					if plainText == "" {
						plainText = stripANSI(uiMsg.content)
					}
					if plainText != "" {
						cmds = append(cmds, copyToClipboardCmd(plainText))
					}
				}
				return m, tea.Batch(cmds...)
			}
		}

		// Normal viewport navigation (only when NOT in selection mode)
		if !m.selectionMode && (key.Matches(msg, messageKeys.PageUp) || key.Matches(msg, messageKeys.PageDown) ||
			key.Matches(msg, messageKeys.HalfPageUp) || key.Matches(msg, messageKeys.HalfPageDown) ||
			key.Matches(msg, messageKeys.Up) || key.Matches(msg, messageKeys.Down)) {
			u, cmd := m.viewport.Update(msg)
			m.viewport = u
			cmds = append(cmds, cmd)
		}

	case tea.MouseMsg:
		switch msg.Type {
		case tea.MouseWheelUp, tea.MouseWheelDown:
			u, cmd := m.viewport.Update(msg)
			m.viewport = u
			cmds = append(cmds, cmd)
		}
		// Handle click to copy message text
		if msg.Button == tea.MouseButtonLeft && msg.Action == tea.MouseActionPress {
			m.selectionStartY = msg.Y
			m.selecting = true
		} else if msg.Button == tea.MouseButtonLeft && msg.Action == tea.MouseActionRelease && m.selecting {
			m.selectionEndY = msg.Y
			m.selecting = false
			// Copy the message at click position
			if cmd := m.copyMessageAtY(msg.Y); cmd != nil {
				cmds = append(cmds, cmd)
			}
		}

	case renderFinishedMsg:
		m.rendering = false
		m.viewport.GotoBottom()
	case pubsub.Event[session.Session]:
		if msg.Type == pubsub.UpdatedEvent && msg.Payload.ID == m.session.ID {
			m.session = msg.Payload
			if m.session.SummaryMessageID == m.currentMsgID {
				delete(m.cachedContent, m.currentMsgID)
				m.renderView()
			}
		}
	case pubsub.Event[message.Message]:
		needsRerender := false
		if msg.Type == pubsub.CreatedEvent {
			if msg.Payload.SessionID == m.session.ID {

				messageExists := false
				for _, v := range m.messages {
					if v.ID == msg.Payload.ID {
						messageExists = true
						break
					}
				}

				if !messageExists {
					if len(m.messages) > 0 {
						lastMsgID := m.messages[len(m.messages)-1].ID
						delete(m.cachedContent, lastMsgID)
					}

					m.messages = append(m.messages, msg.Payload)
					delete(m.cachedContent, m.currentMsgID)
					m.currentMsgID = msg.Payload.ID
					needsRerender = true
				}
			}
			// There are tool calls from the child task
			for _, v := range m.messages {
				for _, c := range v.ToolCalls() {
					if c.ID == msg.Payload.SessionID {
						delete(m.cachedContent, v.ID)
						needsRerender = true
					}
				}
			}
		} else if msg.Type == pubsub.UpdatedEvent && msg.Payload.SessionID == m.session.ID {
			for i, v := range m.messages {
				if v.ID == msg.Payload.ID {
					m.messages[i] = msg.Payload
					delete(m.cachedContent, msg.Payload.ID)
					needsRerender = true
					break
				}
			}
		}
		if needsRerender {
			m.renderView()
			if len(m.messages) > 0 {
				if (msg.Type == pubsub.CreatedEvent) ||
					(msg.Type == pubsub.UpdatedEvent && msg.Payload.ID == m.messages[len(m.messages)-1].ID) {
					m.viewport.GotoBottom()
				}
			}
		}
	}

	spinner, cmd := m.spinner.Update(msg)
	m.spinner = spinner
	cmds = append(cmds, cmd)
	return m, tea.Batch(cmds...)
}

func (m *messagesCmp) IsAgentWorking() bool {
	return m.app.CoderAgent.IsSessionBusy(m.session.ID)
}

func formatTimeDifference(unixTime1, unixTime2 int64) string {
	diffSeconds := float64(math.Abs(float64(unixTime2 - unixTime1)))

	if diffSeconds < 60 {
		return fmt.Sprintf("%.1fs", diffSeconds)
	}

	minutes := int(diffSeconds / 60)
	seconds := int(diffSeconds) % 60
	return fmt.Sprintf("%dm%ds", minutes, seconds)
}

func (m *messagesCmp) renderView() {
	m.uiMessages = make([]uiMessage, 0)
	pos := 0
	baseStyle := styles.BaseStyle()

	if m.width == 0 {
		return
	}
	for inx, msg := range m.messages {
		switch msg.Role {
		case message.User:
			if cache, ok := m.cachedContent[msg.ID]; ok && cache.width == m.width {
				m.uiMessages = append(m.uiMessages, cache.content...)
				continue
			}
			userMsg := renderUserMessage(
				msg,
				msg.ID == m.currentMsgID,
				m.width,
				pos,
			)
			m.uiMessages = append(m.uiMessages, userMsg)
			m.cachedContent[msg.ID] = cacheItem{
				width:   m.width,
				content: []uiMessage{userMsg},
			}
			pos += userMsg.height + 1 // + 1 for spacing
		case message.Assistant:
			if cache, ok := m.cachedContent[msg.ID]; ok && cache.width == m.width {
				m.uiMessages = append(m.uiMessages, cache.content...)
				continue
			}
			isSummary := m.session.SummaryMessageID == msg.ID

			assistantMessages := renderAssistantMessage(
				msg,
				inx,
				m.messages,
				m.app.Messages,
				m.currentMsgID,
				isSummary,
				m.width,
				pos,
			)
			for _, msg := range assistantMessages {
				m.uiMessages = append(m.uiMessages, msg)
				pos += msg.height + 1 // + 1 for spacing
			}
			m.cachedContent[msg.ID] = cacheItem{
				width:   m.width,
				content: assistantMessages,
			}
		}
	}

	messages := make([]string, 0)
	for _, v := range m.uiMessages {
		messages = append(messages, lipgloss.JoinVertical(lipgloss.Left, v.content),
			baseStyle.
				Width(m.width).
				Render(
					"",
				),
		)
	}

	m.viewport.SetContent(
		baseStyle.
			Width(m.width).
			Render(
				lipgloss.JoinVertical(
					lipgloss.Top,
					messages...,
				),
			),
	)
}

func (m *messagesCmp) View() string {
	baseStyle := styles.BaseStyle()

	if m.rendering {
		return baseStyle.
			Width(m.width).
			Render(
				lipgloss.JoinVertical(
					lipgloss.Top,
					"Loading...",
					m.working(),
					m.help(),
				),
			)
	}
	if len(m.messages) == 0 {
		content := baseStyle.
			Width(m.width).
			Height(m.height - 1).
			Render(
				m.initialScreen(),
			)

		return baseStyle.
			Width(m.width).
			Render(
				lipgloss.JoinVertical(
					lipgloss.Top,
					content,
					"",
					m.help(),
				),
			)
	}

	return baseStyle.
		Width(m.width).
		Render(
			lipgloss.JoinVertical(
				lipgloss.Top,
				m.viewport.View(),
				m.working(),
				m.help(),
			),
		)
}

func hasToolsWithoutResponse(messages []message.Message) bool {
	toolCalls := make([]message.ToolCall, 0)
	toolResults := make([]message.ToolResult, 0)
	for _, m := range messages {
		toolCalls = append(toolCalls, m.ToolCalls()...)
		toolResults = append(toolResults, m.ToolResults()...)
	}

	for _, v := range toolCalls {
		found := false
		for _, r := range toolResults {
			if v.ID == r.ToolCallID {
				found = true
				break
			}
		}
		if !found && v.Finished {
			return true
		}
	}
	return false
}

func hasUnfinishedToolCalls(messages []message.Message) bool {
	toolCalls := make([]message.ToolCall, 0)
	for _, m := range messages {
		toolCalls = append(toolCalls, m.ToolCalls()...)
	}
	for _, v := range toolCalls {
		if !v.Finished {
			return true
		}
	}
	return false
}

func (m *messagesCmp) working() string {
	text := ""
	if m.IsAgentWorking() && len(m.messages) > 0 {
		t := theme.CurrentTheme()
		baseStyle := styles.BaseStyle()

		task := "Thinking..."
		lastMessage := m.messages[len(m.messages)-1]
		if hasToolsWithoutResponse(m.messages) {
			task = "Waiting for tool response..."
		} else if hasUnfinishedToolCalls(m.messages) {
			task = "Building tool call..."
		} else if !lastMessage.IsFinished() {
			task = "Generating..."
		}
		if task != "" {
			text += baseStyle.
				Width(m.width).
				Foreground(t.Primary()).
				Bold(true).
				Render(fmt.Sprintf("%s %s ", m.spinner.View(), task))
		}
	}
	return text
}

func (m *messagesCmp) help() string {
	t := theme.CurrentTheme()
	baseStyle := styles.BaseStyle()

	text := ""

	if m.app.CoderAgent.IsBusy() {
		text += lipgloss.JoinHorizontal(
			lipgloss.Left,
			baseStyle.Foreground(t.TextMuted()).Bold(true).Render("press "),
			baseStyle.Foreground(t.Text()).Bold(true).Render("esc"),
			baseStyle.Foreground(t.TextMuted()).Bold(true).Render(" to exit cancel"),
		)
	} else {
		text += lipgloss.JoinHorizontal(
			lipgloss.Left,
			baseStyle.Foreground(t.TextMuted()).Bold(true).Render("press "),
			baseStyle.Foreground(t.Text()).Bold(true).Render("enter"),
			baseStyle.Foreground(t.TextMuted()).Bold(true).Render(" to send,"),
			baseStyle.Foreground(t.Text()).Bold(true).Render(" pgup/pgdn"),
			baseStyle.Foreground(t.TextMuted()).Bold(true).Render(" or "),
			baseStyle.Foreground(t.Text()).Bold(true).Render("↑/↓"),
			baseStyle.Foreground(t.TextMuted()).Bold(true).Render(" to scroll,"),
			baseStyle.Foreground(t.Text()).Bold(true).Render(" ctrl+m"),
			baseStyle.Foreground(t.TextMuted()).Bold(true).Render(" to toggle text selection"),
		)
	}
	return baseStyle.
		Width(m.width).
		Render(text)
}

func (m *messagesCmp) initialScreen() string {
	baseStyle := styles.BaseStyle()

	return baseStyle.Width(m.width).Render(
		lipgloss.JoinVertical(
			lipgloss.Top,
			header(m.width),
			"",
			lspsConfigured(m.width),
		),
	)
}

func (m *messagesCmp) rerender() {
	for _, msg := range m.messages {
		delete(m.cachedContent, msg.ID)
	}
	m.renderView()
}

func (m *messagesCmp) SetSize(width, height int) tea.Cmd {
	if m.width == width && m.height == height {
		return nil
	}
	m.width = width
	m.height = height
	m.viewport.Width = width
	m.viewport.Height = height - 2
	m.attachments.Width = width + 40
	m.attachments.Height = 3
	m.rerender()
	return nil
}

func (m *messagesCmp) GetSize() (int, int) {
	return m.width, m.height
}

func (m *messagesCmp) SetSession(session session.Session) tea.Cmd {
	if m.session.ID == session.ID {
		return nil
	}
	m.session = session
	messages, err := m.app.Messages.List(context.Background(), session.ID)
	if err != nil {
		return util.ReportError(err)
	}
	m.messages = messages
	if len(m.messages) > 0 {
		m.currentMsgID = m.messages[len(m.messages)-1].ID
	}
	delete(m.cachedContent, m.currentMsgID)
	m.rendering = true
	return func() tea.Msg {
		m.renderView()
		return renderFinishedMsg{}
	}
}

// scrollToSelected scrolls the viewport to show the currently selected message
func (m *messagesCmp) scrollToSelected() {
	if m.selectedIndex < 0 || m.selectedIndex >= len(m.uiMessages) {
		return
	}

	uiMsg := m.uiMessages[m.selectedIndex]
	// Calculate the Y position to scroll to
	// The viewport scroll position is measured from the top of the content
	targetY := uiMsg.position

	// Get current viewport state
	viewportHeight := m.viewport.Height
	viewportY := m.viewport.YOffset

	// Only scroll if the selected message is not visible
	if targetY < viewportY {
		// Selected message is above viewport - scroll up
		m.viewport.YOffset = max(0, targetY)
	} else if targetY+uiMsg.height > viewportY+viewportHeight {
		// Selected message is below viewport - scroll down
		m.viewport.YOffset = targetY + uiMsg.height - viewportHeight
	}
}

func (m *messagesCmp) BindingKeys() []key.Binding {
	bindings := []key.Binding{
		m.viewport.KeyMap.PageDown,
		m.viewport.KeyMap.PageUp,
		m.viewport.KeyMap.HalfPageUp,
		m.viewport.KeyMap.HalfPageDown,
		m.viewport.KeyMap.Up,
		m.viewport.KeyMap.Down,
	}
	// Add selection mode keybindings when active
	if m.selectionMode {
		bindings = append(bindings,
			messageKeys.SelectPrev,
			messageKeys.SelectNext,
			messageKeys.CopySelected,
		)
	}
	return bindings
}

func NewMessagesCmp(app *app.App) tea.Model {
	s := spinner.New()
	s.Spinner = spinner.Pulse
	vp := viewport.New(0, 0)
	attachmets := viewport.New(0, 0)
	vp.KeyMap.PageUp = messageKeys.PageUp
	vp.KeyMap.PageDown = messageKeys.PageDown
	vp.KeyMap.HalfPageUp = messageKeys.HalfPageUp
	vp.KeyMap.HalfPageDown = messageKeys.HalfPageDown
	vp.KeyMap.Up = messageKeys.Up
	vp.KeyMap.Down = messageKeys.Down
	return &messagesCmp{
		app:           app,
		cachedContent: make(map[string]cacheItem),
		viewport:      vp,
		spinner:       s,
		attachments:   attachmets,
	}
}

// copyMessageAtY finds the message at the given Y coordinate and copies its plain text to clipboard
func (m *messagesCmp) copyMessageAtY(y int) tea.Cmd {
	if len(m.uiMessages) == 0 {
		return nil
	}

	// Y is relative to the viewport content
	// Adjust for viewport scroll offset
	absoluteY := m.viewport.YOffset + y

	// Find the uiMessage that contains this Y coordinate
	for _, uiMsg := range m.uiMessages {
		if absoluteY >= uiMsg.position && absoluteY < uiMsg.position+uiMsg.height {
			// Found the message - extract plain text and copy to clipboard
			plainText := uiMsg.plainContent
			if plainText == "" {
				// Fallback: strip ANSI codes from styled content
				plainText = stripANSI(uiMsg.content)
			}
			if plainText != "" {
				// Use OSC 52 escape sequence to copy to clipboard
				return copyToClipboardCmd(plainText)
			}
			break
		}
	}
	return nil
}

// copyToClipboardCmd creates a command that copies text to the system clipboard using OSC 52
func copyToClipboardCmd(text string) tea.Cmd {
	return func() tea.Msg {
		// Encode text as base64
		encoded := base64.StdEncoding.EncodeToString([]byte(text))
		// OSC 52 escape sequence: ESC ] 52 ; c ; BASE64_TEXT BEL
		sequence := fmt.Sprintf("\x1b]52;c;%s\x07", encoded)
		// Write directly to stdout (the terminal)
		os.Stdout.Write([]byte(sequence))
		os.Stdout.Sync()
		return nil
	}
}
