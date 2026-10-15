import json
import logging
import sys
from collections.abc import Iterable

_REDACTED = "***REDACTED***"


class RedactingFilter(logging.Filter):
    """Masks configured secrets in every log message as a last line of defence."""

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = sorted({s for s in secrets if s and len(s) >= 4}, key=len, reverse=True)

    def filter(self, record: logging.LogRecord) -> bool:
        if self._secrets:
            message = record.getMessage()
            for secret in self._secrets:
                message = message.replace(secret, _REDACTED)
            record.msg, record.args = message, None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: str = "INFO", fmt: str = "text", secrets: Iterable[str] = ()) -> None:
    handler = logging.StreamHandler(sys.stderr)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter(secrets))

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # urllib3 debug logs include full URLs; keep them quiet unless explicitly debugging.
    logging.getLogger("urllib3").setLevel(max(logging.WARNING, root.level))
