"""Shared logging setup used across skills."""

import logging
import os
from typing import Optional


def get_agent_data_dir() -> str:
    """Return the agent's data directory from AGENT_DATA_DIR env var, defaulting to /tmp."""
    return os.environ.get('AGENT_DATA_DIR', '/tmp')


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    console_format: str = '%(message)s',
    file_format: str = '%(asctime)s - %(levelname)s - %(message)s',
) -> logging.Logger:
    """Configure a logger with console and optional file output.

    Args:
        name: Logger name (e.g. 'briefs', 'paper-digest').
        log_file: Path to log file. Expanded with os.path.expanduser.
                  Parent directories are created automatically.
        console_level: Logging level for console output.
        file_level: Logging level for file output.
        console_format: Format string for console handler.
        file_format: Format string for file handler.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers = []

    if log_file:
        try:
            expanded = os.path.expanduser(log_file)
            os.makedirs(os.path.dirname(expanded), exist_ok=True)
            fh = logging.FileHandler(expanded)
            fh.setLevel(file_level)
            fh.setFormatter(logging.Formatter(file_format))
            logger.addHandler(fh)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")

    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(logging.Formatter(console_format))
    logger.addHandler(ch)

    return logger
