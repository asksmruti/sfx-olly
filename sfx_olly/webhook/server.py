from __future__ import annotations

import logging

import uvicorn

from sfx_olly.config import WebhookSettings, get_logging_settings, get_webhook_settings

logger = logging.getLogger(__name__)


def serve(settings: WebhookSettings | None = None) -> None:
    settings = settings or get_webhook_settings()

    if settings.shared_secret is None:
        logger.warning("Signature verification is DISABLED (WEBHOOK_REQUIRE_SIGNATURE=false)")
    if not settings.is_local_only and not settings.ssl_certfile:
        logger.warning(
            "Listening on %s without TLS. Splunk requires HTTPS (TLS 1.2+): "
            "terminate TLS at a reverse proxy/ingress or set WEBHOOK_SSL_CERTFILE/KEYFILE.",
            settings.host,
        )

    logger.info("Webhook receiver listening on %s", settings.local_url)
    uvicorn.run(
        "sfx_olly.webhook.app:app_factory",
        factory=True,
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        ssl_certfile=settings.ssl_certfile,
        ssl_keyfile=settings.ssl_keyfile,
        proxy_headers=settings.trust_proxy_headers,
        forwarded_allow_ips=settings.forwarded_allow_ips,
        server_header=False,
        log_config=None,
        log_level=get_logging_settings().level.lower(),
    )
