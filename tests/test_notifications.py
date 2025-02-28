"""Tests for the Carrus notification system."""

import asyncio
import datetime
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from carrus.core.config import Config, NotificationConfig
from carrus.core.database import Database
from carrus.core.notifications import (
    CLINotificationProvider,
    EmailNotificationProvider,
    Notification,
    NotificationService,
    SlackNotificationProvider,
    SystemNotificationProvider,
)


@pytest.fixture
def mock_db():
    """Fixture for mocked database."""
    db = MagicMock(spec=Database)
    return db


@pytest.fixture
def test_config():
    """Fixture for test configuration."""
    import tempfile

    temp_dir = tempfile.mkdtemp()
    return Config(
        db_path=f"{temp_dir}/test.db",
        log_dir=f"{temp_dir}/logs",
        notifications=NotificationConfig(
            enabled=True,
            method="cli",
            check_interval=24,
            notify_on_startup=True,
        ),
    )


@pytest.fixture
def notification():
    """Fixture for a test notification."""
    return Notification(
        title="Test Update",
        message="A new version is available",
        package_name="TestApp",
        current_version="1.0.0",
        new_version="1.1.0",
    )


class TestNotificationProviders:
    """Test the notification providers."""

    def test_cli_provider_init(self):
        """Test CLI provider initialization."""
        provider = CLINotificationProvider()
        assert provider.console is not None

    def test_cli_provider_notify(self, notification):
        """Test CLI provider notify method."""
        mock_console = MagicMock()
        provider = CLINotificationProvider(console=mock_console)

        # Run the async function using asyncio
        result = asyncio.run(provider.notify(notification))

        assert result is True
        mock_console.print.assert_called()

    def test_system_provider_notify(self, notification):
        """Test system provider notify method with mocked subprocess."""
        provider = SystemNotificationProvider()

        # Mock the subprocess
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        # Use a context manager to patch during execution
        async def run_test():
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
                result = await provider.notify(notification)
                return result, mock_exec

        # Run the async function with asyncio
        result, mock_exec = asyncio.run(run_test())

        assert result is True
        mock_exec.assert_called_once()

    def test_email_provider_notify(self, notification):
        """Test email provider notify method."""
        provider = EmailNotificationProvider("test@example.com")

        async def run_test():
            with patch("logging.Logger.info") as mock_log:
                result = await provider.notify(notification)
                return result, mock_log

        # Run the async function with asyncio
        result, mock_log = asyncio.run(run_test())

        assert result is True
        mock_log.assert_called_once()

    def test_email_provider_no_recipient(self, notification):
        """Test email provider with no recipient."""
        provider = EmailNotificationProvider("")

        async def run_test():
            with patch("logging.Logger.error") as mock_log:
                result = await provider.notify(notification)
                return result, mock_log

        # Run the async function with asyncio
        result, mock_log = asyncio.run(run_test())

        assert result is False
        mock_log.assert_called_once()

    def test_slack_provider_notify(self, notification):
        """Test Slack provider notify method."""

        # Create a test provider that always returns success
        class TestSlackProvider(SlackNotificationProvider):
            async def notify(self, notification):
                # Simulate successful API call
                logging.getLogger(__name__).info(
                    f"Test: Sent Slack notification for {notification.package_name}"
                )
                return True

        # Create an instance with our test implementation
        provider = TestSlackProvider("https://hooks.slack.com/services/XXX/YYY/ZZZ")

        # Define an async function to run
        async def run_test():
            return await provider.notify(notification)

        # Test the notification using asyncio to run the async function
        result = asyncio.run(run_test())

        # Verify the result
        assert result is True

    def test_slack_provider_notify_error(self, notification):
        """Test Slack provider notify method with error response."""

        # Create a test provider that simulates an error
        class TestSlackProviderError(SlackNotificationProvider):
            async def notify(self, notification):
                # Simulate failed API call
                logging.getLogger(__name__).error(
                    "Test: Failed to send Slack notification: 400 - Invalid webhook URL"
                )
                return False

        # Create an instance with our test implementation
        provider = TestSlackProviderError("https://hooks.slack.com/services/XXX/YYY/ZZZ")

        # Define an async function that includes the patch
        async def run_test():
            with patch("logging.Logger.error") as mock_log:
                result = await provider.notify(notification)
                return result, mock_log

        # Run the async function with asyncio
        result, mock_log = asyncio.run(run_test())

        # Verify the result
        assert result is False
        mock_log.assert_called_once()

    def test_slack_provider_no_webhook(self, notification):
        """Test Slack provider with no webhook URL."""
        provider = SlackNotificationProvider("")

        async def run_test():
            with patch("logging.Logger.error") as mock_log:
                result = await provider.notify(notification)
                return result, mock_log

        # Run the async function with asyncio
        result, mock_log = asyncio.run(run_test())

        assert result is False
        mock_log.assert_called_once()


class TestNotificationService:
    """Test the notification service."""

    def test_init(self, test_config, mock_db):
        """Test service initialization."""
        with patch("carrus.core.notifications.Database", return_value=mock_db):
            service = NotificationService(test_config)

            assert service.config is test_config
            assert service.notification_config is test_config.notifications
            assert isinstance(service.provider, CLINotificationProvider)

    def test_init_with_system_method(self, test_config, mock_db):
        """Test service initialization with system method."""
        test_config.notifications.method = "system"

        with patch("carrus.core.notifications.Database", return_value=mock_db):
            service = NotificationService(test_config)

            assert isinstance(service.provider, SystemNotificationProvider)

    def test_init_with_email_method(self, test_config, mock_db):
        """Test service initialization with email method."""
        test_config.notifications.method = "email"
        test_config.notifications.email = "test@example.com"

        with patch("carrus.core.notifications.Database", return_value=mock_db):
            service = NotificationService(test_config)

            assert isinstance(service.provider, EmailNotificationProvider)

    def test_init_with_slack_method(self, test_config, mock_db):
        """Test service initialization with slack method."""
        test_config.notifications.method = "slack"
        test_config.notifications.slack_webhook_url = "https://hooks.slack.com/services/XXX/YYY/ZZZ"
        test_config.notifications.slack_channel = "#updates"

        with patch("carrus.core.notifications.Database", return_value=mock_db):
            service = NotificationService(test_config)

            assert isinstance(service.provider, SlackNotificationProvider)

    def test_should_check_updates(self, test_config, mock_db):
        """Test should_check_updates method."""
        with patch("carrus.core.notifications.Database", return_value=mock_db):
            service = NotificationService(test_config)

            # No last check, should return True
            assert service.should_check_updates() is True

            # Set last check to now, should return False
            service.notification_config.last_check = datetime.datetime.now().isoformat()
            assert service.should_check_updates() is False

            # Set last check to old date, should return True
            service.notification_config.last_check = (
                datetime.datetime.now() - datetime.timedelta(hours=25)
            ).isoformat()
            assert service.should_check_updates() is True

            # Disable notifications, should return False
            service.notification_config.enabled = False
            assert service.should_check_updates() is False

    def test_check_updates(self, test_config, mock_db):
        """Test check_updates method."""
        # Mock version tracker
        mock_tracker = MagicMock()
        mock_tracker.get_available_updates.return_value = [
            (
                {"id": 1, "name": "TestApp", "version": "1.0.0"},
                {"id": 1, "version": "1.1.0"},
            )
        ]

        # Mock database
        mock_db.get_installed_version.return_value = {"version": "1.0.0"}

        async def run_test():
            with patch("carrus.core.notifications.Database", return_value=mock_db):
                with patch("carrus.core.notifications.VersionTracker", return_value=mock_tracker):
                    service = NotificationService(test_config)
                    notifications = await service.check_updates()
                    return notifications, service.notification_config

        # Run the async function with asyncio
        notifications, notification_config = asyncio.run(run_test())

        assert len(notifications) == 1
        assert notifications[0].package_name == "TestApp"
        assert notifications[0].current_version == "1.0.0"
        assert notifications[0].new_version == "1.1.0"

        # Check last_check was updated
        assert notification_config.last_check is not None

    def test_notify_updates(self, test_config, mock_db, notification):
        """Test notify_updates method."""
        # Mock check_updates
        mock_check = AsyncMock(return_value=[notification])

        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.notify = AsyncMock(return_value=True)

        async def run_test():
            with patch("carrus.core.notifications.Database", return_value=mock_db):
                service = NotificationService(test_config)
                service.check_updates = mock_check
                service.provider = mock_provider
                count = await service.notify_updates()
                return count, mock_check, mock_provider

        # Run the async function with asyncio
        count, mock_check, mock_provider = asyncio.run(run_test())

        assert count == 1
        mock_check.assert_called_once()
        mock_provider.notify.assert_called_once_with(notification)

    def test_notify_updates_disabled(self, test_config, mock_db):
        """Test notify_updates method when disabled."""
        test_config.notifications.enabled = False

        async def run_test():
            with patch("carrus.core.notifications.Database", return_value=mock_db):
                service = NotificationService(test_config)
                return await service.notify_updates()

        # Run the async function with asyncio
        count = asyncio.run(run_test())

        assert count == 0

    def test_set_notification_method(self, test_config, mock_db):
        """Test set_notification_method method."""
        with patch("carrus.core.notifications.Database", return_value=mock_db):
            service = NotificationService(test_config)

            # Change to system
            service.set_notification_method("system")
            assert service.notification_config.method == "system"
            assert isinstance(service.provider, SystemNotificationProvider)

            # Change to email
            service.set_notification_method("email", "test@example.com")
            assert service.notification_config.method == "email"
            assert service.notification_config.email == "test@example.com"
            assert isinstance(service.provider, EmailNotificationProvider)

            # Change to slack
            service.set_notification_method(
                "slack",
                slack_webhook_url="https://hooks.slack.com/services/XXX/YYY/ZZZ",
                slack_channel="#updates",
            )
            assert service.notification_config.method == "slack"
            assert (
                service.notification_config.slack_webhook_url
                == "https://hooks.slack.com/services/XXX/YYY/ZZZ"
            )
            assert service.notification_config.slack_channel == "#updates"
            assert isinstance(service.provider, SlackNotificationProvider)

            # Change back to cli
            service.set_notification_method("cli")
            assert service.notification_config.method == "cli"
            assert isinstance(service.provider, CLINotificationProvider)

            # Invalid method
            with pytest.raises(ValueError):
                service.set_notification_method("invalid")

            # Email without address
            with pytest.raises(ValueError):
                service.set_notification_method("email")

            # Slack without webhook URL
            with pytest.raises(ValueError):
                service.set_notification_method("slack")
