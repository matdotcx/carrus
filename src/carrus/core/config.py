# src/carrus/core/config.py
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class NotificationConfig:
    """Configuration for notifications."""

    enabled: bool = True
    check_interval: int = 24  # Hours
    notify_on_startup: bool = True
    method: str = "cli"  # cli, system, email, github, slack
    email: Optional[str] = None
    github_token: Optional[str] = None
    github_repo: Optional[str] = None
    github_issue_label: str = "update-available"
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    slack_username: str = "Carrus Update Bot"
    last_check: Optional[str] = None


@dataclass
class Config:
    """Configuration data class for carrus."""

    db_path: str
    log_dir: str
    repo_url: Optional[str] = None

    # Using default_factory to avoid mutable default issue
    notifications: NotificationConfig = field(default_factory=NotificationConfig)


def get_config_dir() -> Path:
    """Get the carrus configuration directory."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "~/.config")
    return Path(xdg_config_home).expanduser() / "carrus"


def get_repo_dir() -> Path:
    """Get the repository storage directory."""
    return get_config_dir() / "repos"


def ensure_dirs() -> tuple[Path, Path]:
    """Ensure all required directories exist."""
    config_dir = get_config_dir()
    repo_dir = get_repo_dir()

    config_dir.mkdir(parents=True, exist_ok=True)
    repo_dir.mkdir(parents=True, exist_ok=True)

    return config_dir, repo_dir


def get_default_config() -> Config:
    """Get default configuration with environment variable overrides."""
    db_path = os.environ.get("CARRUS_DB_PATH", str(get_config_dir() / "carrus.db"))
    log_dir = os.environ.get("CARRUS_LOG_DIR", str(get_config_dir() / "logs"))
    repo_url = os.environ.get("CARRUS_REPO_URL")

    # Create the basic config
    config = Config(db_path=db_path, log_dir=log_dir, repo_url=repo_url)

    # Apply notification environment variables if present
    if os.environ.get("CARRUS_NOTIFICATION_ENABLED") is not None:
        config.notifications.enabled = (
            os.environ.get("CARRUS_NOTIFICATION_ENABLED").lower() == "true"
        )

    if os.environ.get("CARRUS_NOTIFICATION_METHOD"):
        config.notifications.method = os.environ.get("CARRUS_NOTIFICATION_METHOD")

    # Email settings
    if os.environ.get("CARRUS_NOTIFICATION_EMAIL"):
        config.notifications.email = os.environ.get("CARRUS_NOTIFICATION_EMAIL")

    # GitHub settings
    if os.environ.get("CARRUS_GITHUB_TOKEN"):
        config.notifications.github_token = os.environ.get("CARRUS_GITHUB_TOKEN")
    if os.environ.get("CARRUS_GITHUB_REPO"):
        config.notifications.github_repo = os.environ.get("CARRUS_GITHUB_REPO")
    if os.environ.get("CARRUS_GITHUB_ISSUE_LABEL"):
        config.notifications.github_issue_label = os.environ.get("CARRUS_GITHUB_ISSUE_LABEL")

    # Slack settings
    if os.environ.get("CARRUS_SLACK_WEBHOOK_URL"):
        config.notifications.slack_webhook_url = os.environ.get("CARRUS_SLACK_WEBHOOK_URL")
    if os.environ.get("CARRUS_SLACK_CHANNEL"):
        config.notifications.slack_channel = os.environ.get("CARRUS_SLACK_CHANNEL")
    if os.environ.get("CARRUS_SLACK_USERNAME"):
        config.notifications.slack_username = os.environ.get("CARRUS_SLACK_USERNAME")

    # Check interval
    if os.environ.get("CARRUS_NOTIFICATION_CHECK_INTERVAL"):
        try:
            config.notifications.check_interval = int(
                os.environ.get("CARRUS_NOTIFICATION_CHECK_INTERVAL")
            )
        except ValueError:
            pass  # Use default if invalid

    return config


def load_config(config_path: Path) -> Config:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)

    return Config(**config_data)


def save_config(config: Config, config_path: Path) -> None:
    """Save configuration to YAML file."""
    notification_dict = {
        "enabled": config.notifications.enabled,
        "check_interval": config.notifications.check_interval,
        "notify_on_startup": config.notifications.notify_on_startup,
        "method": config.notifications.method,
        "email": config.notifications.email,
        "github_token": config.notifications.github_token,
        "github_repo": config.notifications.github_repo,
        "github_issue_label": config.notifications.github_issue_label,
        "slack_webhook_url": config.notifications.slack_webhook_url,
        "slack_channel": config.notifications.slack_channel,
        "slack_username": config.notifications.slack_username,
        "last_check": config.notifications.last_check,
    }

    config_dict = {
        "db_path": config.db_path,
        "log_dir": config.log_dir,
        "repo_url": config.repo_url,
        "notifications": notification_dict,
    }

    with open(config_path, "w") as f:
        yaml.dump(config_dict, f)
