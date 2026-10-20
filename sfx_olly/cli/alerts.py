from __future__ import annotations

import argparse

from sfx_olly.api.client import SplunkOllyClient
from sfx_olly.cli.output import emit, print_json
from sfx_olly.utils import ms_to_iso


def register(sub: argparse._SubParsersAction) -> None:
    detectors = sub.add_parser("detectors", aliases=["detector"], help="List or inspect detectors")
    actions = detectors.add_subparsers(dest="action", required=True, metavar="<action>")
    p = actions.add_parser("list", help="List detectors")
    p.add_argument("--name", help="filter by name (substring)")
    p.add_argument("--tag", help="filter by tag")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(handler=detectors_list)
    p = actions.add_parser("get", help="Get a detector by ID")
    p.add_argument("detector_id")
    p.set_defaults(handler=detectors_get)

    incidents = sub.add_parser("incidents", aliases=["incident"], help="List or inspect incidents (alerts)")
    actions = incidents.add_subparsers(dest="action", required=True, metavar="<action>")
    p = actions.add_parser("list", help="List incidents")
    p.add_argument("--include-resolved", action="store_true")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(handler=incidents_list)
    p = actions.add_parser("get", help="Get an incident by ID")
    p.add_argument("incident_id")
    p.set_defaults(handler=incidents_get)


def detectors_list(args: argparse.Namespace) -> int:
    with SplunkOllyClient() as client:
        data = client.alerts.list_detectors(args.name, args.tag, args.limit, args.offset)
    rows = [
        (d.get("id"), d.get("name"), ms_to_iso(d.get("lastUpdated")), ", ".join(d.get("tags") or []))
        for d in data.get("results", [])
    ]
    emit(args.output, data, f"Detectors ({data.get('count', 0)} total)", ["ID", "Name", "Last updated (UTC)", "Tags"], rows)
    return 0


def detectors_get(args: argparse.Namespace) -> int:
    with SplunkOllyClient() as client:
        print_json(client.alerts.get_detector(args.detector_id))
    return 0


def incidents_list(args: argparse.Namespace) -> int:
    with SplunkOllyClient() as client:
        data = client.alerts.list_incidents(args.include_resolved, args.limit, args.offset)
    rows = []
    for inc in data:
        events = inc.get("events") or [{}]
        rows.append(
            (
                inc.get("incidentId"),
                inc.get("detectorName"),
                inc.get("severity"),
                inc.get("anomalyState"),
                ms_to_iso(events[-1].get("timestamp")),
            )
        )
    emit(args.output, data, f"Incidents ({len(data)})", ["Incident", "Detector", "Severity", "State", "Last event (UTC)"], rows)
    return 0


def incidents_get(args: argparse.Namespace) -> int:
    with SplunkOllyClient() as client:
        print_json(client.alerts.get_incident(args.incident_id))
    return 0
