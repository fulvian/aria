#!/usr/bin/env python3
"""Compatibility entrypoint for the MCP drift audit."""

import sys

from scripts.audit_drift import main

if __name__ == "__main__":
    sys.exit(main())
