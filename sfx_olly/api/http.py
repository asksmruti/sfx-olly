"""Shared HTTP transport: auth header, TLS, timeouts, retries and error mapping."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from sfx_olly import __version__
from sfx_olly.config import ApiSettings
from sfx_olly.exceptions import ApiError, AuthenticationError, NotFoundError, RateLimitError

logger = logging.getLogger(__name__)
# Enabled by `sfx-olly -v`; never logs headers, so the token is not exposed.
request_logger = logging.getLogger("sfx_olly.requests")

_RETRY_STATUSES = (429, 500, 502, 503, 504)
_MAX_ERROR_BODY = 500


class HttpTransport:
    def __init__(self, settings: ApiSettings) -> None:
        self.api_url = settings.api_url
        self.stream_url = settings.stream_url
        self._timeout = settings.timeout_seconds

        retry = Retry(
            total=settings.max_retries,
            backoff_factor=settings.backoff_factor,
            status_forcelist=_RETRY_STATUSES,
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=settings.pool_maxsize,
            pool_maxsize=settings.pool_maxsize,
        )
        self._session = requests.Session()
        # Only HTTPS is mounted with retries; plain HTTP is never used for API calls.
        self._session.mount("https://", adapter)
        self._session.verify = settings.ca_bundle or True
        self._session.headers.update(
            {
                "X-SF-Token": settings.token.get_secret_value(),
                "Accept": "application/json",
                "User-Agent": f"sfx-olly/{__version__}",
            }
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        data: bytes | str | None = None,
        headers: dict[str, str] | None = None,
        stream: bool = False,
    ) -> requests.Response:
        if request_logger.isEnabledFor(logging.DEBUG):
            prepared = requests.PreparedRequest()
            prepared.prepare_url(url, params)
            request_logger.debug("--> %s %s", method, prepared.url)
            if isinstance(data, (bytes, str)) and data:
                body = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
                request_logger.debug("    body: %s", body[:2_000])
        started = time.monotonic()
        try:
            # Redirects are disabled so the token header is never forwarded to another host.
            response = self._session.request(
                method,
                url,
                params=params,
                json=json_body,
                data=data,
                headers=headers,
                stream=stream,
                timeout=self._timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise ApiError(f"{method} {url} failed: {exc.__class__.__name__}") from exc

        request_logger.debug(
            "<-- HTTP %s (%d ms)", response.status_code, (time.monotonic() - started) * 1000
        )
        if response.status_code >= 300:
            self._raise_for_status(response)
        return response

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.request("GET", f"{self.api_url}{path}", params=params)
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(f"Invalid JSON returned by {path}", response.status_code) from exc

    def close(self) -> None:
        self._session.close()

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        status = response.status_code
        try:
            detail = response.text[:_MAX_ERROR_BODY]
        finally:
            response.close()
        endpoint = response.url.split("?", 1)[0]
        message = f"HTTP {status} from {response.request.method} {endpoint}: {detail}"
        if status in (401, 403):
            raise AuthenticationError(message, status)
        if status == 404:
            raise NotFoundError(message, status)
        if status == 429:
            raise RateLimitError(message, status)
        raise ApiError(message, status)
