from __future__ import annotations

from sfx_olly.api.base import MAX_QUERY_LENGTH, BaseAPI, with_default_field
from sfx_olly.utils import require_int, require_text


class TimeSeriesAPI(BaseAPI):
    """Raw datapoints via /v1/timeserieswindow."""

    def window(
        self, query: str, start_ms: int, end_ms: int, resolution_ms: int = 60_000
    ) -> dict[str, list[list[float]]]:
        """Return {tsId: [[timestamp_ms, value], ...]} for MTS matching `query`."""
        require_text(query, "query", MAX_QUERY_LENGTH)
        require_int(resolution_ms, "resolution_ms", 1_000, 86_400_000)
        if start_ms >= end_ms:
            raise ValueError("start_ms must be before end_ms")
        params = {
            "query": with_default_field(query, "sf_metric"),
            "startMs": start_ms,
            "endMs": end_ms,
            "resolution": resolution_ms,
        }
        return self._http.get_json("/v1/timeserieswindow", params).get("data", {})