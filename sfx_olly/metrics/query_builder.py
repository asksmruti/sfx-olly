"""Build SignalFlow programs from structured, validated metric queries."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

AGGREGATIONS = ("mean", "sum", "min", "max", "count", "median", "stddev", "variance")
ROLLUPS = ("average", "sum", "min", "max", "count", "delta", "rate", "latest", "lag")

_METRIC_RE = re.compile(r"^[A-Za-z0-9_.:/\-*]{1,256}$")
_KEY_RE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,128}$")
_WINDOW_RE = re.compile(r"^[1-9][0-9]{0,4}[smhdw]$")
_LABEL_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_FORBIDDEN_VALUE_CHARS = set("'\"\\") | {chr(code) for code in range(32)}


@dataclass
class MetricQuery:
    metric: str
    filters: dict[str, list[str]] = field(default_factory=dict)
    excludes: dict[str, list[str]] = field(default_factory=dict)
    rollup: str | None = None
    aggregation: str | None = None
    group_by: list[str] = field(default_factory=list)
    transform: str | None = None
    window: str | None = None
    label: str = "A"


def build_program(spec: MetricQuery) -> str:
    _check(_METRIC_RE, spec.metric, "metric")
    _check(_LABEL_RE, spec.label, "label")

    args = [_quote(spec.metric)]
    filter_expr = _filter_expression(spec.filters, spec.excludes)
    if filter_expr:
        args.append(f"filter={filter_expr}")
    if spec.rollup:
        _choice(spec.rollup, ROLLUPS, "rollup")
        args.append(f"rollup={_quote(spec.rollup)}")
    program = f"data({', '.join(args)})"

    if spec.aggregation:
        _choice(spec.aggregation, AGGREGATIONS, "aggregation")
        by = ""
        if spec.group_by:
            for key in spec.group_by:
                _check(_KEY_RE, key, "group-by dimension")
            by = f"by=[{', '.join(_quote(key) for key in spec.group_by)}]"
        program += f".{spec.aggregation}({by})"
    elif spec.group_by:
        raise ValueError("group_by requires an aggregation (e.g. --agg sum --by topic)")

    if spec.transform or spec.window:
        if not (spec.transform and spec.window):
            raise ValueError("transform and window must be used together (e.g. --transform sum --over 1d)")
        _choice(spec.transform, AGGREGATIONS, "transform")
        _check(_WINDOW_RE, spec.window, "window")
        program += f".{spec.transform}(over={_quote(spec.window)})"

    return f"{program}.publish(label={_quote(spec.label)})"


def parse_key_values(items: Iterable[str] | None) -> dict[str, list[str]]:
    """['env=prod', 'topic=a,b', 'env=dev'] -> {'env': ['prod', 'dev'], 'topic': ['a', 'b']}"""
    result: dict[str, list[str]] = {}
    for item in items or []:
        key, sep, raw = item.partition("=")
        key = key.strip()
        values = [value.strip() for value in raw.split(",") if value.strip()]
        if not sep or not key or not values:
            raise ValueError(f"Expected key=value[,value...], got '{item}'")
        result.setdefault(key, []).extend(values)
    return result


def _filter_expression(filters: dict[str, list[str]], excludes: dict[str, list[str]]) -> str:
    parts = [_filter_call(key, values) for key, values in filters.items()]
    parts += [f"not {_filter_call(key, values)}" for key, values in excludes.items()]
    return " and ".join(parts)


def _filter_call(key: str, values: list[str]) -> str:
    _check(_KEY_RE, key, "filter dimension")
    if not values:
        raise ValueError(f"filter '{key}' needs at least one value")
    for value in values:
        _check_value(value)
    return f"filter({', '.join(_quote(value) for value in (key, *values))})"


def _check_value(value: str) -> None:
    if not value or len(value) > 256 or _FORBIDDEN_VALUE_CHARS.intersection(value):
        raise ValueError(f"invalid filter value '{value[:50]}' (no quotes, backslashes or control chars)")


def _check(pattern: re.Pattern[str], value: str, name: str) -> None:
    if not value or not pattern.fullmatch(value):
        raise ValueError(f"invalid {name} '{value[:50]}'")


def _choice(value: str, allowed: tuple[str, ...], name: str) -> None:
    if value not in allowed:
        raise ValueError(f"invalid {name} '{value}', choose from: {', '.join(allowed)}")


def _quote(value: str) -> str:
    return f"'{value}'"