"""Tests for update checking."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from carrus.core.updater import (
    check_updates,
    compare_versions,
    notify_updates,
)


@pytest.fixture
def mock_download_dir():
    """Create a mock download directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def test_version_comparison():
    """Test semantic version comparison."""
    assert compare_versions("115.0", "114.0") > 0
    assert compare_versions("115.0.1", "115.0.2") < 0
    assert compare_versions("115.0.0", "115.0.0") == 0


def test_update_checking(mock_download_dir):
    """Test update availability checking."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b"115.0.1"
        mock_urlopen.return_value = mock_response

        updates = check_updates([{"name": "Firefox", "version": "115.0.0"}])
        assert len(updates) == 1
        assert updates[0]["new_version"] == "115.0.1"


def test_notification_sending():
    """Test update notification system."""
    with patch("smtplib.SMTP") as mock_smtp:
        notify_updates([{"name": "Firefox", "old_version": "115.0.0", "new_version": "115.0.1"}])
        assert mock_smtp().send_message.call_count == 1


def test_failed_update_check():
    """Test handling of update check failures."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = Exception("Network error")
        updates = check_updates([{"name": "Firefox", "version": "115.0.0"}])
        assert len(updates) == 0  # No updates on error
