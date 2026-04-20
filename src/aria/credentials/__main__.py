from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m aria.credentials",
        description="ARIA credentials CLI (Phase 0 placeholder).",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=("status", "reload", "rotate"),
        help="Credentials operation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    parser.exit(
        0, f"Phase 0 placeholder: credentials command '{args.command}' is not active yet.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
