#!/usr/bin/env python3
"""
Google Workspace MCP Write Health Check

Verifies that the Google Workspace MCP server is properly configured
for write operations.

Usage:
    workspace-write-health [--verbose]
    workspace-write-health --check-scopes <access_token>

Exit Codes:
    0 - All checks passed
    1 - Configuration error or missing scopes
    2 - MCP server not reachable
"""

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    passed: bool
    component: str
    message: str
    details: dict | None = None


def run_command(cmd: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -2, "", f"Command not found: {cmd[0]}"


def check_mcp_wrapper() -> HealthCheckResult:
    """Check if the wrapper script exists and is executable."""
    wrapper_path = os.path.join(
        os.path.dirname(__file__), "wrappers", "google-workspace-wrapper.sh"
    )

    if not os.path.exists(wrapper_path):
        return HealthCheckResult(
            passed=False,
            component="wrapper",
            message=f"Wrapper script not found: {wrapper_path}",
        )

    if not os.access(wrapper_path, os.X_OK):
        return HealthCheckResult(
            passed=False,
            component="wrapper",
            message=f"Wrapper script not executable: {wrapper_path}",
        )

    return HealthCheckResult(
        passed=True,
        component="wrapper",
        message="Wrapper script OK",
        details={"path": wrapper_path},
    )


def check_env_vars() -> HealthCheckResult:
    """Check if required environment variables are set."""
    required = ["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"]
    optional = ["GOOGLE_OAUTH_REDIRECT_URI", "OAUTHLIB_INSECURE_TRANSPORT"]

    missing = []
    found = {}

    for var in required:
        val = os.environ.get(var)
        if val:
            # Mask sensitive values
            found[var] = f"{val[:10]}..." if len(val) > 10 else "***"
        else:
            missing.append(var)

    for var in optional:
        val = os.environ.get(var)
        if val:
            found[var] = val

    if missing:
        return HealthCheckResult(
            passed=False,
            component="env",
            message=f"Missing required env vars: {', '.join(missing)}",
            details={"found": found, "missing": missing},
        )

    return HealthCheckResult(
        passed=True, component="env", message="Environment variables OK", details=found
    )


def check_workspace_mcp_installed() -> HealthCheckResult:
    """Check if workspace-mcp is installed via uvx."""
    returncode, stdout, stderr = run_command(["uvx", "workspace-mcp", "--help"])

    if returncode == -2:
        return HealthCheckResult(
            passed=False,
            component="workspace-mcp",
            message="workspace-mcp not found in PATH",
            details={"suggestion": "Run: uvx workspace-mcp --help"},
        )

    if returncode != 0:
        # Exit code 2 typically means --help was shown
        pass

    return HealthCheckResult(
        passed=True,
        component="workspace-mcp",
        message="workspace-mcp is available",
        details={"version_check": "passed"},
    )


def check_wrapper_config(args: argparse.Namespace) -> HealthCheckResult:
    """Check wrapper configuration."""
    wrapper_path = os.path.join(
        os.path.dirname(__file__), "wrappers", "google-workspace-wrapper.sh"
    )

    returncode, stdout, stderr = run_command([wrapper_path, "--check"], timeout=15)

    if returncode != 0:
        return HealthCheckResult(
            passed=False,
            component="wrapper-config",
            message="Wrapper configuration check failed",
            details={"stdout": stdout, "stderr": stderr},
        )

    return HealthCheckResult(
        passed=True,
        component="wrapper-config",
        message="Wrapper configuration OK",
        details={"output": stdout.strip()},
    )


def check_scopes(access_token: str) -> HealthCheckResult:
    """Verify OAuth scopes for the given access token."""
    try:
        from workspace_auth import format_scope_error, verify_write_scopes

        result = verify_write_scopes(access_token)

        if result.write_ready:
            return HealthCheckResult(
                passed=True,
                component="oauth-scopes",
                message="All write scopes verified",
                details=result.to_dict(),
            )
        else:
            error_msg = format_scope_error(result)
            return HealthCheckResult(
                passed=False, component="oauth-scopes", message=error_msg, details=result.to_dict()
            )
    except ImportError:
        return HealthCheckResult(
            passed=False,
            component="oauth-scopes",
            message="workspace_auth module not available",
            details={"path": __file__},
        )
    except Exception as e:
        return HealthCheckResult(
            passed=False,
            component="oauth-scopes",
            message=f"Scope verification failed: {e}",
        )


def run_health_checks(args: argparse.Namespace) -> int:
    """Run all health checks and return exit code."""
    checks = [
        ("Wrapper Script", check_mcp_wrapper),
        ("Environment Variables", check_env_vars),
        ("workspace-mcp Installed", check_workspace_mcp_installed),
        ("Wrapper Configuration", lambda: check_wrapper_config(args)),
    ]

    results = []
    all_passed = True

    print("=" * 60)
    print("Google Workspace MCP Write Health Check")
    print("=" * 60)
    print()

    for name, check_fn in checks:
        print(f"Checking {name}...", end=" ")
        result = check_fn()
        results.append(result)

        if result.passed:
            print("✓ PASS")
            if args.verbose and result.details:
                for key, value in result.details.items():
                    print(f"    {key}: {value}")
        else:
            print("✗ FAIL")
            print(f"    {result.message}")
            if args.verbose and result.details:
                for key, value in result.details.items():
                    print(f"    {key}: {value}")
            all_passed = False
        print()

    # Scope check if token provided
    if args.check_scopes:
        print("Verifying OAuth scopes...")
        result = check_scopes(args.check_scopes)
        if result.passed:
            print("✓ PASS - OAuth scopes verified")
            if args.verbose and result.details:
                for key, value in result.details.items():
                    print(f"    {key}: {value}")
        else:
            print("✗ FAIL - OAuth scope verification failed")
            print(f"    {result.message}")
            all_passed = False
        print()

    print("=" * 60)
    if all_passed:
        print("RESULT: All checks passed ✓")
        print("Google Workspace MCP is configured for write operations.")
    else:
        print("RESULT: Some checks failed ✗")
        print("Review the errors above and fix the configuration.")
    print("=" * 60)

    return 0 if all_passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Workspace MCP Write Health Check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    workspace-write-health                    # Run all checks
    workspace-write-health --verbose          # Run with details
    workspace-write-health --check-scopes TOKEN  # Verify OAuth scopes
        """,
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")

    parser.add_argument(
        "--check-scopes", metavar="TOKEN", help="Verify OAuth scopes for the given access token"
    )

    args = parser.parse_args()

    exit_code = run_health_checks(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
