"""Structured logging for the application processes.

One JSON line per log record, so a log aggregator can filter by level and
logger without parsing prose. Configured once, in the composition root; library
code keeps using plain ``logging.getLogger(__name__)`` and never knows the
format. Content redaction stays where it belongs - callers redact before
logging (see :func:`rag.domain.privacy.redact`); the formatter never sees
plaintext user content.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = record.exc_info[0].__name__
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Install the JSON formatter on the root logger, once."""
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
