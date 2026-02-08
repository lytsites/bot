import contextvars
import logging
import os
from uuid import uuid4

from fastapi import Request

from common.config import LOG_LEVEL, LOG_PATH


request_id_ctx = contextvars.ContextVar("request_id", default="-")
_record_factory_set = False


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def setup_logging() -> None:
    global _record_factory_set
    logger = logging.getLogger()
    if logger.handlers:
        return

    log_dir = os.path.dirname(LOG_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | req=%(request_id)s | %(message)s"
    )

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.setLevel(LOG_LEVEL)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addFilter(RequestIdFilter())

    if not _record_factory_set:
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            if not hasattr(record, "request_id"):
                record.request_id = request_id_ctx.get()
            return record

        logging.setLogRecordFactory(record_factory)
        _record_factory_set = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_ctx.reset(token)
