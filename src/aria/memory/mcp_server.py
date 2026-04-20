from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m aria.memory.mcp_server",
        description="ARIA Memory MCP server (Phase 0 placeholder).",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio",),
        help="Transport layer for MCP server.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate import path and exit without starting the server.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.check:
        return 0
    parser.exit(0, "Phase 0 placeholder: memory MCP runtime is implemented in Phase 1.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
