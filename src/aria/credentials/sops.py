# SOPS Adapter for ARIA Credentials
#
# Wrapper around the `sops` CLI for encrypt/decrypt operations on YAML files.
# Per blueprint §13.1 and sprint plan W1.1.C.
#
# Features:
# - Decrypt YAML files via sops --decrypt
# - Encrypt in-place with atomic write (tmp + rename)
# - edit_atomic with flock-based locking (10s timeout)
# - 15s subprocess timeout
# - SopsError with actionable messages
#
# Usage:
#   from aria.credentials.sops import SopsAdapter, SopsError
#
#   adapter = SopsAdapter(age_key_file=Path("~/.config/sops/age/keys.txt"))
#   data = adapter.decrypt(Path(".aria/credentials/secrets/api-keys.enc.yaml"))
#   adapter.edit_atomic(path, lambda d: {**d, "new_key": "value"})

from __future__ import annotations

import fcntl
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from collections.abc import Callable

# === Exceptions ===


class SopsError(Exception):
    """SOPS operation failed with actionable error message."""

    def __init__(
        self, message: str, exit_code: int | None = None, path: Path | None = None
    ) -> None:
        self.exit_code = exit_code
        self.path = path
        super().__init__(message)

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.exit_code is not None:
            parts.append(f"(exit code: {self.exit_code})")
        if self.path:
            parts.append(f"path: {self.path}")
        return " ".join(parts)


# === SOPS Adapter ===


class SopsAdapter:
    """Wrapper for SOPS CLI operations.

    Handles encryption/decryption of YAML files containing credentials.
    All operations are synchronous and use subprocess calls to the sops binary.
    """

    # Subprocess timeout (15s per sprint plan)
    SUBPROCESS_TIMEOUT = 15.0
    LOCK_TIMEOUT_SECONDS = 10.0

    def __init__(self, age_key_file: Path) -> None:
        """Initialize SOPS adapter.

        Args:
            age_key_file: Path to the age private key file (for SOPS_AGE_KEY_FILE env var)
        """
        self.age_key_file = age_key_file.resolve()

    def _sops_env(self) -> dict[str, str]:
        """Build environment for SOPS subprocess."""
        env = os.environ.copy()
        env["SOPS_AGE_KEY_FILE"] = str(self.age_key_file)
        # SOPS sensitive log level - reduce noise
        env["SOPS_LOG_LEVEL"] = "error"
        return env

    def _run_sops(self, args: list[str], path: Path | None = None) -> str:
        """Run sops command and return stdout.

        Args:
            args: SOPS CLI arguments (e.g., ["--decrypt", str(path)])
            path: Optional path for error context

        Returns:
            stdout from sops

        Raises:
            SopsError: on non-zero exit code or timeout
        """
        try:
            result = subprocess.run(
                ["sops"] + args,
                capture_output=True,
                text=True,
                check=True,
                env=self._sops_env(),
                timeout=self.SUBPROCESS_TIMEOUT,
            )
            return result.stdout

        except subprocess.TimeoutExpired as e:
            raise SopsError(
                f"SOPS subprocess timed out after {self.SUBPROCESS_TIMEOUT}s",
                exit_code=None,
                path=path,
            ) from e

        except subprocess.CalledProcessError as e:
            # Parse stderr for actionable messages
            stderr = e.stderr.strip() if e.stderr else ""

            # Map common exit codes to messages
            exit_code = e.returncode
            if exit_code == 128:
                actionable = "Decryption failed: age key file not found or invalid"
            elif exit_code == 129:
                actionable = "No age key found in SOPS_AGE_KEY_FILE or age-agent"
            elif exit_code == 137:
                actionable = "SOPS process killed (timeout or OOM)"
            else:
                actionable = stderr if stderr else f"SOPS exited with code {exit_code}"

            raise SopsError(
                actionable,
                exit_code=exit_code,
                path=path,
            ) from e

    def decrypt(self, path: Path) -> dict[str, Any]:
        """Decrypt a SOPS-encrypted YAML file.

        Args:
            path: Path to .enc.yaml file

        Returns:
            Decrypted data as dictionary

        Raises:
            SopsError: if decryption fails
            FileNotFoundError: if path doesn't exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Encrypted file not found: {path}")

        try:
            stdout = self._run_sops(["--decrypt", str(path)], path=path)
            return yaml.safe_load(stdout) or {}
        except yaml.YAMLError as e:
            raise SopsError(f"Invalid YAML in decrypted file: {e}", path=path) from e

    def encrypt_inplace(self, path: Path, data: dict[str, Any]) -> None:
        """Encrypt data and write in-place to file.

        Uses atomic write: temp file + sops encrypt + rename.
        File permissions set to 0600 after encryption.

        Args:
            path: Path to output .enc.yaml file
            data: Dictionary to encrypt

        Raises:
            SopsError: if encryption fails
        """
        # Create temp file in same directory (for atomic rename)
        dirname = path.parent
        dirname.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            dir=dirname,
            prefix=".sops_tmp_",
            suffix=".yaml",
        )
        os.close(fd)  # Close fd, let sops write to path

        try:
            # Write plaintext YAML to temp file
            with open(tmp_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False)

            # Encrypt in-place with sops
            self._run_sops(["--encrypt", "-i", tmp_path], path=path)

            # Set permissions to 0600
            os.chmod(tmp_path, 0o600)

            # Atomic rename to final path
            os.replace(tmp_path, path)

        except Exception:
            # Clean up temp file on failure
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()
            raise

    def edit_atomic(
        self,
        path: Path,
        mutate_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        """Atomically edit a SOPS-encrypted file.

        Uses flock-based locking with 10s timeout.
        Decrypts file, applies mutation function, encrypts back.

        Args:
            path: Path to .enc.yaml file
            mutate_fn: Function that takes decrypted dict and returns new dict

        Raises:
            SopsError: on lock timeout or encryption failure
        """
        lock_path = Path(str(path) + ".lock")

        try:
            with open(lock_path, "w") as lock_fd:
                # Acquire exclusive lock with timeout
                deadline = time.monotonic() + self.LOCK_TIMEOUT_SECONDS
                while True:
                    try:
                        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise SopsError(
                                f"Timed out acquiring lock on {lock_path} after 10s",
                                path=path,
                            )
                        time.sleep(0.05)
                    except OSError as e:
                        raise SopsError(
                            f"Failed to acquire lock on {lock_path}: {e}",
                            path=path,
                        ) from e

                try:
                    # Decrypt current content
                    data = self.decrypt(path)

                    # Apply mutation
                    new_data = mutate_fn(data)

                    # Encrypt back
                    self.encrypt_inplace(path, new_data)

                finally:
                    # Release lock
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

        finally:
            # Clean up lock file
            if lock_path.exists():
                lock_path.unlink()

    def is_encrypted(self, path: Path) -> bool:
        """Check if a file is SOPS-encrypted.

        Args:
            path: Path to check

        Returns:
            True if file appears to be SOPS-encrypted
        """
        if not path.exists():
            return False

        # SOPS-encrypted files have sops yaml tags at start
        try:
            with open(path, encoding="utf-8") as f:
                first_line = f.readline()
                return "sops:" in first_line or "sops_yaml" in first_line
        except (UnicodeDecodeError, OSError):
            return False


# === CLI Entry Point ===


def main() -> int:  # pragma: no cover - developer utility CLI
    """CLI for SOPS operations (testing/dev only)."""
    import argparse

    parser = argparse.ArgumentParser(description="SOPS adapter CLI")
    parser.add_argument("action", choices=["decrypt", "encrypt", "edit", "is-encrypted"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--data", help="YAML data for encrypt action")

    args = parser.parse_args()

    # Get age key from environment
    age_key_file = Path(
        os.environ.get("SOPS_AGE_KEY_FILE", "~/.config/sops/age/keys.txt")
    ).expanduser()
    adapter = SopsAdapter(age_key_file)

    try:
        if args.action == "decrypt":
            data = adapter.decrypt(args.path)
        elif args.action == "encrypt":
            if not args.data:
                return 1

            data = yaml.safe_load(args.data)
            adapter.encrypt_inplace(args.path, data)
        elif args.action == "is-encrypted":
            adapter.is_encrypted(args.path)
        else:
            return 1
        return 0
    except SopsError:
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
