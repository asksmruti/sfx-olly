"""Typed configuration loaded from environment variables or a local `.env` file."""

from __future__ import annotations

import ipaddress
import re
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = ".env"
_REALM_RE = re.compile(r"^[a-z]{2,4}[0-9]{1,2}$")
_PATH_RE = re.compile(r"^/[A-Za-z0-9/_\-.]*$")
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class ApiSettings(BaseSettings):
    """Splunk Observability API client settings (prefix `SFX_`)."""

    model_config = SettingsConfigDict(env_prefix="SFX_", env_file=_ENV_FILE, extra="ignore")

    token: SecretStr
    realm: str = "us1"
    api_base_url: str | None = None
    stream_base_url: str | None = None
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_factor: float = Field(default=0.5, ge=0, le=30)
    pool_maxsize: int = Field(default=10, ge=1, le=200)
    ca_bundle: str | None = None

    @field_validator("token")
    @classmethod
    def _token_not_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("realm")
    @classmethod
    def _valid_realm(cls, value: str) -> str:
        value = value.strip().lower()
        if not _REALM_RE.fullmatch(value):
            raise ValueError("invalid realm (expected e.g. us1, eu0, jp0)")
        return value

    @field_validator("api_base_url", "stream_base_url")
    @classmethod
    def _https_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().rstrip("/")
        if not value.startswith("https://"):
            raise ValueError("must start with https://")
        return value

    @property
    def api_url(self) -> str:
        return self.api_base_url or f"https://api.{self.realm}.signalfx.com"

    @property
    def stream_url(self) -> str:
        return self.stream_base_url or f"https://stream.{self.realm}.signalfx.com"


class LoggingSettings(BaseSettings):
    """Logging settings (prefix `LOG_`)."""

    model_config = SettingsConfigDict(env_prefix="LOG_", env_file=_ENV_FILE, extra="ignore")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["text", "json"] = "text"

    @field_validator("level", mode="before")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper() if isinstance(value, str) else value


class WebhookSettings(BaseSettings):
    """Webhook receiver settings (prefix `WEBHOOK_`)."""

    model_config = SettingsConfigDict(env_prefix="WEBHOOK_", env_file=_ENV_FILE, extra="ignore")

    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)
    path: str = "/webhooks/splunk"
    workers: int = Field(default=1, ge=1, le=64)
    shared_secret: SecretStr | None = None
    require_signature: bool = True
    max_body_bytes: int = Field(default=262_144, ge=1_024, le=10_485_760)
    allowed_cidrs: str = ""
    trust_proxy_headers: bool = False
    forwarded_allow_ips: str = "127.0.0.1"
    dedupe_ttl_seconds: int = Field(default=300, ge=0, le=86_400)
    console_output: bool = True
    output_file: str | None = None
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None

    @field_validator("path")
    @classmethod
    def _valid_path(cls, value: str) -> str:
        if not _PATH_RE.fullmatch(value):
            raise ValueError("must start with '/' and contain only [A-Za-z0-9/_-.]")
        return value

    @field_validator("allowed_cidrs")
    @classmethod
    def _valid_cidrs(cls, value: str) -> str:
        for cidr in _split_csv(value):
            ipaddress.ip_network(cidr, strict=False)
        return value

    @model_validator(mode="after")
    def _security_checks(self) -> WebhookSettings:
        if self.shared_secret is not None and not self.shared_secret.get_secret_value().strip():
            self.shared_secret = None
        if self.require_signature and self.shared_secret is None:
            raise ValueError(
                "WEBHOOK_SHARED_SECRET is required when WEBHOOK_REQUIRE_SIGNATURE=true"
            )
        if bool(self.ssl_certfile) != bool(self.ssl_keyfile):
            raise ValueError("set both WEBHOOK_SSL_CERTFILE and WEBHOOK_SSL_KEYFILE, or neither")
        return self

    @property
    def allowed_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        return [ipaddress.ip_network(c, strict=False) for c in _split_csv(self.allowed_cidrs)]

    @property
    def is_local_only(self) -> bool:
        return self.host in _LOCAL_HOSTS

    @property
    def local_url(self) -> str:
        scheme = "https" if self.ssl_certfile else "http"
        host = "127.0.0.1" if self.host in {"0.0.0.0", "::"} else self.host
        return f"{scheme}://{host}:{self.port}{self.path}"


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_api_settings() -> ApiSettings:
    return ApiSettings()  # type: ignore[call-arg]


@lru_cache
def get_logging_settings() -> LoggingSettings:
    return LoggingSettings()


@lru_cache
def get_webhook_settings() -> WebhookSettings:
    return WebhookSettings()


def known_secrets() -> list[str]:
    """Best-effort list of configured secrets, used to redact logs."""
    secrets: list[str] = []
    for loader, attr in (
        (get_api_settings, "token"),
        (get_webhook_settings, "shared_secret"),
    ):
        try:
            value = getattr(loader(), attr)
        except ValidationError:
            continue
        if value is not None:
            secrets.append(value.get_secret_value())
    return secrets
