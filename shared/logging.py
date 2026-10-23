"""Framework-agnostic structured logging with request-scoped context."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

client_ip_ctx: ContextVar[str] = ContextVar("client_ip", default="-")
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_ctx.get(),
            "client_ip": client_ip_ctx.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())

    for noisy in ("uvicorn.access", "sqlalchemy.engine", "werkzeug"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
