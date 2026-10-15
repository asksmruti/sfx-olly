from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from sfx_olly.cli.output import console, print_error
from sfx_olly.config import get_webhook_settings
from sfx_olly.webhook.formatter import render_alert
from sfx_olly.webhook.models import AlertPayload

_MAX_RENDER_FILE = 50 * 1024 * 1024


def register(sub: argparse._SubParsersAction) -> None:
    webhook = sub.add_parser("webhook", help="Receive and display Splunk alert webhooks")
    actions = webhook.add_subparsers(dest="action", required=True, metavar="<action>")

    p = actions.add_parser("serve", help="Start the webhook receiver (WEBHOOK_* settings)")
    p.set_defaults(handler=serve)

    p = actions.add_parser("send-test", help="POST a signed sample alert to the receiver")
    p.add_argument("--url", help="receiver URL (default: derived from WEBHOOK_* settings)")
    p.add_argument("--file", type=Path, help="JSON payload to send instead of the sample")
    p.add_argument("--state", default="anomalous", choices=["anomalous", "ok", "manually resolved", "stopped"])
    p.add_argument("--insecure", action="store_true", help="skip TLS verification (self-signed dev certs)")
    p.set_defaults(handler=send_test)

    p = actions.add_parser("render", help="Pretty-print alerts from a .json or .jsonl file")
    p.add_argument("file", type=Path)
    p.set_defaults(handler=render)


def serve(args: argparse.Namespace) -> int:
    from sfx_olly.webhook.server import serve as run_server

    run_server()
    return 0


def send_test(args: argparse.Namespace) -> int:
    from sfx_olly.webhook.testing import sample_alert, send_test_alert

    settings = get_webhook_settings()
    payload = json.loads(_read(args.file)) if args.file else sample_alert(args.state)
    secret = settings.shared_secret.get_secret_value() if settings.shared_secret else None
    url = args.url or settings.local_url
    response = send_test_alert(url, secret, payload, verify=not args.insecure)
    console.print(f"POST {url} -> HTTP {response.status_code} {response.text[:200]}")
    return 0 if response.ok else 1


def render(args: argparse.Namespace) -> int:
    failures = 0
    for number, record in enumerate(_load_records(args.file), start=1):
        try:
            # JSONL written by JsonlFileHandler wraps the payload in {"alert": ...}.
            alert = AlertPayload.model_validate(record.get("alert", record))
        except (ValidationError, AttributeError):
            print_error(f"Skipping invalid record #{number}")
            failures += 1
            continue
        console.print(render_alert(alert))
    return 1 if failures else 0


def _load_records(path: Path) -> list:
    text = _read(path)
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    return data if isinstance(data, list) else [data]


def _read(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"File not found: {path}")
    if path.stat().st_size > _MAX_RENDER_FILE:
        raise ValueError(f"File exceeds {_MAX_RENDER_FILE} bytes")
    return path.read_text(encoding="utf-8")
