import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings


def get_request_id():
    from app.api.middleware import request_id_context_var

    try:
        return request_id_context_var.get()
    except Exception:
        return "-"


class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id()
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging():
    logger = logging.getLogger("fastapi_starter")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        logger.addFilter(RequestIDFilter())
        handler.addFilter(RequestIDFilter())

        if settings.LOG_FORMAT == "json":
            handler.setFormatter(JSONFormatter())
        else:
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] [ReqID: %(request_id)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger


logger = setup_logging()
