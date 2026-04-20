# Unit tests for ARIA package
# Phase 0: basic skeleton tests


class TestAriaPackage:
    """Test ARIA package basic structure."""

    def test_version_exists(self) -> None:
        """ARIA package has a version."""
        import aria

        assert hasattr(aria, "__version__")
        assert aria.__version__ is not None

    def test_submodules_available(self) -> None:
        """Core submodules are importable."""
        from aria import agents, credentials, gateway, memory, scheduler, tools, utils

        assert agents is not None
        assert credentials is not None
        assert gateway is not None
        assert memory is not None
        assert scheduler is not None
        assert tools is not None
        assert utils is not None

    def test_credentials_module_has_manager(self) -> None:
        """Credentials module exports CredentialManager."""
        from aria.credentials import CredentialManager

        assert CredentialManager is not None

    def test_memory_module_has_episodic_store(self) -> None:
        """Memory module exports EpisodicStore."""
        from aria.memory import EpisodicStore

        assert EpisodicStore is not None

    def test_scheduler_module_has_daemon(self) -> None:
        """Scheduler module exports SchedulerDaemon."""
        from aria.scheduler import SchedulerDaemon

        assert SchedulerDaemon is not None

    def test_gateway_module_has_daemon(self) -> None:
        """Gateway module exports GatewayDaemon."""
        from aria.gateway import GatewayDaemon

        assert GatewayDaemon is not None


class TestUtilsModule:
    """Test utils module."""

    def test_utils_has_get_logger(self) -> None:
        """Utils module exports get_logger."""
        from aria.utils import get_logger

        assert get_logger is not None

    def test_utils_has_redact_secret(self) -> None:
        """Utils module exports redact_secret."""
        from aria.utils import redact_secret

        assert redact_secret is not None
        assert redact_secret(None) == "<none>"
        assert redact_secret("sk-abc1234567") == "***4567"

    def test_utils_has_trace_functions(self) -> None:
        """Utils module exports trace ID functions."""
        from aria.utils import get_trace_id, new_trace_id, set_trace_id

        assert new_trace_id is not None
        assert set_trace_id is not None
        assert get_trace_id is not None
