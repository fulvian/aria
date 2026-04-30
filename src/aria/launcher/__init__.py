# ARIA launcher module
#
# MCP bootstrap and lazy-loading infrastructure per stabilization plan §F3.
#
# Usage:
#   from aria.launcher.lazy_loader import (
#       build_mcp_config,
#       generate_mcp_json,
#       LazyLoaderConfig,
#       Profile,
#       run_with_profile,
#   )

from __future__ import annotations

from aria.launcher.lazy_loader import (
    LazyLoaderConfig,
    Profile,
    build_mcp_config,
    generate_mcp_json,
    run_with_profile,
)

__all__ = [
    "LazyLoaderConfig",
    "Profile",
    "build_mcp_config",
    "generate_mcp_json",
    "run_with_profile",
]
