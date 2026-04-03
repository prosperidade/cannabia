# src/infra/logging.py
"""
Logging estruturado em JSON com redacao de dados sensiveis.
Cada log entry inclui campos padronizados para correlacao e observabilidade.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from src.infra.security import redact_text


class JsonFormatter(logging.Formatter):
    """Emite cada log record como uma linha JSON com campos padronizados."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        message = redact_text(message)

        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "message": message,
        }

        # Campos de contexto injetados via extra ou Flask g
        for ctx_field in (
            "request_id", "user_id", "tenant_id", "clinic_id",
            "path", "method", "status_code", "elapsed_ms",
        ):
            value = getattr(record, ctx_field, None)
            if value is not None:
                entry[ctx_field] = value

        if record.exc_info and record.exc_info[1]:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """Configura logging raiz com JSON formatter para stdout e arquivo."""
    root = logging.getLogger()

    # Evita adicionar handlers duplicados em reloads
    if any(isinstance(h, logging.StreamHandler) and hasattr(h.formatter, '__class__')
           and h.formatter.__class__.__name__ == 'JsonFormatter' for h in root.handlers):
        return

    root.setLevel(logging.INFO)

    # Remove handlers default para evitar duplicacao
    root.handlers.clear()

    formatter = JsonFormatter()

    # Console (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # Arquivo
    file_handler = logging.FileHandler("cannabia.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
