"""Logging helpers for Apex Bot."""
from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=level,
        stream=sys.stdout,
    )


def get_logger(name: str = "apex") -> logging.Logger:
    return logging.getLogger(name)
  
