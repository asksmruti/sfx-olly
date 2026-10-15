"""Render alerts for humans. All payload values are untrusted and sanitised."""

from __future__ import annotations

import json
from typing import Any

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sfx_olly.webhook.models import AlertPayload

_MAX_FIELD = 2_000
_SEVERITY_STYLES = {
    "critical": "bold white on red",
    "major": "bold red",
    "minor": "bold yellow",
    "warning": "yellow",
    "info": "cyan",
}
_STATE_STYLES = {
    "anomalous": "bold white on red",
    "ok": "bold white on green",
    "manually resolved": "bold white on green",
    "stopped": "bold white on grey50",
}
_BORDER_STYLES = {"anomalous": "red", "ok": "green", "manually resolved": "green"}


def sanitize(value: Any, limit: int = _MAX_FIELD) -> str:
    """Stringify, strip control/escape characters and truncate."""
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    text = "".join(ch for ch in text if ch in "\n\t" or ch.isprintable())
    return text if len(text) <= limit else text[:limit] + "…"


def render_alert(alert: AlertPayload) -> Panel:
    state = alert.state
    severity = alert.severity or "Unknown"

    title = Text()
    title.append(f" {state.upper()} ", style=_STATE_STYLES.get(state, "bold reverse"))
    title.append(" ")
    title.append(f" {sanitize(severity, 32)} ", style=_SEVERITY_STYLES.get(severity.lower(), "bold"))
    title.append(" ")
    title.append(sanitize(alert.message_title or alert.rule or "Splunk alert", 200), style="bold")

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column(overflow="fold")

    for label, value in (
        ("Detector", alert.detector),
        ("Rule", alert.rule),
        ("Metric", alert.originating_metric),
        ("Source", alert.src),
        ("Time", alert.timestamp),
        ("Incident", alert.incident_id),
        ("Description", alert.description),
    ):
        if value:
            table.add_row(label, Text(sanitize(value)))

    if alert.dimensions:
        dims = "\n".join(
            f"{sanitize(k, 100)} = {sanitize(v, 300)}" for k, v in sorted(alert.dimensions.items())
        )
        table.add_row("Dimensions", Text(dims))

    inputs = _format_inputs(alert.inputs)
    if inputs:
        table.add_row("Inputs", Text(inputs))

    for label, value in (
        ("Message", alert.message_body),
        ("Tip", alert.tip),
        ("Runbook", alert.runbook_url),
        ("Detector URL", alert.detector_url),
    ):
        if value:
            table.add_row(label, Text(sanitize(value)))

    return Panel(table, title=title, title_align="left", border_style=_BORDER_STYLES.get(state, "white"))


def _format_inputs(inputs: dict[str, Any] | list[Any] | None) -> str:
    if not inputs:
        return ""
    items = inputs.items() if isinstance(inputs, dict) else enumerate(inputs)
    lines = []
    for name, data in items:
        if isinstance(data, dict):
            value = data.get("value")
            key = data.get("key")
            suffix = f"  {sanitize(key, 300)}" if key else ""
            lines.append(f"{sanitize(name, 100)}: {sanitize(value, 100)}{suffix}")
        else:
            lines.append(f"{sanitize(name, 100)}: {sanitize(data, 300)}")
    return "\n".join(lines)
