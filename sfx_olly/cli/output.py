from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

from sfx_olly.webhook.formatter import sanitize

console = Console()
error_console = Console(stderr=True)


def print_json(data: Any) -> None:
    console.print_json(json.dumps(data, default=str))


def print_table(title: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    table = Table(title=title, header_style="bold", show_lines=False)
    for column in columns:
        table.add_column(column, overflow="fold")
    for row in rows:
        table.add_row(*(Text(_cell(value)) for value in row))
    console.print(table)


def emit(
    output: str,
    data: Any,
    title: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
) -> None:
    if output == "json":
        print_json(data)
    else:
        print_table(title, columns, rows)


def print_error(message: str) -> None:
    error_console.print(Text(message, style="bold red"))


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return sanitize(json.dumps(value, separators=(",", ":"), default=str), 500)
    return sanitize(str(value), 500)
