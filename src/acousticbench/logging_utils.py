"""Logging helpers.

The toolkit uses the standard :mod:`logging` module.  :func:`setup_logging`
is idempotent and safe to call from the CLI, the experiments and the
Streamlit dashboard (which may execute it repeatedly).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Final

DEFAULT_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S"
LOGGER_NAME: Final[str] = "acousticbench"
_CONFIGURED: bool = False


def setup_logging(
    level: str | int = "INFO",
    log_file: str | Path | None = None,
    *,
    force: bool = False,
) -> logging.Logger:
    """Configure the package logger.

    Parameters
    ----------
    level:
        Logging level name or numeric level.
    log_file:
        Optional path to a log file.  Parent directories are created.
    force:
        Re-configure even if logging was already set up.

    Returns
    -------
    logging.Logger
        The configured ``acousticbench`` logger.
    """
    global _CONFIGURED
    logger = logging.getLogger(LOGGER_NAME)
    if _CONFIGURED and not force:
        return logger

    numeric_level = logging.getLevelName(level) if isinstance(level, str) else level
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    logger.setLevel(numeric_level)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler(stream=sys.stderr)
    console.setFormatter(formatter)
    console.setLevel(numeric_level)
    logger.addHandler(console)

    if log_file is not None:
        path = Path(log_file)
        if str(path) not in {"", "."}:
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            file_handler.setLevel(numeric_level)
            logger.addHandler(file_handler)

    _CONFIGURED = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger of the ``acousticbench`` logger."""
    if name is None or name == LOGGER_NAME:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def log_environment(logger: logging.Logger | None = None) -> dict[str, str]:
    """Log and return a small runtime fingerprint (useful for reproducibility)."""
    import platform

    import numpy as np
    import pandas as pd
    import scipy

    logger = logger or get_logger(__name__)
    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "pandas": pd.__version__,
        "pid": str(os.getpid()),
    }
    logger.info(
        "Environment: python=%s numpy=%s scipy=%s pandas=%s platform=%s",
        info["python"],
        info["numpy"],
        info["scipy"],
        info["pandas"],
        info["platform"],
    )
    return info
