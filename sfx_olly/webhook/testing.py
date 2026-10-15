"""Helpers to exercise the receiver locally without a real Splunk alert."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any

import requests

from sfx_olly.webhook.security import SIGNATURE_HEADER, compute_signature


def sample_alert(state: str = "anomalous") -> dict[str, Any]:
    return {
        "sf_schema": 2,
        "detector": "High CPU on web tier",
        "detectorId": "DETECTOR123",
        "detectorUrl": "https://app.us1.signalfx.com/#/detector/DETECTOR123/edit",
        "incidentId": f"TEST{secrets.token_hex(4).upper()}",
        "eventType": "cpu-high",
        "rule": "CPU above 90%",
        "severity": "Critical",
        "status": state,
        "statusExtended": state,
        "description": "The value of cpu.utilization is above 90.",
        "messageTitle": "Critical Alert: CPU above 90% on web-01",
        "messageBody": "cpu.utilization has been above 90% for 5 minutes.",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "originatingMetric": "cpu.utilization",
        "src": "web-01",
        "dimensions": {"host": "web-01", "env": "prod", "sf_metric": "cpu.utilization"},
        "inputs": {"A": {"value": "97.3", "key": {"host": "web-01"}}},
        "runbookUrl": "https://wiki.example.com/runbooks/cpu",
        "tip": "Check top processes and recent deployments.",
    }


def send_test_alert(
    url: str,
    secret: str | None,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
    verify: bool | str = True,
) -> requests.Response:
    body = json.dumps(payload or sample_alert(), separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret:
        headers[SIGNATURE_HEADER] = compute_signature(secret.encode("utf-8"), body)
    return requests.post(
        url, data=body, headers=headers, timeout=timeout, allow_redirects=False, verify=verify
    )
