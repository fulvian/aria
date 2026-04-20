from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m aria.gateway.daemon",
        description="ARIA Gateway daemon (Phase 0 placeholder).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate CLI wiring and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.check:
        return 0
    parser.exit(0, "Phase 0 placeholder: gateway runtime is implemented in Phase 1.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
