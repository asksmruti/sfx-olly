"""FastAPI application that receives Splunk Observability webhook notifications."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from sfx_olly.config import WebhookSettings, get_logging_settings, get_webhook_settings
from sfx_olly.logging_config import setup_logging
from sfx_olly.webhook.handlers import AlertHandler, build_handlers
from sfx_olly.webhook.models import AlertPayload
from sfx_olly.webhook.security import (
    SIGNATURE_HEADER,
    IpAllowlist,
    ReplayGuard,
    verify_signature,
)

logger = logging.getLogger(__name__)


def create_app(
    settings: WebhookSettings, handlers: Sequence[AlertHandler] | None = None
) -> FastAPI:
    sinks = list(handlers) if handlers is not None else build_handlers(settings)
    secret = settings.shared_secret.get_secret_value().encode() if settings.shared_secret else None
    allowlist = IpAllowlist(settings.allowed_networks)
    replay_guard = ReplayGuard(settings.dedupe_ttl_seconds)

    app = FastAPI(title="sfx-olly webhook", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(settings.path, include_in_schema=False)
    async def receive_alert(request: Request, background: BackgroundTasks) -> JSONResponse:
        client_ip = request.client.host if request.client else None
        if not allowlist.allows(client_ip):
            logger.warning("Rejected webhook from disallowed address %s", client_ip)
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Expected application/json")

        body = await _read_body(request, settings.max_body_bytes)

        if secret is not None and not verify_signature(
            secret, body, request.headers.get(SIGNATURE_HEADER)
        ):
            logger.warning("Rejected webhook with missing/invalid signature from %s", client_ip)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")

        try:
            alert = AlertPayload.model_validate_json(body)
        except ValidationError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid payload") from None

        if replay_guard.is_duplicate(alert.dedupe_key):
            logger.info("Duplicate notification ignored for incident %s", alert.incident_id)
            return JSONResponse({"status": "duplicate"})

        # Respond 200 immediately; Splunk retries slow endpoints.
        background.add_task(_dispatch, sinks, alert)
        logger.info("Accepted alert incident=%s state=%s", alert.incident_id, alert.state)
        return JSONResponse({"status": "accepted"})

    return app


async def _read_body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdigit():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Content-Length")
        if int(declared) > limit:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Payload too large")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Payload too large")
    return bytes(body)


def _dispatch(handlers: Sequence[AlertHandler], alert: AlertPayload) -> None:
    for handler in handlers:
        try:
            handler.handle(alert)
        except Exception:
            logger.exception(
                "Handler %s failed for incident %s", type(handler).__name__, alert.incident_id
            )


def app_factory() -> FastAPI:
    """Entry point for uvicorn (also used by each worker process)."""
    log_settings = get_logging_settings()
    settings = get_webhook_settings()
    secrets = [settings.shared_secret.get_secret_value()] if settings.shared_secret else []
    setup_logging(log_settings.level, log_settings.format, secrets)
    return create_app(settings)
