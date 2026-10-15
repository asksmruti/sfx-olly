import re
import time
from datetime import datetime, timezone

_DURATION_RE = re.compile(r"^(\d+)([smhdw])$")
_UNIT_MS = {"s": 1_000, "m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}

_BINARY_UNITS = {"gib": ("GiB", 1024**3), "mib": ("MiB", 1024**2), "kib": ("KiB", 1024)}
VALUE_UNITS = ("raw", "bytes", "kib", "mib", "gib")


def format_value(value: float | None, unit: str = "raw") -> float | str | None:
    """Format a numeric value; 'bytes' auto-scales to B/KiB/MiB/GiB."""
    if value is None or unit == "raw":
        return value
    if unit == "bytes":
        for label, factor in _BINARY_UNITS.values():
            if abs(value) >= factor:
                return f"{value / factor:,.2f} {label}"
        return f"{value:,.0f} B"
    label, factor = _BINARY_UNITS[unit]
    return f"{value / factor:,.2f} {label}"


def now_ms() -> int:
    return int(time.time() * 1000)


def parse_duration(value: str) -> int:
    """Convert '30s', '15m', '1h', '7d', '2w' to milliseconds."""
    match = _DURATION_RE.fullmatch(value.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration '{value}'. Use e.g. 30s, 15m, 1h, 7d, 2w")
    ms = int(match.group(1)) * _UNIT_MS[match.group(2)]
    if ms <= 0:
        raise ValueError("Duration must be greater than zero")
    return ms


def time_range(lookback: str, end_ms: int | None = None) -> tuple[int, int]:
    end = end_ms if end_ms is not None else now_ms()
    return end - parse_duration(lookback), end


def ms_to_iso(ms: int | float | None) -> str:
    if ms is None:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="seconds")


def require_int(value: int, name: str, low: int, high: int) -> int:
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high} (got {value})")
    return value


def require_text(value: str, name: str, max_length: int = 2048) -> str:
    if not value or not value.strip():
        raise ValueError(f"{name} must not be empty")
    if len(value) > max_length:
        raise ValueError(f"{name} exceeds {max_length} characters")
    return value
