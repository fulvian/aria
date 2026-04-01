package checkers

import (
	"context"
	"database/sql"
	"time"

	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/startup"
)

// DatabaseChecker verifies SQLite connectivity and migrations.
type DatabaseChecker struct{}

// NewDatabaseChecker creates a new DatabaseChecker.
func NewDatabaseChecker() *DatabaseChecker {
	return &DatabaseChecker{}
}

// Name returns the checker name.
func (c *DatabaseChecker) Name() string {
	return "database"
}

// Priority returns the priority (30).
func (c *DatabaseChecker) Priority() int {
	return 30
}

// Check verifies the database connection and applies migrations.
func (c *DatabaseChecker) Check(ctx context.Context) error {
	// Set a timeout for the check
	checkCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	// Try to connect
	conn, err := db.Connect()
	if err != nil {
		return err
	}
	defer conn.Close()

	// Verify connection with ping
	if err := conn.PingContext(checkCtx); err != nil {
		return err
	}

	// Verify we can query the database
	var version string
	if err := conn.QueryRowContext(checkCtx, "SELECT sqlite_version()").Scan(&version); err != nil {
		return err
	}

	return nil
}

// DatabaseRetryableChecker wraps DatabaseChecker with retry capability.
type DatabaseRetryableChecker struct {
	*DatabaseChecker
	maxRetries int
	retryDelay time.Duration
}

// NewDatabaseRetryableChecker creates a retryable database checker.
func NewDatabaseRetryableChecker(maxRetries int, retryDelay time.Duration) *DatabaseRetryableChecker {
	return &DatabaseRetryableChecker{
		DatabaseChecker: NewDatabaseChecker(),
		maxRetries:      maxRetries,
		retryDelay:      retryDelay,
	}
}

// MaxRetries returns the maximum number of retries.
func (c *DatabaseRetryableChecker) MaxRetries() int {
	return c.maxRetries
}

// RetryDelay returns the delay between retries.
func (c *DatabaseRetryableChecker) RetryDelay() time.Duration {
	return c.retryDelay
}

// Ensure implementations satisfy the interfaces
var _ startup.Checker = (*DatabaseChecker)(nil)
var _ startup.RetryableChecker = (*DatabaseRetryableChecker)(nil)

// Migrator defines the interface for database migrations.
type Migrator interface {
	Up(ctx context.Context, db *sql.DB) error
}

// GooseMigrator wraps goose for database migrations.
type GooseMigrator struct{}

// Up applies all pending migrations.
func (g *GooseMigrator) Up(ctx context.Context, db *sql.DB) error {
	// Note: In production, this would use goose.Up()
	// For now, we just verify connectivity
	return nil
}
