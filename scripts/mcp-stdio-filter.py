#!/usr/bin/env python3
"""MCP stdio filter — bidirectional relay + non-JSON stdout suppression.

Filters out startup noise from MCP servers that print non-JSON text to stdout
before starting the MCP protocol. Only JSONRPC messages are passed to stdout;
everything else goes to stderr.

This is a full bidirectional relay: stdin is passed through to the child,
and the child's stdout is filtered.

Usage:
    uv run python scripts/mcp-stdio-filter.py -- <server-command> [args...]

Use in wrapper scripts (bash):
    exec uv run /path/to/mcp-stdio-filter.py -- real-server --arg1 --arg2
"""
import json
import subprocess
import sys
import threading


def main() -> None:
    if "--" not in sys.argv:
        print(f"Usage: {sys.argv[0]} -- <command> [args...]", file=sys.stderr)
        sys.exit(1)

    idx = sys.argv.index("--")
    cmd = sys.argv[idx + 1:]

    if not cmd:
        print("No command specified.", file=sys.stderr)
        sys.exit(1)

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    # Thread: relay stdin to child process
    def relay_stdin() -> None:
        assert proc.stdin is not None
        try:
            for line in sys.stdin:
                proc.stdin.write(line)
                proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass

    threading.Thread(target=relay_stdin, daemon=True).start()

    # Thread: filter child stdout — only JSONRPC lines
    def filter_stdout() -> None:
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                stripped = line.strip()
                if stripped:
                    try:
                        obj = json.loads(stripped)
                        if isinstance(obj, dict) and "jsonrpc" in obj:
                            sys.stdout.write(line)
                            sys.stdout.flush()
                            continue
                    except (json.JSONDecodeError, ValueError):
                        pass
                sys.stderr.write(f"[mcp-filter] {line}")
                sys.stderr.flush()
        except (BrokenPipeError, OSError):
            pass

    threading.Thread(target=filter_stdout, daemon=True).start()

    # Thread: relay child stderr
    def relay_stderr() -> None:
        assert proc.stderr is not None
        try:
            for line in proc.stderr:
                sys.stderr.write(line)
                sys.stderr.flush()
        except OSError:
            pass

    threading.Thread(target=relay_stderr, daemon=True).start()

    proc.wait()
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
