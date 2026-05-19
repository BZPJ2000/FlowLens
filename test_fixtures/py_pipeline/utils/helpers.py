"""Utility helpers — used by processors and pipeline runner."""
import hashlib
import time
import json
from typing import Any
from datetime import datetime


def generate_record_id(source_name: str, raw_data: dict[str, Any]) -> str:
    """Generate deterministic record ID from source + content hash."""
    content_str = json.dumps(raw_data, sort_keys=True, default=str)
    content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]
    return f"{source_name}_{content_hash}_{int(time.time() * 1000)}"


def calculate_quality_score(data: dict[str, Any], required_fields: list[str]) -> float:
    """Calculate data quality score based on field completeness and validity."""
    if not required_fields:
        return 1.0

    present = 0
    valid = 0
    for field in required_fields:
        value = data.get(field)
        if value is not None:
            present += 1
            if isinstance(value, str) and len(str(value).strip()) > 0:
                valid += 1
            elif isinstance(value, (int, float, bool, list, dict)):
                valid += 1

    completeness = present / len(required_fields)
    validity = valid / len(required_fields) if present > 0 else 0
    return round(completeness * 0.6 + validity * 0.4, 3)


def timestamp_to_iso(ts: float) -> str:
    """Convert Unix timestamp to ISO format string."""
    return datetime.fromtimestamp(ts).isoformat()


def sanitize_field_name(name: str) -> str:
    """Convert arbitrary string to safe field name."""
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def batch_records(records: list[Any], batch_size: int) -> list[list[Any]]:
    """Split records into batches of batch_size."""
    return [records[i:i + batch_size] for i in range(0, len(records), batch_size)]


def calculate_latency_p99(latencies_ms: list[float]) -> float:
    """Calculate the 99th percentile latency."""
    if not latencies_ms:
        return 0.0
    sorted_lat = sorted(latencies_ms)
    idx = int(len(sorted_lat) * 0.99)
    return sorted_lat[min(idx, len(sorted_lat) - 1)]


def merge_metrics(*metrics_dicts: dict[str, Any]) -> dict[str, Any]:
    """Merge multiple metric snapshots."""
    merged: dict[str, Any] = {}
    for m in metrics_dicts:
        for key, value in m.items():
            if key in merged and isinstance(value, (int, float)):
                merged[key] = merged[key] + value
            else:
                merged[key] = value
    return merged
