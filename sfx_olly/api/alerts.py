from __future__ import annotations

import re

from sfx_olly.api.base import MAX_RESULTS, BaseAPI
from sfx_olly.utils import require_int

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _require_id(value: str, name: str) -> str:
    if not _ID_RE.fullmatch(value):
        raise ValueError(f"{name} must be 1-64 alphanumeric, '_' or '-' characters")
    return value


class AlertsAPI(BaseAPI):
    """Detectors and incidents."""

    def list_detectors(
        self, name: str | None = None, tags: str | None = None, limit: int = 50, offset: int = 0
    ) -> dict:
        require_int(limit, "limit", 1, MAX_RESULTS)
        require_int(offset, "offset", 0, MAX_RESULTS)
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if name:
            params["name"] = name[:256]
        if tags:
            params["tags"] = tags[:256]
        return self._http.get_json("/v2/detector", params)

    def get_detector(self, detector_id: str) -> dict:
        return self._http.get_json(f"/v2/detector/{_require_id(detector_id, 'detector_id')}")

    def list_incidents(
        self, include_resolved: bool = False, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        require_int(limit, "limit", 1, 1_000)
        require_int(offset, "offset", 0, MAX_RESULTS)
        params = {
            "includeResolved": str(include_resolved).lower(),
            "limit": limit,
            "offset": offset,
        }
        return self._http.get_json("/v2/incident", params)

    def get_incident(self, incident_id: str) -> dict:
        return self._http.get_json(f"/v2/incident/{_require_id(incident_id, 'incident_id')}")
