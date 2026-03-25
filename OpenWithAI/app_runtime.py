import logging
from logging.handlers import RotatingFileHandler
import sys
from typing import Optional

from settings import LOG_FILE, ensure_app_dirs

_LOGGER_NAME = "openwithai"


def get_logger() -> logging.Logger:
    ensure_app_dirs()
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    handler = RotatingFileHandler(LOG_FILE, maxBytes=512_000, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def configure_exception_logging() -> logging.Logger:
    logger = get_logger()

    def _handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.exception("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _handle_exception
    return logger


def log_exception(message: str, exc: Optional[BaseException] = None) -> None:
    logger = get_logger()
    if exc is None:
        logger.exception(message)
        return
    logger.exception(message, exc_info=(type(exc), exc, exc.__traceback__))
