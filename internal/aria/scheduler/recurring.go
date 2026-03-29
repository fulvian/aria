package scheduler

import (
	"context"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/fulvian/aria/internal/logging"
	"github.com/fulvian/aria/internal/pubsub"
)

// Cron expression format: minute hour day month weekday
// Examples:
//   - 0 * * * *   - every hour at minute 0
//   - 0 9 * * 1-5 - every weekday at 9am
//   - */15 * * * * - every 15 minutes

var (
	ErrInvalidCronExpr  = fmt.Errorf("invalid cron expression")
	ErrInvalidInterval  = fmt.Errorf("invalid interval expression")
	ErrInvalidSchedule  = fmt.Errorf("invalid schedule")
	ErrNoIdempotencyKey = fmt.Errorf("idempotency key conflict")
)

// intervalRegex matches "every:X" where X is a duration (e.g., "every:5m", "every:1h")
var intervalRegex = regexp.MustCompile(`^every:(\d+)([smhd])$`)

// ParseInterval parses an interval expression like "every:5m" and returns the duration.
func ParseInterval(expr string) (time.Duration, error) {
	expr = strings.TrimSpace(expr)
	matches := intervalRegex.FindStringSubmatch(expr)
	if matches == nil {
		return 0, fmt.Errorf("%w: expected format 'every:X' where X is duration (e.g., 'every:5m', 'every:1h'), got '%s'", ErrInvalidInterval, expr)
	}

	value, err := strconv.ParseInt(matches[1], 10, 64)
	if err != nil {
		return 0, fmt.Errorf("%w: invalid duration value: %s", ErrInvalidInterval, err)
	}

	if value <= 0 {
		return 0, fmt.Errorf("%w: duration must be positive", ErrInvalidInterval)
	}

	var duration time.Duration
	switch matches[2] {
	case "s":
		duration = time.Duration(value) * time.Second
	case "m":
		duration = time.Duration(value) * time.Minute
	case "h":
		duration = time.Duration(value) * time.Hour
	case "d":
		duration = time.Duration(value) * 24 * time.Hour
	default:
		return 0, fmt.Errorf("%w: unknown unit '%s'", ErrInvalidInterval, matches[2])
	}

	return duration, nil
}

// ParseCron parses a cron expression and computes the next run time from the given time.
// Uses standard cron format: minute hour day month weekday
func ParseCron(expr string) (time.Time, error) {
	expr = strings.TrimSpace(expr)
	fields := strings.Fields(expr)
	if len(fields) != 5 {
		return time.Time{}, fmt.Errorf("%w: expected 5 fields (minute hour day month weekday), got %d", ErrInvalidCronExpr, len(fields))
	}

	// Parse each field
	minField, err := parseCronField(fields[0], 0, 59) // minute: 0-59
	if err != nil {
		return time.Time{}, fmt.Errorf("%w: invalid minute field: %s", ErrInvalidCronExpr, err)
	}

	hourField, err := parseCronField(fields[1], 0, 23) // hour: 0-23
	if err != nil {
		return time.Time{}, fmt.Errorf("%w: invalid hour field: %s", ErrInvalidCronExpr, err)
	}

	dayField, err := parseCronField(fields[2], 1, 31) // day: 1-31
	if err != nil {
		return time.Time{}, fmt.Errorf("%w: invalid day field: %s", ErrInvalidCronExpr, err)
	}

	monthField, err := parseCronField(fields[3], 1, 12) // month: 1-12
	if err != nil {
		return time.Time{}, fmt.Errorf("%w: invalid month field: %s", ErrInvalidCronExpr, err)
	}

	weekdayField, err := parseCronField(fields[4], 0, 6) // weekday: 0-6 (0 = Sunday)
	if err != nil {
		return time.Time{}, fmt.Errorf("%w: invalid weekday field: %s", ErrInvalidCronExpr, err)
	}

	// Compute next run time
	return computeNextCronRun(time.Now(), minField, hourField, dayField, monthField, weekdayField)
}

// cronField represents a parsed cron field with possible values, ranges, and steps
type cronField struct {
	values  []int
	ranges  [][2]int // inclusive ranges
	hasStep bool
	step    int
}

// parseCronField parses a single cron field which can be:
// - * (any)
// - specific value (e.g., "5")
// - comma-separated values (e.g., "1,3,5")
// - range with step (e.g., "1-5")
// - step expression (e.g., "*/15")
func parseCronField(field string, min, max int) (*cronField, error) {
	if field == "*" {
		return &cronField{
			values:  nil, // nil means "any"
			ranges:  nil,
			hasStep: false,
			step:    1,
		}, nil
	}

	cf := &cronField{}

	// Check for step expression
	if strings.Contains(field, "/") {
		parts := strings.Split(field, "/")
		if len(parts) != 2 {
			return nil, fmt.Errorf("invalid step expression '%s'", field)
		}
		cf.hasStep = true
		step, err := strconv.Atoi(parts[1])
		if err != nil || step <= 0 {
			return nil, fmt.Errorf("invalid step value '%s': %s", parts[1], err)
		}
		cf.step = step

		// The base part before / can be * or a number
		base := parts[0]
		if base != "*" {
			val, err := strconv.Atoi(base)
			if err != nil {
				return nil, fmt.Errorf("invalid step base '%s': %s", base, err)
			}
			if val < min || val > max {
				return nil, fmt.Errorf("value %d out of range (%d-%d)", val, min, max)
			}
			cf.values = []int{val}
		}
		// If base is *, values remain nil (will be filled in computeNextCronRun)
		return cf, nil
	}

	// Check for range expression
	if strings.Contains(field, "-") {
		parts := strings.Split(field, "-")
		if len(parts) != 2 {
			return nil, fmt.Errorf("invalid range expression '%s'", field)
		}
		start, err := strconv.Atoi(parts[0])
		if err != nil {
			return nil, fmt.Errorf("invalid range start '%s': %s", parts[0], err)
		}
		end, err := strconv.Atoi(parts[1])
		if err != nil {
			return nil, fmt.Errorf("invalid range end '%s': %s", parts[1], err)
		}
		if start < min || end > max || start > end {
			return nil, fmt.Errorf("range %d-%d out of bounds (%d-%d)", start, end, min, max)
		}
		cf.ranges = [][2]int{{start, end}}
		return cf, nil
	}

	// Check for comma-separated values
	if strings.Contains(field, ",") {
		parts := strings.Split(field, ",")
		values := make([]int, 0, len(parts))
		for _, p := range parts {
			val, err := strconv.Atoi(strings.TrimSpace(p))
			if err != nil {
				return nil, fmt.Errorf("invalid value '%s': %s", p, err)
			}
			if val < min || val > max {
				return nil, fmt.Errorf("value %d out of range (%d-%d)", val, min, max)
			}
			values = append(values, val)
		}
		cf.values = values
		return cf, nil
	}

	// Single value
	val, err := strconv.Atoi(field)
	if err != nil {
		return nil, fmt.Errorf("invalid value '%s': %s", field, err)
	}
	if val < min || val > max {
		return nil, fmt.Errorf("value %d out of range (%d-%d)", val, min, max)
	}
	cf.values = []int{val}
	return cf, nil
}

// computeNextCronRun finds the next time that matches the cron fields
func computeNextCronRun(from time.Time, min, hour, day, month, weekday *cronField) (time.Time, error) {
	// Start from the next minute
	t := from.Truncate(time.Minute).Add(time.Minute)
	maxIterations := 366 * 24 * 60 // Safety limit: ~2 years of minutes

	for i := 0; i < maxIterations; i++ {
		if matchesCronTime(t, min, hour, day, month, weekday) {
			return t, nil
		}
		t = t.Add(time.Minute)
	}

	return time.Time{}, fmt.Errorf("%w: no matching time found within 2 years", ErrInvalidCronExpr)
}

// matchesCronTime checks if a time matches all cron fields
func matchesCronTime(t time.Time, min, hour, day, month, weekday *cronField) bool {
	if !matchesCronField(t.Minute(), min) {
		return false
	}
	if !matchesCronField(t.Hour(), hour) {
		return false
	}
	if !matchesCronField(t.Day(), day) {
		return false
	}
	if !matchesCronField(int(t.Month()), month) {
		return false
	}
	if !matchesCronField(int(t.Weekday()), weekday) {
		return false
	}
	return true
}

// matchesCronField checks if a value matches a parsed cron field
func matchesCronField(value int, field *cronField) bool {
	// If field has explicit values, check them
	if len(field.values) > 0 {
		for _, v := range field.values {
			if v == value {
				return true
			}
		}
		return false
	}

	// If field has ranges, check them
	if len(field.ranges) > 0 {
		for _, r := range field.ranges {
			if value >= r[0] && value <= r[1] {
				// Apply step if present
				if field.hasStep {
					start := r[0]
					if len(field.values) > 0 {
						start = field.values[0]
					}
					if (value-start)%field.step == 0 {
						return true
					}
				}
				return true
			}
		}
		return false
	}

	// Field is * (any value)
	if field.values == nil && len(field.ranges) == 0 {
		if field.hasStep {
			// */X means every X units
			return value%field.step == 0
		}
		return true
	}

	return false
}

// ValidateSchedule validates that a schedule is well-formed.
func ValidateSchedule(s Schedule) error {
	if s.Type == "" {
		return fmt.Errorf("%w: schedule type is required", ErrInvalidSchedule)
	}

	switch s.Type {
	case ScheduleCron:
		if s.Expression == "" {
			return fmt.Errorf("%w: cron expression is required", ErrInvalidSchedule)
		}
		_, err := ParseCron(s.Expression)
		if err != nil {
			return fmt.Errorf("%w: %s", ErrInvalidSchedule, err)
		}
	case ScheduleInterval:
		if s.Expression == "" {
			return fmt.Errorf("%w: interval expression is required", ErrInvalidSchedule)
		}
		_, err := ParseInterval(s.Expression)
		if err != nil {
			return fmt.Errorf("%w: %s", ErrInvalidSchedule, err)
		}
	case ScheduleSpecific:
		// specific_times stores JSON array of timestamps - validation happens at parse time
		if s.Expression == "" {
			return fmt.Errorf("%w: specific times expression is required", ErrInvalidSchedule)
		}
	default:
		return fmt.Errorf("%w: unknown schedule type '%s'", ErrInvalidSchedule, s.Type)
	}

	return nil
}

// RecurringPlanner generates task instances from recurring task templates.
type RecurringPlanner struct {
	scheduler *SchedulerService
	lookAhead time.Duration // How far ahead to generate instances
	interval  time.Duration // How often to check for new instances
	mu        sync.Mutex
	running   bool
	stopCh    chan struct{}
}

// NewRecurringPlanner creates a new RecurringPlanner.
func NewRecurringPlanner(scheduler *SchedulerService, lookAhead, interval time.Duration) *RecurringPlanner {
	return &RecurringPlanner{
		scheduler: scheduler,
		lookAhead: lookAhead,
		interval:  interval,
		stopCh:    make(chan struct{}),
	}
}

// Run starts the recurring planner loop. It runs until Stop is called or the context is cancelled.
func (p *RecurringPlanner) Run(ctx context.Context) {
	p.mu.Lock()
	if p.running {
		p.mu.Unlock()
		return
	}
	p.running = true
	p.mu.Unlock()

	logging.Info("recurring planner started",
		"lookAhead", p.lookAhead.String(),
		"interval", p.interval.String())

	defer func() {
		p.mu.Lock()
		p.running = false
		p.mu.Unlock()
	}()

	ticker := time.NewTicker(p.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			logging.Info("recurring planner stopped: context cancelled")
			return
		case <-p.stopCh:
			logging.Info("recurring planner stopped: stop signal received")
			return
		case <-ticker.C:
			if err := p.generateInstances(ctx); err != nil {
				logging.Error("recurring planner: error generating instances", "error", err)
			}
		}
	}
}

// Stop stops the recurring planner loop gracefully.
func (p *RecurringPlanner) Stop() {
	p.mu.Lock()
	if !p.running {
		p.mu.Unlock()
		return
	}
	p.mu.Unlock()

	select {
	case <-p.stopCh:
		// Already stopped
	default:
		close(p.stopCh)
	}
}

// generateInstances finds recurring tasks and generates future task instances.
func (p *RecurringPlanner) generateInstances(ctx context.Context) error {
	// Find all recurring tasks
	recurringTasks, err := p.scheduler.ListTasks(ctx, TaskFilter{
		Status: []TaskStatus{TaskStatusCreated, TaskStatusDeferred},
		Limit:  100,
	})
	if err != nil {
		return fmt.Errorf("failed to list recurring tasks: %w", err)
	}

	// Filter to only tasks with schedule_expr (actual recurring tasks)
	var recurringTemplates []Task
	for _, task := range recurringTasks {
		if task.Type == TaskTypeRecurring && task.Schedule != nil && task.Schedule.Expression != "" {
			recurringTemplates = append(recurringTemplates, task)
		}
	}

	if len(recurringTemplates) == 0 {
		return nil
	}

	logging.Debug("recurring planner: processing templates", "count", len(recurringTemplates))

	now := time.Now()
	windowEnd := now.Add(p.lookAhead)
	generated := 0

	for _, template := range recurringTemplates {
		// Compute next run times within the look-ahead window
		nextRuns, err := p.computeNextRuns(template.Schedule, now, windowEnd)
		if err != nil {
			logging.Error("recurring planner: failed to compute next runs",
				"task_id", template.ID,
				"error", err)
			continue
		}

		for _, nextRun := range nextRuns {
			// Check idempotency - don't create duplicate instances
			exists, err := p.instanceExists(ctx, template.ID, nextRun)
			if err != nil {
				logging.Error("recurring planner: failed to check instance existence",
					"task_id", template.ID,
					"scheduled_at", nextRun,
					"error", err)
				continue
			}

			if exists {
				logging.Debug("recurring planner: instance already exists, skipping",
					"task_id", template.ID,
					"scheduled_at", nextRun)
				continue
			}

			// Create the new task instance
			instanceID, err := p.createInstance(ctx, template, nextRun)
			if err != nil {
				logging.Error("recurring planner: failed to create instance",
					"task_id", template.ID,
					"scheduled_at", nextRun,
					"error", err)
				continue
			}

			logging.Debug("recurring planner: created instance",
				"template_id", template.ID,
				"instance_id", instanceID,
				"scheduled_at", nextRun)
			generated++
		}
	}

	if generated > 0 {
		logging.Info("recurring planner: generated instances", "count", generated)
	}

	return nil
}

// computeNextRuns computes all next run times for a schedule within the given window.
func (p *RecurringPlanner) computeNextRuns(schedule *Schedule, windowStart, windowEnd time.Time) ([]time.Time, error) {
	if schedule == nil {
		return nil, fmt.Errorf("schedule is nil")
	}

	var runs []time.Time

	switch schedule.Type {
	case ScheduleCron:
		// Use iteration approach to find all cron matches within window
		runs = p.iterateCronMatches(schedule.Expression, windowStart, windowEnd)

	case ScheduleInterval:
		duration, err := ParseInterval(schedule.Expression)
		if err != nil {
			return nil, err
		}
		// Find all intervals within window
		if schedule.StartDate != nil && windowStart.Before(*schedule.StartDate) {
			windowStart = *schedule.StartDate
		}
		// Start from the next interval after windowStart
		elapsed := windowStart.Sub(windowStart.Truncate(duration))
		if elapsed > 0 {
			windowStart = windowStart.Add(duration - elapsed)
		} else {
			windowStart = windowStart.Add(duration - elapsed)
		}

		next := windowStart
		for next.Before(windowEnd) && len(runs) < 100 {
			if !next.Before(windowStart) {
				runs = append(runs, next)
			}
			next = next.Add(duration)
		}

	case ScheduleSpecific:
		// Parse JSON array of timestamps
		var times []time.Time
		if err := json.Unmarshal([]byte(schedule.Expression), &times); err != nil {
			return nil, fmt.Errorf("failed to parse specific times: %w", err)
		}
		for _, t := range times {
			if !t.Before(windowStart) && !t.After(windowEnd) {
				runs = append(runs, t)
			}
		}
	}

	return runs, nil
}

// iterateCronMatches finds all times matching a cron expression within a window.
func (p *RecurringPlanner) iterateCronMatches(expr string, windowStart, windowEnd time.Time) []time.Time {
	var runs []time.Time
	current := windowStart.Truncate(time.Minute).Add(time.Minute)
	maxIterations := int(p.lookAhead / time.Minute)

	for i := 0; i < maxIterations && current.Before(windowEnd); i++ {
		// Check if current matches the cron expression
		if matchesExpressionAtTime(expr, current) {
			runs = append(runs, current)
		}
		current = current.Add(time.Minute)
	}

	return runs
}

// matchesExpressionAtTime checks if a cron expression matches at a specific time.
// This is a helper that parses the expression once and checks a single time.
func matchesExpressionAtTime(expr string, t time.Time) bool {
	fields := strings.Fields(expr)
	if len(fields) != 5 {
		return false
	}

	minuteOK := matchesSingleField(fields[0], t.Minute(), 0, 59)
	hourOK := matchesSingleField(fields[1], t.Hour(), 0, 23)
	dayOK := matchesSingleField(fields[2], t.Day(), 1, 31)
	monthOK := matchesSingleField(fields[3], int(t.Month()), 1, 12)
	weekdayOK := matchesSingleField(fields[4], int(t.Weekday()), 0, 6)

	return minuteOK && hourOK && dayOK && monthOK && weekdayOK
}

// matchesSingleField checks if a cron field matches a value
func matchesSingleField(field string, value, min, max int) bool {
	field = strings.TrimSpace(field)

	// Handle * (any)
	if field == "*" {
		return true
	}

	// Handle */X (step)
	if strings.HasPrefix(field, "*/") {
		stepStr := strings.TrimPrefix(field, "*/")
		step, err := strconv.Atoi(stepStr)
		if err != nil || step <= 0 {
			return false
		}
		return value%step == 0
	}

	// Handle X-Y (range)
	if strings.Contains(field, "-") && !strings.Contains(field, ",") {
		parts := strings.Split(field, "-")
		if len(parts) != 2 {
			return false
		}
		start, err1 := strconv.Atoi(parts[0])
		end, err2 := strconv.Atoi(parts[1])
		if err1 != nil || err2 != nil {
			return false
		}
		return value >= start && value <= end
	}

	// Handle comma-separated values
	if strings.Contains(field, ",") {
		parts := strings.Split(field, ",")
		for _, p := range parts {
			p = strings.TrimSpace(p)
			val, err := strconv.Atoi(p)
			if err != nil {
				continue
			}
			if val == value {
				return true
			}
		}
		return false
	}

	// Handle single value
	val, err := strconv.Atoi(field)
	if err != nil {
		return false
	}
	return val == value
}

// computeNextRun computes the next run time for a schedule from a given time.
func (p *RecurringPlanner) computeNextRun(s Schedule, from time.Time) (time.Time, error) {
	switch s.Type {
	case ScheduleCron:
		return ParseCron(s.Expression)
	case ScheduleInterval:
		duration, err := ParseInterval(s.Expression)
		if err != nil {
			return time.Time{}, err
		}
		// Find next occurrence after 'from'
		truncated := from.Truncate(duration)
		next := truncated.Add(duration)
		if !next.After(from) {
			next = next.Add(duration)
		}
		return next, nil
	case ScheduleSpecific:
		var times []time.Time
		if err := json.Unmarshal([]byte(s.Expression), &times); err != nil {
			return time.Time{}, fmt.Errorf("failed to parse specific times: %w", err)
		}
		for _, t := range times {
			if t.After(from) {
				return t, nil
			}
		}
		return time.Time{}, fmt.Errorf("no future times in schedule")
	default:
		return time.Time{}, fmt.Errorf("%w: unknown schedule type '%s'", ErrInvalidSchedule, s.Type)
	}
}

// instanceExists checks if a task instance already exists for the given parent and scheduled time.
func (p *RecurringPlanner) instanceExists(ctx context.Context, parentID TaskID, scheduledAt time.Time) (bool, error) {
	// For idempotency, we check if a task with the same name prefix and scheduled_at exists
	// The approach: query tasks created from this recurring parent within a small time window
	// Since we store name as-is, we use a name-based approach combined with scheduled_at

	// Query for tasks with similar name pattern and exact scheduled_at
	// We use a unique idempotency key approach: hash of parentID + scheduledAt
	idempotencyKey := generateIdempotencyKey(string(parentID), scheduledAt)

	// For MVP, we do a simpler check: look for a task with the same scheduled_at
	// that was created as a recurring instance (has the parent's name prefix)
	// and was created after the last check

	// Query tasks by scheduled_at range to find potential duplicates
	// This is approximate - a proper solution would add a recurring_parent_id column
	tasks, err := p.scheduler.ListTasks(ctx, TaskFilter{
		ScheduledBefore: &scheduledAt,
		ScheduledAfter:  &scheduledAt,
		Limit:           10,
	})
	if err != nil {
		return false, fmt.Errorf("failed to check instance existence: %w", err)
	}

	// Check if any task has the same idempotency key
	for _, task := range tasks {
		if task.Schedule != nil {
			// Check idempotency key stored in schedule expr
			existingKey := generateIdempotencyKey(string(task.ID), scheduledAt)
			if existingKey == idempotencyKey {
				return true, nil
			}
		}
	}

	// Alternative approach: check by name pattern
	// Look for tasks with name containing the parent task's ID
	tasksByName, err := p.scheduler.ListTasks(ctx, TaskFilter{
		Limit: 100,
	})
	if err != nil {
		return false, fmt.Errorf("failed to list tasks for idempotency check: %w", err)
	}

	for _, task := range tasksByName {
		if task.Type != TaskTypeRecurring && task.ScheduledAt != nil {
			// Check if this is an instance of our recurring task
			taskKey := generateIdempotencyKey(string(parentID), *task.ScheduledAt)
			if taskKey == idempotencyKey {
				return true, nil
			}
		}
	}

	// Use a direct database query approach for more reliable idempotency
	exists, err := p.checkInstanceByQuery(ctx, string(parentID), scheduledAt)
	if err != nil {
		logging.Debug("idempotency check by query failed, using fallback", "error", err)
		return false, nil // Fallback: allow creation
	}

	return exists, nil
}

// checkInstanceByQuery directly checks the database for an existing instance.
func (p *RecurringPlanner) checkInstanceByQuery(ctx context.Context, parentID string, scheduledAt time.Time) (bool, error) {
	// Look for tasks created within 1 minute of the scheduled time
	// that have a name pattern indicating they're from a recurring template
	windowStart := scheduledAt.Add(-time.Minute)
	windowEnd := scheduledAt.Add(time.Minute)

	allTasks, err := p.scheduler.ListTasks(ctx, TaskFilter{
		Limit: 100,
	})
	if err != nil {
		return false, err
	}

	for _, task := range allTasks {
		if task.ScheduledAt == nil {
			continue
		}
		scheduled := *task.ScheduledAt
		// Check if scheduled time is within the window
		if scheduled.After(windowStart) && scheduled.Before(windowEnd) {
			// Verify the task has the same idempotency key
			key := generateIdempotencyKey(parentID, scheduledAt)
			// Check if task's schedule contains our idempotency key
			if task.Schedule != nil && task.Schedule.Expression != "" {
				if strings.Contains(task.Schedule.Expression, key) {
					return true, nil
				}
			}
		}
	}

	return false, nil
}

// generateIdempotencyKey creates a unique key for a recurring task instance.
func generateIdempotencyKey(parentID string, scheduledAt time.Time) string {
	data := fmt.Sprintf("%s:%d", parentID, scheduledAt.Unix())
	hash := md5.Sum([]byte(data))
	return hex.EncodeToString(hash[:])
}

// createInstance creates a new task instance from a recurring template.
func (p *RecurringPlanner) createInstance(ctx context.Context, template Task, scheduledAt time.Time) (TaskID, error) {
	// Create a new task as a copy of the template, but:
	// - New ID
	// - Type is 'scheduled' (not 'recurring')
	// - scheduled_at is set to the computed time
	// - name includes parent ID for idempotency tracking
	// - schedule_expr is NOT copied (the instance is not recurring itself)

	instance := Task{
		ID:          TaskID(uuid.New().String()),
		Name:        fmt.Sprintf("%s (instance of %s)", template.Name, template.ID),
		Description: template.Description,
		Type:        TaskTypeScheduled, // Instances are scheduled, not recurring
		Priority:    template.Priority,
		ScheduledAt: &scheduledAt,
		Agency:      template.Agency,
		Agent:       template.Agent,
		Skills:      template.Skills,
		Params:      template.Params,
		Status:      TaskStatusCreated,
		Progress:    0,
		CreatedAt:   time.Now(),
	}

	// Store idempotency key in schedule expr for later verification
	idempotencyKey := generateIdempotencyKey(string(template.ID), scheduledAt)
	idempotencySchedule := Schedule{
		Type:       ScheduleInterval,
		Expression: "every:1s", // Placeholder
	}
	idempotencyJSON, _ := json.Marshal(map[string]string{
		"idempotency_key": idempotencyKey,
		"parent_task_id":  string(template.ID),
		"scheduled_at":    scheduledAt.Format(time.RFC3339),
	})
	idempotencySchedule.Expression = string(idempotencyJSON)
	instance.Schedule = &idempotencySchedule

	dbParams, err := taskToDB(instance)
	if err != nil {
		return "", fmt.Errorf("failed to convert instance to db params: %w", err)
	}

	createdTask, err := p.scheduler.db.CreateTask(ctx, dbParams)
	if err != nil {
		return "", fmt.Errorf("failed to create task instance: %w", err)
	}

	// Create recurring_scheduled event
	event := TaskEvent{
		TaskID:    TaskID(createdTask.ID),
		Type:      "recurring_scheduled",
		Progress:  0,
		Message:   fmt.Sprintf("Instance of recurring task %s scheduled for %s", template.ID, scheduledAt.Format(time.RFC3339)),
		Timestamp: time.Now(),
	}

	dbEventParams, err := taskEventToDB(event)
	if err != nil {
		logging.Error("failed to convert recurring scheduled event to db params", "error", err)
	} else {
		if _, err := p.scheduler.db.CreateTaskEvent(ctx, dbEventParams); err != nil {
			logging.Error("failed to create recurring_scheduled event", "error", err)
		}
	}

	// Publish event to subscribers
	p.scheduler.eventBroker.Publish(pubsub.CreatedEvent, event)

	return TaskID(createdTask.ID), nil
}
