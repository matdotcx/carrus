"""Tests for the logging system."""

import logging
import tempfile
from pathlib import Path

import pytest

from carrus.core.logging import (
    AUDIT_LOGGER,
    DEBUG_LOGGER,
    get_audit_logger,
    get_debug_logger,
    setup_logging,
)


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def test_setup_logging_console_only():
    """Test logging setup without file output."""
    setup_logging(debug=True)

    audit_logger = logging.getLogger(AUDIT_LOGGER)
    debug_logger = logging.getLogger(DEBUG_LOGGER)

    # Verify logger levels
    assert audit_logger.level == logging.INFO
    assert debug_logger.level == logging.DEBUG

    # Verify console handlers
    assert any(isinstance(h, logging.StreamHandler) for h in debug_logger.handlers)


def test_setup_logging_with_files(temp_log_dir):
    """Test logging setup with file output."""
    setup_logging(log_dir=temp_log_dir, debug=True)

    audit_logger = logging.getLogger(AUDIT_LOGGER)
    debug_logger = logging.getLogger(DEBUG_LOGGER)

    # Verify file handlers
    assert any(isinstance(h, logging.FileHandler) for h in audit_logger.handlers)
    assert any(isinstance(h, logging.FileHandler) for h in debug_logger.handlers)

    # Test logging
    test_msg = "Test log message"
    audit_logger.info(test_msg)
    debug_logger.debug(test_msg)

    # Verify log files
    log_files = list(temp_log_dir.glob("*.log"))
    assert len(log_files) == 2

    # Verify log content
    for log_file in log_files:
        content = log_file.read_text()
        assert test_msg in content


def test_get_loggers():
    """Test logger retrieval functions."""
    setup_logging()

    audit_logger = get_audit_logger()
    debug_logger = get_debug_logger()

    assert isinstance(audit_logger, logging.Logger)
    assert isinstance(debug_logger, logging.Logger)
    assert audit_logger.name == AUDIT_LOGGER
    assert debug_logger.name == DEBUG_LOGGER


def test_audit_logging(temp_log_dir):
    """Test audit logging functionality."""
    setup_logging(log_dir=temp_log_dir)
    audit_logger = get_audit_logger()

    test_messages = [
        "Package verification started",
        "Signature verification passed",
        "Download completed",
    ]

    for msg in test_messages:
        audit_logger.info(msg)

    audit_log = next(temp_log_dir.glob("carrus_audit_*.log"))
    content = audit_log.read_text()

    for msg in test_messages:
        assert msg in content
        assert "[AUDIT]" in content


def test_debug_logging(temp_log_dir):
    """Test debug logging functionality."""
    setup_logging(log_dir=temp_log_dir, debug=True)
    debug_logger = get_debug_logger()

    test_messages = {
        "debug": "Detailed operation info",
        "info": "Operation completed",
        "warning": "Minor issue occurred",
        "error": "Operation failed",
    }

    debug_logger.debug(test_messages["debug"])
    debug_logger.info(test_messages["info"])
    debug_logger.warning(test_messages["warning"])
    debug_logger.error(test_messages["error"])

    debug_log = next(temp_log_dir.glob("carrus_debug_*.log"))
    content = debug_log.read_text()

    for msg in test_messages.values():
        assert msg in content
