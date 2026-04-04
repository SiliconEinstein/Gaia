"""Unified logging configuration for LKM."""

from __future__ import annotations

import logging
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(
    level: str = "INFO",
    log_file: Path | None = None,
) -> None:
    """Configure logging for all gaia.lkm.* loggers.

    Call once at process startup (CLI entry point or API lifespan).
    Console handler is always added; file handler is added if log_file is set.
    """
    root_logger = logging.getLogger("gaia.lkm")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers to allow reconfiguration
    root_logger.handlers.clear()

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        root_logger.addHandler(fh)
