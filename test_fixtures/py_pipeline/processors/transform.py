"""Concrete processors — data transformation, enrichment, filtering."""
from typing import Any
from datetime import datetime

from models.schemas import RawRecord, ProcessedRecord, PipelineConfig, DataSource
from processors.base import BaseProcessor
from utils.helpers import calculate_quality_score, sanitize_field_name


class FieldNormalizer(BaseProcessor):
    """Normalize field names and data types in records."""

    def process(self, record: RawRecord) -> ProcessedRecord:
        normalized: dict[str, Any] = {}
        for key, value in record.payload.items():
            safe_key = sanitize_field_name(key)
            if isinstance(value, str) and value.lower() in ("true", "false"):
                normalized[safe_key] = value.lower() == "true"
            elif isinstance(value, str) and value.replace(".", "").replace("-", "").isdigit():
                normalized[safe_key] = float(value) if "." in value else int(value)
            else:
                normalized[safe_key] = value

        quality = calculate_quality_score(normalized, list(record.payload.keys()))

        return ProcessedRecord(
            record_id=record.record_id,
            source=record.source,
            data=normalized,
            schema_version=1,
            quality_score=quality,
            tags=["normalized"],
        )


class DataEnricher(BaseProcessor):
    """Enrich records with computed fields and external lookups."""

    def __init__(self, config: PipelineConfig):
        super().__init__(config)
        self.geo_cache: dict[str, dict[str, str]] = {}

    def pre_process(self, record: RawRecord) -> RawRecord:
        # Add tracking headers
        record.headers["enriched_by"] = "DataEnricher"
        record.headers["enriched_at"] = datetime.now().isoformat()
        return record

    def process(self, record: RawRecord) -> ProcessedRecord:
        data = dict(record.payload)

        # Add computed fields
        data["processing_timestamp"] = datetime.now().isoformat()
        data["source_type"] = record.source.value
        data["data_category"] = self._categorize(data)

        # Simulate geo lookup
        if "ip" in data:
            ip = str(data["ip"])
            if ip not in self.geo_cache:
                self.geo_cache[ip] = {"country": "CN", "city": "Beijing"}
            data["geo"] = self.geo_cache[ip]

        quality = calculate_quality_score(data, ["user_id", "event_type", "processing_timestamp"])

        return ProcessedRecord(
            record_id=record.record_id,
            source=record.source,
            data=data,
            schema_version=2,
            quality_score=quality,
            tags=["normalized", "enriched"],
        )

    def _categorize(self, data: dict[str, Any]) -> str:
        event = str(data.get("event_type", "")).lower()
        if "purchase" in event or "order" in event:
            return "transaction"
        elif "view" in event or "browse" in event:
            return "behavior"
        elif "error" in event or "crash" in event:
            return "error"
        return "unknown"


class QualityFilter(BaseProcessor):
    """Filter out records below quality threshold."""

    def process(self, record: RawRecord) -> ProcessedRecord:
        quality = calculate_quality_score(
            record.payload,
            ["user_id", "timestamp", "event_type", "session_id"],
        )

        return ProcessedRecord(
            record_id=record.record_id,
            source=record.source,
            data=record.payload,
            schema_version=1,
            quality_score=quality,
            tags=["filtered"] if quality < self.config.quality_threshold else ["passed"],
            errors=[] if quality >= self.config.quality_threshold
            else [f"Quality {quality} below threshold {self.config.quality_threshold}"],
        )
