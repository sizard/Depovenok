from __future__ import annotations

import sys
from loguru import logger


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stdout, level=level, backtrace=False, diagnose=False, enqueue=False,
               format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")


__all__ = ["logger", "setup_logging"]
