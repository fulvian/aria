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

    def test_utils_has_setup_logging(self) -> None:
        """Utils module exports setup_logging."""
        from aria.utils import setup_logging

        assert setup_logging is not None

    def test_utils_has_get_logger(self) -> None:
        """Utils module exports get_logger."""
        from aria.utils import get_logger

        assert get_logger is not None
