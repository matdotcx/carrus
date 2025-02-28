# src/carrus/core/notifications.py

import asyncio
import datetime
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional

from rich.console import Console

from carrus.core.config import Config
from carrus.core.database import Database
from carrus.core.updater import VersionTracker

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    """Notification data class."""

    title: str
    message: str
    package_name: str
    current_version: str
    new_version: str
    timestamp: datetime.datetime = datetime.datetime.now()


class NotificationProvider(ABC):
    """Base class for notification providers."""

    @abstractmethod
    async def notify(self, notification: Notification) -> bool:
        """Send a notification."""
        pass


class CLINotificationProvider(NotificationProvider):
    """CLI-based notification provider."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    async def notify(self, notification: Notification) -> bool:
        """Display notification in CLI."""
        try:
            self.console.print(f"\n[bold yellow]{notification.title}[/bold yellow]")
            self.console.print(f"{notification.message}")
            self.console.print(
                f"Package: [cyan]{notification.package_name}[/cyan] "
                f"([green]{notification.current_version}[/green] → "
                f"[yellow]{notification.new_version}[/yellow])"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send CLI notification: {e}")
            return False


class SystemNotificationProvider(NotificationProvider):
    """System notification provider using platform-specific methods."""

    async def notify(self, notification: Notification) -> bool:
        """Send a system notification."""
        try:
            # On macOS, use osascript
            cmd = [
                "osascript",
                "-e",
                f'display notification "{notification.message}" with title "{notification.title}"',
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"System notification failed: {stderr.decode()}")
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to send system notification: {e}")
            return False


class EmailNotificationProvider(NotificationProvider):
    """Email notification provider."""

    def __init__(self, recipient_email: str):
        self.recipient_email = recipient_email

    async def notify(self, notification: Notification) -> bool:
        """Send an email notification."""
        if not self.recipient_email:
            logger.error("No recipient email provided for email notification")
            return False

        try:
            # Create email message
            msg = EmailMessage()
            msg["Subject"] = notification.title
            msg["From"] = "carrus-updater@noreply.local"
            msg["To"] = self.recipient_email

            body = f"""
            {notification.message}
            
            Package: {notification.package_name}
            Current Version: {notification.current_version}
            New Version: {notification.new_version}
            
            Timestamp: {notification.timestamp.isoformat()}
            """

            msg.set_content(body)

            # In a real implementation, you would configure SMTP settings
            # For now, we'll just log the message
            logger.info(f"Would send email to {self.recipient_email}: {msg}")

            # Placeholder for actual email sending
            # with smtplib.SMTP('localhost') as server:
            #     server.send_message(msg)

            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False


class NotificationService:
    """Service for managing notifications."""

    def __init__(self, config: Config, db_path: Optional[Path] = None):
        """Initialize the notification service."""
        self.config = config
        self.notification_config = config.notifications
        self.db = Database(Path(db_path or config.db_path))
        self.version_tracker = VersionTracker(self.db)

        # Set up the notification provider based on configuration
        if self.notification_config.method == "system":
            self.provider = SystemNotificationProvider()
        elif self.notification_config.method == "email" and self.notification_config.email:
            self.provider = EmailNotificationProvider(self.notification_config.email)
        else:
            self.provider = CLINotificationProvider()

    async def check_updates(self) -> List[Notification]:
        """Check for updates and return notifications for available updates."""
        notifications = []

        # Get all available updates
        available_updates = self.version_tracker.get_available_updates()

        for package, latest_version in available_updates:
            # Get installed version
            installed_version = self.db.get_installed_version(package["id"])

            if not installed_version:
                continue

            notification = Notification(
                title="Update Available",
                message=f"A new version of {package['name']} is available.",
                package_name=package["name"],
                current_version=installed_version["version"],
                new_version=latest_version["version"],
            )

            notifications.append(notification)

        # Update the last check time
        self.notification_config.last_check = datetime.datetime.now().isoformat()

        return notifications

    async def notify_updates(self) -> int:
        """Check for updates and send notifications. Returns number of notifications sent."""
        if not self.notification_config.enabled:
            logger.info("Notifications are disabled")
            return 0

        notifications = await self.check_updates()

        # Send notifications
        sent_count = 0
        for notification in notifications:
            if await self.provider.notify(notification):
                sent_count += 1

        return sent_count

    def should_check_updates(self) -> bool:
        """Determine if updates should be checked based on last check time."""
        if not self.notification_config.enabled:
            return False

        if not self.notification_config.last_check:
            return True

        try:
            last_check = datetime.datetime.fromisoformat(self.notification_config.last_check)
            interval = datetime.timedelta(hours=self.notification_config.check_interval)

            return datetime.datetime.now() - last_check > interval
        except (ValueError, TypeError):
            return True

    def set_notification_method(self, method: str, email: Optional[str] = None) -> None:
        """Set the notification method."""
        if method not in ["cli", "system", "email"]:
            raise ValueError(f"Invalid notification method: {method}")

        self.notification_config.method = method

        if method == "email":
            if not email:
                raise ValueError("Email address required for email notifications")
            self.notification_config.email = email
            self.provider = EmailNotificationProvider(email)
        elif method == "system":
            self.provider = SystemNotificationProvider()
        else:
            self.provider = CLINotificationProvider()
