from __future__ import annotations
"""程式入口點

此版本會持續輪詢 OpenSearch，將新日誌交由 ``log_processor`` 處理。"""

import logging
from time import sleep

from . import config
from .src import log_processor
from .src.utils import logger

# 統一設定 logging handler
log_handlers = [logging.StreamHandler()]
try:
    fh = logging.FileHandler(config.LMS_OPERATIONAL_LOG_FILE, encoding="utf-8")
    log_handlers.append(fh)
except PermissionError:
    print(f"[CRITICAL] Cannot write to {config.LMS_OPERATIONAL_LOG_FILE}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    handlers=log_handlers,
)


def main() -> None:
    """Main polling loop."""
    logger.info("Starting OpenSearch polling loop")
    while True:
        try:
            count = log_processor.process_new_logs()
            if count:
                logger.info("Processed %d new logs", count)
        except Exception as exc:  # pragma: no cover - log unexpected errors
            logger.error("Error processing logs: %s", exc)
        sleep(config.POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
