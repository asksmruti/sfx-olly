from __future__ import annotations

import argparse

from rich.text import Text
from rich.tree import Tree

from sfx_olly.api.client import SplunkOllyClient
from sfx_olly.cli.output import console, emit, print_json


def register(sub: argparse._SubParsersAction) -> None:
    metrics = sub.add_parser("metrics", help="Search and inspect metric metadata")
    actions = metrics.add_subparsers(dest="action", required=True, metavar="<action>")

    p = actions.add_parser("search", help="Search metrics, e.g. 'name:cpu.*'")
    p.add_argument("query", nargs="?", default="*")
    _add_paging(p)
    p.set_defaults(handler=metrics_search)

    p = actions.add_parser("get", help="Get one metric by name")
    p.add_argument("name")
    p.set_defaults(handler=metrics_get)

    p = actions.add_parser("inspect", help="Show a metric's dimension keys and values as a tree")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=1_000, help="max series inspected (1-10000; default 1000)")
    p.set_defaults(handler=metrics_inspect)

    dims = sub.add_parser("dimensions", help="Search dimensions")
    actions = dims.add_subparsers(dest="action", required=True, metavar="<action>")
    p = actions.add_parser("search", help="Search dimensions, e.g. 'key:host'")
    p.add_argument("query")
    _add_paging(p)
    p.set_defaults(handler=dimensions_search)

    mts = sub.add_parser("mts", help="Search metric time series")
    actions = mts.add_subparsers(dest="action", required=True, metavar="<action>")
    p = actions.add_parser("search", help="Search MTS, e.g. 'sf_metric:cpu.utilization'")
    p.add_argument("query")
    _add_paging(p)
    p.set_defaults(handler=mts_search)


def _add_paging(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=50, help="max results (default 50)")
    parser.add_argument("--offset", type=int, default=0, help="result offset (default 0)")


def metrics_search(args: argparse.Namespace) -> int:
    with SplunkOllyClient() as client:
        data = client.metadata.search_metrics(args.query, args.limit, args.offset)
    rows = [(m.get("name"), m.get("type"), m.get("description")) for m in data.get("results", [])]
    emit(args.output, data, f"Metrics ({data.get('count', 0)} total)", ["Name", "Type", "Description"], rows)
    return 0


def metrics_get(args: argparse.Namespace) -> int:
    with SplunkOllyClient() as client:
        print_json(client.metadata.get_metric(args.name))
    return 0


def metrics_inspect(args: argparse.Namespace) -> int:
    with SplunkOllyClient() as client:
        report = client.metadata.inspect_metric(args.name, args.limit)
    if args.output == "json":
        print_json(report)
        return 0
    tree = Tree(Text(
        f"{report['metric']} ({report['matched_series']} matching series; "
        f"{report['inspected_series']} inspected)"
    ))
    for key, values in report["dimensions"].items():
        branch = tree.add(Text(f"{key} ({len(values)} distinct values)"))
        for value in values[:10]:
            branch.add(Text(value))
        if len(values) > 10:
            branch.add(Text(f"... {len(values) - 10} more; use -o json for all inspected values"))
    console.print(tree)
    if report["truncated"]:
        console.print("Partial dimension inventory: increase --limit (max 10000).", markup=False)
    if not report["matched_series"]:
        console.print("No indexed series match this metric in the configured realm/org.", markup=False)
    return 0


def dimensions_search(args: argparse.Namespace) -> int:
    with SplunkOllyClient() as client:
        data = client.metadata.search_dimensions(args.query, args.limit, args.offset)
    rows = [(d.get("key"), d.get("value"), d.get("description")) for d in data.get("results", [])]
    emit(args.output, data, f"Dimensions ({data.get('count', 0)} total)", ["Key", "Value", "Description"], rows)
    return 0


def mts_search(args: argparse.Namespace) -> int:
    with SplunkOllyClient() as client:
        data = client.metadata.search_mts(args.query, args.limit, args.offset)
    rows = [(m.get("id"), m.get("metric"), m.get("dimensions")) for m in data.get("results", [])]
    emit(args.output, data, f"Metric time series ({data.get('count', 0)} total)", ["ID", "Metric", "Dimensions"], rows)
    return 0
