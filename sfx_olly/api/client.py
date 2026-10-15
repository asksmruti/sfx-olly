from __future__ import annotations

from sfx_olly.api.alerts import AlertsAPI
from sfx_olly.api.http import HttpTransport
from sfx_olly.metrics import MetadataAPI, SignalFlowAPI, TimeSeriesAPI
from sfx_olly.config import ApiSettings, get_api_settings


class SplunkOllyClient:
    """Facade over all API groups sharing one pooled HTTP session.

    Example:
        with SplunkOllyClient() as client:
            client.metadata.search_metrics("name:cpu.*")
    """

    def __init__(self, settings: ApiSettings | None = None) -> None:
        self.settings = settings or get_api_settings()
        self._http = HttpTransport(self.settings)
        self.metadata = MetadataAPI(self._http)
        self.timeseries = TimeSeriesAPI(self._http)
        self.signalflow = SignalFlowAPI(self._http)
        self.alerts = AlertsAPI(self._http)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> SplunkOllyClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
