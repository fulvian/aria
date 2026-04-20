# ARIA Configuration Module
#
# Loads ARIA configuration from environment variables and .env files.
# Follows P1 (isolation) by never touching global KiloCode config.
#
# Environment variables (all prefixed with ARIA_):
#   ARIA_HOME           - ARIA root directory
#   ARIA_RUNTIME        - Runtime state directory
#   ARIA_CREDENTIALS    - Credentials directory
#   ARIA_LOG_LEVEL      - Log level (DEBUG, INFO, WARNING, ERROR)
#   ARIA_TIMEZONE       - Timezone for scheduling
#   ARIA_LOCALE         - Locale for formatting
#   ARIA_QUIET_HOURS    - Quiet hours (no proactive notifications)
#   ARIA_TELEGRAM_WHITELIST - Comma-separated Telegram user IDs
#
# Usage:
#   from aria.config import get_config, ARIAConfig
#   config = get_config()

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import ClassVar

# Default paths - isolated under ARIA_HOME
DEFAULT_ARIA_HOME = Path("/home/fulvio/coding/aria")
DEFAULT_ARIA_RUNTIME = Path("/home/fulvio/coding/aria/.aria/runtime")
DEFAULT_ARIA_CREDENTIALS = Path("/home/fulvio/coding/aria/.aria/credentials")
DEFAULT_KILOCODE_CONFIG_DIR = Path("/home/fulvio/coding/aria/.aria/kilocode")
DEFAULT_KILOCODE_STATE_DIR = Path("/home/fulvio/coding/aria/.aria/kilocode/sessions")

# SOPS default
DEFAULT_SOPS_AGE_KEY_FILE = Path("~/.config/sops/age/keys.txt").expanduser()

# Regex for quiet hours format "HH:MM-HH:MM"
QUIET_HOURS_PATTERN = re.compile(r"^(\d{2}:\d{2})-(\d{2}:\d{2})$")


def _expand_path(value: str | None) -> Path | None:
    """Expand ~ and environment variables in path strings."""
    if value is None:
        return None
    return Path(os.path.expanduser(os.path.expandvars(value))).resolve()


@dataclass
class PathsConfig:
    """Path configuration for ARIA directories."""

    home: Path = DEFAULT_ARIA_HOME
    runtime: Path = DEFAULT_ARIA_RUNTIME
    credentials: Path = DEFAULT_ARIA_CREDENTIALS
    kilocode_config: Path = DEFAULT_KILOCODE_CONFIG_DIR
    kilocode_state: Path = DEFAULT_KILOCODE_STATE_DIR

    @classmethod
    def from_env(cls) -> PathsConfig:
        """Load paths from environment variables."""
        return cls(
            home=_expand_path(os.environ.get("ARIA_HOME")) or DEFAULT_ARIA_HOME,
            runtime=_expand_path(os.environ.get("ARIA_RUNTIME")) or DEFAULT_ARIA_RUNTIME,
            credentials=_expand_path(os.environ.get("ARIA_CREDENTIALS"))
            or DEFAULT_ARIA_CREDENTIALS,
            kilocode_config=_expand_path(os.environ.get("KILOCODE_CONFIG_DIR"))
            or DEFAULT_KILOCODE_CONFIG_DIR,
            kilocode_state=_expand_path(os.environ.get("KILOCODE_STATE_DIR"))
            or DEFAULT_KILOCODE_STATE_DIR,
        )


@dataclass
class OperationalConfig:
    """Operational settings."""

    log_level: str = "INFO"
    timezone: str = "Europe/Rome"
    locale: str = "it_IT.UTF-8"
    quiet_hours_start: str | None = "22:00"
    quiet_hours_end: str | None = "07:00"

    # Valid log levels
    VALID_LOG_LEVELS: ClassVar[set[str]] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    @classmethod
    def from_env(cls) -> OperationalConfig:
        """Load operational config from environment variables."""
        raw_quiet = os.environ.get("ARIA_QUIET_HOURS", "")
        quiet_start, quiet_end = None, None

        if raw_quiet:
            match = QUIET_HOURS_PATTERN.match(raw_quiet)
            if match:
                quiet_start, quiet_end = match.group(1), match.group(2)

        log_level = os.environ.get("ARIA_LOG_LEVEL", "INFO").upper()
        if log_level not in cls.VALID_LOG_LEVELS:
            log_level = "INFO"

        return cls(
            log_level=log_level,
            timezone=os.environ.get("ARIA_TIMEZONE", "Europe/Rome"),
            locale=os.environ.get("ARIA_LOCALE", "it_IT.UTF-8"),
            quiet_hours_start=quiet_start,
            quiet_hours_end=quiet_end,
        )


@dataclass
class SOPSConfig:
    """SOPS encryption configuration."""

    age_key_file: Path = field(default_factory=lambda: DEFAULT_SOPS_AGE_KEY_FILE)

    @classmethod
    def from_env(cls) -> SOPSConfig:
        """Load SOPS config from environment variables."""
        key_file = os.environ.get("SOPS_AGE_KEY_FILE")
        if key_file:
            key_file = os.path.expanduser(key_file)
        return cls(age_key_file=_expand_path(key_file) or DEFAULT_SOPS_AGE_KEY_FILE)


@dataclass
class MemoryConfig:
    """Memory subsystem configuration."""

    t2_enabled: bool = False  # ARIA_MEMORY_T2
    t0_retention_days: int = 365
    t1_compression_after_days: int = 90

    @classmethod
    def from_env(cls) -> MemoryConfig:
        """Load memory config from environment variables."""
        t2_env = os.environ.get("ARIA_MEMORY_T2", "0").lower()
        t2_enabled = t2_env in ("1", "true", "yes", "on")

        t0_retention = int(os.environ.get("ARIA_MEMORY_T0_RETENTION_DAYS", "365"))
        t1_compression = int(os.environ.get("ARIA_MEMORY_T1_COMPRESSION_DAYS", "90"))

        return cls(
            t2_enabled=t2_enabled,
            t0_retention_days=t0_retention,
            t1_compression_after_days=t1_compression,
        )


@dataclass
class TelegramConfig:
    """Telegram gateway configuration."""

    whitelist: list[int] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> TelegramConfig:
        """Load Telegram config from environment variables."""
        raw_whitelist = os.environ.get("ARIA_TELEGRAM_WHITELIST", "")
        user_ids: list[int] = []

        if raw_whitelist:
            # Support both comma-separated and space-separated
            for part in raw_whitelist.replace(",", " ").split():
                if part.strip().isdigit():
                    user_ids.append(int(part.strip()))

        return cls(whitelist=user_ids)


class ConfigurationError(ValueError):
    """Raised when configuration is invalid or incomplete."""


@dataclass
class ARIAConfig:
    """Main ARIA configuration container.

    Collects all configuration namespaces and provides a single access point.

    Per sprint plan §1.2:
    - home: Path (ARIA_HOME)
    - runtime: Path (ARIA_RUNTIME)
    - credentials: Path (ARIA_CREDENTIALS)
    - log_level: str = "INFO"
    - timezone: str = "Europe/Rome"
    - locale: str = "it_IT.UTF-8"
    - quiet_hours: str = "22:00-07:00"
    - memory_t2_enabled: bool = False (ARIA_MEMORY_T2)
    - memory_t0_retention_days: int = 365
    - memory_t1_compression_after_days: int = 90
    - sops_age_key_file: Path (SOPS_AGE_KEY_FILE)
    - telegram_whitelist: list[str] = [] (CSV in env)
    """

    paths: PathsConfig = field(default_factory=PathsConfig.from_env)
    operational: OperationalConfig = field(default_factory=OperationalConfig.from_env)
    sops: SOPSConfig = field(default_factory=SOPSConfig.from_env)
    memory: MemoryConfig = field(default_factory=MemoryConfig.from_env)
    telegram: TelegramConfig = field(default_factory=TelegramConfig.from_env)

    # Version info
    VERSION: ClassVar[str] = "0.1.0"

    @property
    def home(self) -> Path:
        return self.paths.home

    @property
    def runtime(self) -> Path:
        return self.paths.runtime

    @property
    def credentials(self) -> Path:
        return self.paths.credentials

    @property
    def log_level(self) -> str:
        return self.operational.log_level

    @property
    def quiet_hours(self) -> str:
        start = self.operational.quiet_hours_start or "22:00"
        end = self.operational.quiet_hours_end or "07:00"
        return f"{start}-{end}"

    @property
    def memory_t2_enabled(self) -> bool:
        return self.memory.t2_enabled

    @property
    def memory_t0_retention_days(self) -> int:
        return self.memory.t0_retention_days

    @property
    def memory_t1_compression_after_days(self) -> int:
        return self.memory.t1_compression_after_days

    @property
    def sops_age_key_file(self) -> Path:
        return self.sops.age_key_file

    @property
    def telegram_whitelist(self) -> list[str]:
        return [str(user_id) for user_id in self.telegram.whitelist]

    @classmethod
    def from_env(cls) -> ARIAConfig:
        """Load full configuration from environment."""
        return cls(
            paths=PathsConfig.from_env(),
            operational=OperationalConfig.from_env(),
            sops=SOPSConfig.from_env(),
            memory=MemoryConfig.from_env(),
            telegram=TelegramConfig.from_env(),
        )

    @classmethod
    def load(cls) -> ARIAConfig:
        """Thread-safe singleton loader.

        Raises:
            ConfigurationError: if ARIA_HOME does not exist.
        """
        config = get_config()
        if not config.paths.home.exists():
            raise ConfigurationError(f"ARIA_HOME does not exist: {config.paths.home}")
        return config

    def validate(self) -> list[str]:
        """Validate configuration and return list of issues (empty if valid)."""
        issues: list[str] = []

        # Check required paths exist
        if not self.paths.home.exists():
            issues.append(f"ARIA_HOME does not exist: {self.paths.home}")

        # Check SOPS key file
        if not self.sops.age_key_file.exists():
            issues.append(f"SOPS AGE key file not found: {self.sops.age_key_file}")

        # Validate log level
        if self.operational.log_level not in OperationalConfig.VALID_LOG_LEVELS:
            issues.append(f"Invalid ARIA_LOG_LEVEL: {self.operational.log_level}")

        # Validate timezone (basic check)
        if not self.operational.timezone:
            issues.append("ARIA_TIMEZONE is not set")

        return issues

    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        if not self.operational.quiet_hours_start or not self.operational.quiet_hours_end:
            return False

        from datetime import datetime

        now = datetime.now(tz=UTC)
        current_time = now.strftime("%H:%M")

        start = self.operational.quiet_hours_start
        end = self.operational.quiet_hours_end

        # Handle overnight quiet hours (e.g., 22:00-07:00)
        if start <= end:
            return start <= current_time <= end
        else:
            return current_time >= start or current_time <= end


# Global config instance (lazy loaded)
_config_instance: ARIAConfig | None = None
_config_lock = threading.RLock()


def get_config() -> ARIAConfig:
    """Get the global ARIA configuration instance.

    Loads from environment on first call, returns cached instance thereafter.
    """
    global _config_instance  # noqa: PLW0603
    with _config_lock:
        if _config_instance is None:
            _config_instance = ARIAConfig.from_env()
        return _config_instance


def reload_config() -> ARIAConfig:
    """Force reload of configuration from environment."""
    global _config_instance  # noqa: PLW0603
    with _config_lock:
        _config_instance = ARIAConfig.from_env()
        return _config_instance


AriaConfig = ARIAConfig
