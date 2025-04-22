import logging
import os
import sys


def setup_logging():
    LOG_LEVELS = {
        "NOTSET": logging.NOTSET,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()

    if log_level_name not in LOG_LEVELS:
        raise ValueError(f"Invalid log level: {log_level_name}")
    log_level = LOG_LEVELS[log_level_name]

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )
