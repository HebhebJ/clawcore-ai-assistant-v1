import logging

logger = logging.getLogger(__name__)


def trace(run_id: str, message: str) -> None:
    logger.info("run=%s %s", run_id, message)
