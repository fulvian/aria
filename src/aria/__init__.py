# ARIA package
#
# This module contains the core ARIA services:
# - credentials: SOPS+age encrypted credential management
# - memory: 5D memory subsystem (episodic, semantic, procedural)
# - scheduler: task scheduling daemon with budget/policy gates
# - gateway: external channel adapter (Telegram)
# - agents: sub-agent wrappers (search, workspace)
# - tools: Python scripts exposed via MCP
# - utils: logging, metrics, shared utilities
#
# Usage:
#   import aria
#   from aria.credentials import CredentialManager
#   from aria.memory import EpisodicStore

__version__ = "0.1.0"
__author__ = "Fulvio"

from aria import agents, credentials, gateway, memory, scheduler, tools, utils

__all__ = [
    "credentials",
    "memory",
    "scheduler",
    "gateway",
    "agents",
    "tools",
    "utils",
]
