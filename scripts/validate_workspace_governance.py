#!/usr/bin/env python3
"""
Validate Google Workspace Tool Governance Matrix per Phase 0 W0.4.

Checks:
1. Governance matrix exists at expected path
2. All required columns present in each row
3. Write tools have hitl_required = yes
4. No rows with missing required fields
5. Policy values are valid (allow/ask/deny)

Usage:
    python scripts/validate_workspace_governance.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

GOVERNANCE_MATRIX = Path(
    "/home/fulvio/coding/aria/docs/roadmaps/workspace_tool_governance_matrix.md"
)

# Required columns per governance matrix schema
REQUIRED_COLUMNS = [
    "tool_name",
    "domain",
    "rw",
    "risk",
    "policy",
    "hitl_required",
    "min_scope",
    "owner",
    "testcase_id",
]

VALID_POLICIES = {"allow", "ask", "deny"}
VALID_RW = {"read", "write"}
VALID_RISK = {"low", "medium", "high", "critical"}


def parse_markdown_tables(content: str) -> list[dict[str, str]]:
    """Parse all markdown tables that match the governance matrix schema.

    Each domain has its own table. Returns all tool rows from all valid tables.
    """
    lines = content.strip().split("\n")
    all_rows = []
    expected_headers = [
        "tool_name",
        "domain",
        "rw",
        "risk",
        "policy",
        "hitl_required",
        "min_scope",
        "owner",
        "testcase_id",
    ]

    # Invalid tool names to skip (summary table rows, headers, etc.)
    skip_names = {
        "tool_name",
        "domain",
        "rw",
        "risk",
        "policy",
        "hitl_required",
        "min_scope",
        "owner",
        "testcase_id",
        "domain",
        "gmail",
        "calendar",
        "drive",
        "docs",
        "sheets",
        "slides",
        "forms",
        "chat",
        "tasks",
        "search",
        "contacts",
        "apps script",
        "**total**",
        "-----------",
        "total tools",
        "denied tools",
    }

    i = 0
    while i < len(lines):
        line = lines[i]

        # Look for table header with tool_name
        if line.strip().startswith("|") and "tool_name" in line.lower():
            header_cells = [h.strip().lower() for h in line.split("|") if h.strip()]

            # Check if this is a governance table (has tool_name as first column)
            if header_cells and header_cells[0] == "tool_name":
                # Skip separator line
                i += 2

                # Parse rows until we hit a non-table line
                while i < len(lines) and lines[i].strip().startswith("|"):
                    row_line = lines[i]
                    cells = [c.strip() for c in row_line.split("|") if c.strip()]

                    # Skip separator lines
                    if cells and not all(c.startswith("-") for c in cells):
                        if len(cells) >= 9:
                            row = {}
                            for j, header in enumerate(expected_headers):
                                if j < len(cells):
                                    row[header] = cells[j]

                            # Only add if tool_name is valid
                            tool_name = row.get("tool_name", "").lower()
                            if (
                                tool_name
                                and tool_name not in skip_names
                                and not tool_name.startswith("-")
                            ):
                                all_rows.append(row)

                    i += 1
                continue
        i += 1

    return all_rows


def validate_row(row: dict[str, str], row_num: int) -> list[str]:
    """Validate a single governance matrix row.

    Returns list of error messages (empty if valid).
    """
    errors = []

    # Check required columns
    missing = [col for col in REQUIRED_COLUMNS if not row.get(col)]
    if missing:
        errors.append(f"Row '{row.get('tool_name', '?')}': missing columns: {missing}")

    # Validate rw
    rw = row.get("rw", "")
    if rw and rw not in VALID_RW:
        errors.append(f"Row '{row['tool_name']}': invalid rw '{rw}' (must be one of {VALID_RW})")

    # Validate policy
    policy = row.get("policy", "")
    if policy and policy not in VALID_POLICIES:
        errors.append(
            f"Row '{row['tool_name']}': invalid policy '{policy}' (must be one of {VALID_POLICIES})"
        )

    # Validate risk
    risk = row.get("risk", "")
    if risk and risk not in VALID_RISK:
        errors.append(
            f"Row '{row['tool_name']}': invalid risk '{risk}' (must be one of {VALID_RISK})"
        )

    # Write tools MUST have hitl_required = yes
    if rw == "write":
        hitl = row.get("hitl_required", "").lower()
        if hitl != "yes":
            errors.append(
                f"Row '{row['tool_name']}': write tool without HITL (hitl_required must be 'yes')"
            )

    # Deny tools MUST NOT have hitl_required = no (deny already blocks)
    if policy == "deny":
        hitl = row.get("hitl_required", "").lower()
        if hitl == "no":
            errors.append(
                f"Row '{row['tool_name']}': deny policy should not have hitl_required='no'"
            )

    return errors


def assert_policy_row(row: dict[str, str]) -> None:
    """Assert a row has all required fields. Raises ValueError if not.

    This is the programmatic check function mentioned in the plan.
    """
    required = [
        "tool_name",
        "rw",
        "risk",
        "policy",
        "hitl_required",
        "min_scope",
        "owner",
        "testcase_id",
    ]
    missing = [k for k in required if not row.get(k)]
    if missing:
        raise ValueError(f"governance row incomplete: {missing}")
    if row["rw"] == "write" and row["hitl_required"].lower() != "yes":
        raise ValueError(f"write tool without HITL: {row['tool_name']}")


def main() -> int:
    """Main validation."""
    errors = []

    # Check file exists
    if not GOVERNANCE_MATRIX.exists():
        print(f"FATAL: Governance matrix not found at {GOVERNANCE_MATRIX}")
        print("Please create docs/roadmaps/workspace_tool_governance_matrix.md first")
        return 1

    # Read and parse
    content = GOVERNANCE_MATRIX.read_text(encoding="utf-8")
    rows = parse_markdown_tables(content)

    if not rows:
        print(f"WARNING: No rows found in governance matrix at {GOVERNANCE_MATRIX}")
        return 0

    print(f"Validating {len(rows)} governance rows...")

    # Validate each row
    all_pass = True
    for i, row in enumerate(rows, 1):
        row_errors = validate_row(row, i)
        if row_errors:
            errors.extend(row_errors)
            all_pass = False

    # Report
    if errors:
        print("Governance validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print(f"Governance validation PASSED ({len(rows)} rows)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
