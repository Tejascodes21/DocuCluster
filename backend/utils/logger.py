"""Centralized logging configuration for DocuCluster."""
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Create and configure a named logger.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        Configured logging.Logger with stream handler and standard format.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
