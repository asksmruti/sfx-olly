from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from sfx_olly.api.http import HttpTransport
from sfx_olly.utils import require_int, require_text

# Splunk Observability caps offset + limit at 10,000 for search endpoints.
MAX_RESULTS = 10_000
MAX_QUERY_LENGTH = 2_048

_FIELD_SYNTAX_RE = re.compile(r"[:\s()]")


def with_default_field(query: str, default_field: str) -> str:
    """Search endpoints need `field:value`; turn a bare term like `cpu.*` into `name:cpu.*`."""
    query = query.strip()
    if query == "*" or _FIELD_SYNTAX_RE.search(query):
        return query
    return f"{default_field}:{query}"


class BaseAPI:
    def __init__(self, http: HttpTransport) -> None:
        self._http = http

    def _search(self, path: str, query: str, limit: int, offset: int, **extra: Any) -> dict:
        require_text(query, "query", MAX_QUERY_LENGTH)
        require_int(limit, "limit", 1, MAX_RESULTS)
        require_int(offset, "offset", 0, MAX_RESULTS)
        params = {"query": query, "limit": limit, "offset": offset, **extra}
        return self._http.get_json(path, params)

    def _paginate(
        self, path: str, query: str, page_size: int = 1_000, max_items: int | None = None
    ) -> Iterator[dict]:
        """Lazily walk all pages so large result sets never sit fully in memory."""
        require_int(page_size, "page_size", 1, MAX_RESULTS)
        offset = yielded = 0
        while offset < MAX_RESULTS:
            limit = min(page_size, MAX_RESULTS - offset)
            page = self._search(path, query, limit, offset)
            results = page.get("results", [])
            for item in results:
                yield item
                yielded += 1
                if max_items is not None and yielded >= max_items:
                    return
            offset += len(results)
            if not results or offset >= page.get("count", 0):
                return
