"""Splunk Observability webhook payload (default template, sf_schema 2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertPayload(BaseModel):
    # extra="allow" keeps fields from custom payload templates.
    model_config = ConfigDict(extra="allow", populate_by_name=True, str_max_length=20_000)

    sf_schema: int | None = None
    incident_id: str | None = Field(default=None, alias="incidentId")
    event_type: str | None = Field(default=None, alias="eventType")
    org_id: str | None = Field(default=None, alias="orgId")
    detector: str | None = None
    detector_id: str | None = Field(default=None, alias="detectorId")
    detector_url: str | None = Field(default=None, alias="detectorUrl")
    detector_tags: list[Any] | None = Field(default=None, alias="detectorTags")
    rule: str | None = None
    severity: str | None = None
    status: str | None = None
    status_extended: str | None = Field(default=None, alias="statusExtended")
    description: str | None = None
    message_title: str | None = Field(default=None, alias="messageTitle")
    message_body: str | None = Field(default=None, alias="messageBody")
    timestamp: str | None = None
    originating_metric: str | None = Field(default=None, alias="originatingMetric")
    src: str | None = None
    dimensions: dict[str, Any] | None = None
    inputs: dict[str, Any] | list[Any] | None = None
    image_url: str | None = Field(default=None, alias="imageUrl")
    runbook_url: str | None = Field(default=None, alias="runbookUrl")
    tip: str | None = None
    detect_on_condition: str | None = Field(default=None, alias="detectOnCondition")
    detect_off_condition: str | None = Field(default=None, alias="detectOffCondition")

    @field_validator("severity", "sf_schema", mode="before")
    @classmethod
    def _coerce_scalar(cls, value: Any, info: Any) -> Any:
        if value in ("", None):
            return None
        if info.field_name == "severity":
            return str(value)
        return value

    @property
    def state(self) -> str:
        return (self.status_extended or self.status or "unknown").lower()

    @property
    def is_firing(self) -> bool:
        return self.state == "anomalous"

    @property
    def dedupe_key(self) -> str | None:
        if not self.incident_id:
            return None
        return f"{self.incident_id}|{self.state}|{self.timestamp or ''}"
