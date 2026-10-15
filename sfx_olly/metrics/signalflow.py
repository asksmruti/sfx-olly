"""SignalFlow execution over HTTP Server-Sent Events."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from sfx_olly.api.base import BaseAPI
from sfx_olly.metrics.query_builder import MetricQuery, build_program
from sfx_olly.exceptions import SignalFlowError
from sfx_olly.utils import require_int, require_text

MAX_PROGRAM_LENGTH = 50_000


@dataclass(frozen=True)
class SignalFlowMessage:
    event: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class DataPoint:
    timestamp_ms: int | None
    ts_id: str
    value: float | None
    properties: dict[str, Any] = field(default_factory=dict)


class SignalFlowAPI(BaseAPI):
    def stream(
        self,
        program: str,
        start_ms: int,
        stop_ms: int,
        resolution_ms: int = 60_000,
        max_delay_ms: int | None = None,
    ) -> Iterator[SignalFlowMessage]:
        """Yield raw SSE messages (metadata, data, control-message, ...)."""
        require_text(program, "program", MAX_PROGRAM_LENGTH)
        require_int(resolution_ms, "resolution_ms", 1_000, 86_400_000)
        if start_ms >= stop_ms:
            raise ValueError("start_ms must be before stop_ms")

        params: dict[str, Any] = {
            "start": start_ms,
            "stop": stop_ms,
            "resolution": resolution_ms,
            "immediate": "true",
        }
        if max_delay_ms is not None:
            params["maxDelay"] = require_int(max_delay_ms, "max_delay_ms", 0, 900_000)

        response = self._http.request(
            "POST",
            f"{self._http.stream_url}/v2/signalflow/execute",
            params=params,
            data=program.encode("utf-8"),
            headers={"Content-Type": "text/plain", "Accept": "text/event-stream"},
            stream=True,
        )
        with response:
            yield from _parse_sse(response.iter_lines(decode_unicode=True))

    def execute(
        self,
        program: str,
        start_ms: int,
        stop_ms: int,
        resolution_ms: int = 60_000,
        max_delay_ms: int | None = None,
    ) -> list[DataPoint]:
        """Run a program to completion and return datapoints joined with their metadata."""
        metadata: dict[str, dict[str, Any]] = {}
        points: list[DataPoint] = []
        for msg in self.stream(program, start_ms, stop_ms, resolution_ms, max_delay_ms):
            if msg.event == "metadata":
                metadata[msg.payload.get("tsId", "")] = msg.payload.get("properties", {})
            elif msg.event == "data":
                timestamp = msg.payload.get("logicalTimestampMs")
                for ts_id, value in _iter_values(msg.payload.get("data")):
                    points.append(DataPoint(timestamp, ts_id, value, metadata.get(ts_id, {})))
            elif msg.event == "error":
                raise SignalFlowError(json.dumps(msg.payload)[:500])
            elif msg.event == "control-message":
                if msg.payload.get("event") == "CHANNEL_ABORT":
                    raise SignalFlowError(json.dumps(msg.payload.get("abortInfo", msg.payload))[:500])
                if msg.payload.get("event") == "END_OF_CHANNEL":
                    break
        return points

    def query(
        self,
        spec: MetricQuery,
        start_ms: int,
        stop_ms: int,
        resolution_ms: int = 60_000,
    ) -> list[DataPoint]:
        """Fetch any metric from a structured spec instead of hand-written SignalFlow."""
        return self.execute(build_program(spec), start_ms, stop_ms, resolution_ms)


def _parse_sse(lines: Iterable[str | None]) -> Iterator[SignalFlowMessage]:
    event, buffer = "message", []
    for line in lines:
        if line is None:
            continue
        if line == "":
            if buffer:
                yield SignalFlowMessage(event, _loads(buffer))
            event, buffer = "message", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            buffer.append(line[len("data:"):].lstrip())
    if buffer:
        yield SignalFlowMessage(event, _loads(buffer))


def _loads(buffer: list[str]) -> dict[str, Any]:
    raw = "\n".join(buffer)
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {"raw": raw}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _iter_values(data: Any) -> Iterator[tuple[str, float | None]]:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield str(item.get("tsId", "")), item.get("value")
    elif isinstance(data, dict):
        for ts_id, value in data.items():
            yield str(ts_id), value