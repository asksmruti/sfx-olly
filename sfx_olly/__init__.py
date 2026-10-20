"""Splunk Observability Cloud (SignalFx) toolkit: REST client, CLI and webhook receiver."""

__version__ = "1.0.0"

from sfx_olly.api.client import SplunkOllyClient  # noqa: E402

__all__ = ["SplunkOllyClient", "__version__"]
