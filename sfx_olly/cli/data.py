from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rich.text import Text

from sfx_olly.api.client import SplunkOllyClient
from sfx_olly.metrics.query_builder import (
    AGGREGATIONS,
    ROLLUPS,
    MetricQuery,
    build_program,
    parse_key_values,
)
from sfx_olly.metrics.signalflow import MAX_PROGRAM_LENGTH, DataPoint
from sfx_olly.cli.output import console, emit, error_console
from sfx_olly.utils import VALUE_UNITS, format_value, ms_to_iso, parse_duration, time_range


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("timeseries", help="Fetch raw datapoints for MTS matching a query")
    p.add_argument("query", help="e.g. 'sf_metric:cpu.utilization AND host:web-01'")
    _add_window(p)
    p.add_argument("--last", type=int, default=5, help="points per series shown in table mode")
    p.set_defaults(handler=timeseries)

    p = sub.add_parser("signalflow", help="Execute a SignalFlow program over a time window")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("program", nargs="?", help="SignalFlow program text")
    src.add_argument("--file", type=Path, help="read program from file")
    _add_window(p)
    _add_latest(p)
    p.set_defaults(handler=signalflow)

    p = sub.add_parser(
        "query",
        help="Fetch any metric with filters/aggregation (builds SignalFlow for you)",
        description="Example: sfx-olly query example.bytes.total "
        "--filter environment=env-prod --rollup delta --agg sum --by topic "
        "--transform sum --over 1d --range 1d --resolution 1h --latest",
    )
    p.add_argument("metric", help="metric name (wildcards allowed), e.g. example.bytes.total")
    p.add_argument("--filter", action="append", metavar="KEY=V[,V]", help="include dimension values (repeatable; '*' wildcard ok)")
    p.add_argument("--exclude", action="append", metavar="KEY=V[,V]", help="exclude dimension values (repeatable)")
    p.add_argument("--rollup", choices=ROLLUPS, help="how raw points roll up to the resolution")
    p.add_argument("--agg", choices=AGGREGATIONS, help="aggregate across series")
    p.add_argument("--by", action="append", metavar="DIM", help="group the aggregation by dimension (repeatable)")
    p.add_argument("--transform", choices=AGGREGATIONS, help="aggregate over a time window (needs --over)")
    p.add_argument("--over", metavar="WINDOW", help="transform window, e.g. 1h, 1d")
    p.add_argument("--label", default="A")
    p.add_argument("--show-program", action="store_true", help="print the generated SignalFlow")
    p.add_argument("--dry-run", action="store_true", help="only print the SignalFlow, don't call the API")
    _add_window(p)
    _add_latest(p)
    p.set_defaults(handler=query)


def _add_window(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--range", default="15m", help="look-back window, e.g. 15m, 1h, 7d")
    parser.add_argument("--resolution", default="1m", help="rollup resolution, e.g. 10s, 1m, 1h")


def _add_latest(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--latest", action="store_true", help="show only the latest value per series")
    parser.add_argument(
        "--unit",
        choices=VALUE_UNITS,
        default="raw",
        help="value display unit: bytes = auto B/KiB/MiB/GiB (table only; JSON stays raw)",
    )


def timeseries(args: argparse.Namespace) -> int:
    start, end = time_range(args.range)
    with SplunkOllyClient() as client:
        data = client.timeseries.window(args.query, start, end, parse_duration(args.resolution))
    rows = [
        (ts_id, ms_to_iso(point[0]), point[1])
        for ts_id, points in data.items()
        for point in points[-max(args.last, 1):]
    ]
    emit(args.output, data, f"Time series ({len(data)} series)", ["TS ID", "Time (UTC)", "Value"], rows)
    return 0


def signalflow(args: argparse.Namespace) -> int:
    program = _read_program(args)
    start, end = time_range(args.range)
    with SplunkOllyClient() as client:
        points = client.signalflow.execute(program, start, end, parse_duration(args.resolution))
    _emit_points(args, points)
    return 0


def query(args: argparse.Namespace) -> int:
    spec = MetricQuery(
        metric=args.metric,
        filters=parse_key_values(args.filter),
        excludes=parse_key_values(args.exclude),
        rollup=args.rollup,
        aggregation=args.agg,
        group_by=args.by or [],
        transform=args.transform,
        window=args.over,
        label=args.label,
    )
    program = build_program(spec)
    if args.show_program or args.dry_run:
        console.print(program, markup=False, highlight=False, soft_wrap=True)
    if args.dry_run:
        return 0
    start, end = time_range(args.range)
    with SplunkOllyClient() as client:
        points = client.signalflow.execute(program, start, end, parse_duration(args.resolution))
    if not any(point.value is not None for point in points):
        error_console.print(Text(
            f"No non-null datapoints for {args.metric} in the last {args.range}. "
            f"Check dimension keys/values with: sfx-olly metrics inspect {args.metric}. "
            "Compare the dashboard's filters, time window, realm/org and rollup. "
            "An empty result does not prove the metric does not exist.",
            style="yellow",
        ))
    _emit_points(args, points)
    return 0


def _emit_points(args: argparse.Namespace, points: list[DataPoint]) -> None:
    if args.latest:
        latest: dict[str, DataPoint] = {}
        for p in points:
            if p.value is not None:
                latest[p.ts_id] = p
        points = list(latest.values())
    rows = [
        (ms_to_iso(p.timestamp_ms), _series_label(p.properties, p.ts_id), format_value(p.value, args.unit))
        for p in points
    ]
    emit(args.output, [asdict(p) for p in points], f"Results ({len(points)} points)", ["Time (UTC)", "Series", "Value"], rows)


def _read_program(args: argparse.Namespace) -> str:
    if args.file is None:
        return args.program
    path: Path = args.file
    if not path.is_file():
        raise ValueError(f"Program file not found: {path}")
    if path.stat().st_size > MAX_PROGRAM_LENGTH:
        raise ValueError(f"Program file exceeds {MAX_PROGRAM_LENGTH} bytes")
    return path.read_text(encoding="utf-8")


def _series_label(properties: dict[str, Any], ts_id: str) -> str:
    metric = properties.get("sf_originatingMetric") or properties.get("sf_metric") or ""
    dims = [f"{k}={v}" for k, v in sorted(properties.items()) if not k.startswith("sf_")]
    label = " ".join(filter(None, [str(metric), ", ".join(dims)]))
    return label or ts_id
