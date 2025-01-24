"""Logging configuration for carrus."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Constants
AUDIT_LOGGER = "carrus.audit"
DEBUG_LOGGER = "carrus.debug"


def setup_logging(log_dir: Optional[Path] = None, debug: bool = False) -> None:
    """Configure logging for carrus.

    Args:
        log_dir: Directory to store log files. If None, logs to stderr only.
        debug: Whether to enable debug logging.
    """
    # Create formatters
    audit_formatter = logging.Formatter("%(asctime)s - %(levelname)s - [AUDIT] %(message)s")
    debug_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    # Setup audit logger
    audit_logger = logging.getLogger(AUDIT_LOGGER)
    audit_logger.setLevel(logging.INFO)

    # Setup debug logger
    debug_logger = logging.getLogger(DEBUG_LOGGER)
    debug_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Console handlers
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(debug_formatter)
    debug_logger.addHandler(console_handler)

    if log_dir:
        # Create log directory
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # File handlers
        audit_file = log_dir / f"carrus_audit_{datetime.now():%Y%m%d}.log"
        audit_handler = logging.FileHandler(audit_file)
        audit_handler.setFormatter(audit_formatter)
        audit_logger.addHandler(audit_handler)

        if debug:
            debug_file = log_dir / f"carrus_debug_{datetime.now():%Y%m%d}.log"
            debug_handler = logging.FileHandler(debug_file)
            debug_handler.setFormatter(debug_formatter)
            debug_logger.addHandler(debug_handler)


def get_audit_logger() -> logging.Logger:
    """Get the audit logger."""
    return logging.getLogger(AUDIT_LOGGER)


def get_debug_logger() -> logging.Logger:
    """Get the debug logger."""
    return logging.getLogger(DEBUG_LOGGER)
