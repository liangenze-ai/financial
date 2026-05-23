import sys
from pathlib import Path

from loguru import logger


LOG_DIR = Path(__file__).resolve().parent.parent / 'logs'
LOG_FORMAT = (
    '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | '
    '<level>{level: <8}</level> | '
    '{file.path}:{function}:{line} | '
    '<level>{message}</level>'
)

_LOGGING_CONFIGURED = False


def setup_logging():
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        sys.stdout,
        level='INFO',
        format=LOG_FORMAT,
        enqueue=True,
        backtrace=True,
        diagnose=False,
        colorize=True,
    )
    logger.add(
        LOG_DIR / 'finance-backend-{time:YYYY-MM-DD}.log',
        level='DEBUG',
        format=LOG_FORMAT,
        encoding='utf-8',
        enqueue=True,
        backtrace=True,
        diagnose=False,
        rotation='20 MB',
        retention='30 days',
        compression='zip',
    )
    _LOGGING_CONFIGURED = True
    return logger
