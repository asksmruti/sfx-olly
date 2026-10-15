"""Pluggable alert sinks. Implement `AlertHandler.handle` to add your own (Slack, Kafka, DB...)."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from rich.console import Console

from sfx_olly.config import WebhookSettings
from sfx_olly.webhook.formatter import render_alert
from sfx_olly.webhook.models import AlertPayload


@runtime_checkable
class AlertHandler(Protocol):
    def handle(self, alert: AlertPayload) -> None: ...


class ConsoleHandler:
    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()
        self._lock = threading.Lock()

    def handle(self, alert: AlertPayload) -> None:
        panel = render_alert(alert)
        with self._lock:
            self._console.print(panel)


class JsonlFileHandler:
    """Append one JSON line per alert; file is created owner-read/write only (0600)."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def handle(self, alert: AlertPayload) -> None:
        record = {
            "receivedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "alert": alert.model_dump(by_alias=True, exclude_none=True),
        }
        line = (json.dumps(record, ensure_ascii=True, default=str) + "\n").encode("utf-8")
        with self._lock:
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)


def build_handlers(settings: WebhookSettings) -> list[AlertHandler]:
    handlers: list[AlertHandler] = []
    if settings.console_output:
        handlers.append(ConsoleHandler())
    if settings.output_file:
        handlers.append(JsonlFileHandler(settings.output_file))
    return handlers
