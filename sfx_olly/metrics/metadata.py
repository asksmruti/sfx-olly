from __future__ import annotations

import json
from collections.abc import Iterator
from urllib.parse import quote

from sfx_olly.api.base import BaseAPI, with_default_field
from sfx_olly.utils import require_text


class MetadataAPI(BaseAPI):
    """Metric, dimension and metric-time-series (MTS) metadata.

    Bare terms are expanded: metrics -> `name:`, dimensions -> `key:`, MTS -> `sf_metric:`.
    """

    def search_metrics(self, query: str = "*", limit: int = 100, offset: int = 0) -> dict:
        return self._search("/v2/metric", with_default_field(query, "name"), limit, offset)

    def iter_metrics(
        self, query: str = "*", page_size: int = 1_000, max_items: int | None = None
    ) -> Iterator[dict]:
        return self._paginate("/v2/metric", with_default_field(query, "name"), page_size, max_items)

    def get_metric(self, name: str) -> dict:
        require_text(name, "name", 256)
        return self._http.get_json(f"/v2/metric/{quote(name, safe='')}")

    def inspect_metric(self, name: str, limit: int = 1_000) -> dict:
        """Summarize dimension values from a bounded, one-shot MTS search."""
        require_text(name, "name", 256)
        page = self.search_mts(f"sf_metric:{json.dumps(name)}", limit=limit)
        series = page.get("results", [])
        dimensions: dict[str, set[str]] = {}
        for item in series:
            for key, value in (item.get("dimensions") or {}).items():
                if value is not None and not key.startswith("sf_"):
                    dimensions.setdefault(key, set()).add(str(value))
        total = page.get("count", len(series))
        return {
            "metric": name,
            "matched_series": total,
            "inspected_series": len(series),
            "truncated": total > len(series),
            "dimensions": {key: sorted(values) for key, values in sorted(dimensions.items())},
        }

    def search_dimensions(self, query: str, limit: int = 100, offset: int = 0) -> dict:
        return self._search("/v2/dimension", with_default_field(query, "key"), limit, offset)

    def get_dimension(self, key: str, value: str) -> dict:
        require_text(key, "key", 256)
        require_text(value, "value", 256)
        return self._http.get_json(f"/v2/dimension/{quote(key, safe='')}/{quote(value, safe='')}")

    def search_mts(self, query: str, limit: int = 100, offset: int = 0) -> dict:
        return self._search(
            "/v2/metrictimeseries", with_default_field(query, "sf_metric"), limit, offset
        )

    def iter_mts(
        self, query: str, page_size: int = 1_000, max_items: int | None = None
    ) -> Iterator[dict]:
        return self._paginate(
            "/v2/metrictimeseries", with_default_field(query, "sf_metric"), page_size, max_items
        )