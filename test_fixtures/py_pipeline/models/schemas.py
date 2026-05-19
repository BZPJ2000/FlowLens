"""Core data models — the type hub for the entire pipeline."""
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional, Any


class PipelineStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    PROCESSING = "processing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class DataSource(str, Enum):
    KAFKA = "kafka"
    S3 = "s3"
    HTTP = "http"
    POSTGRES = "postgres"
    REDIS = "redis"


@dataclass
class RawRecord:
    """Raw data received from source — before any processing."""
    record_id: str
    source: DataSource
    payload: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)
    received_at: float = field(default_factory=lambda: datetime.now().timestamp())
    partition_key: str = ""
    raw_size_bytes: int = 0


@dataclass
class ProcessedRecord:
    """Data after transformation — enriched with metadata."""
    record_id: str
    source: DataSource
    data: dict[str, Any]
    schema_version: int
    tags: list[str] = field(default_factory=list)
    quality_score: float = 1.0
    processing_latency_ms: float = 0.0
    transformed_by: str = "unknown"
    errors: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of validation checks on a processed record."""
    record_id: str
    is_valid: bool
    checks_passed: int
    checks_failed: int
    failures: list[dict[str, str]] = field(default_factory=list)
    validated_at: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class PipelineConfig:
    """Configuration for the entire pipeline."""
    name: str
    source: DataSource
    batch_size: int = 100
    max_retries: int = 3
    retry_delay_ms: int = 1000
    timeout_seconds: int = 300
    quality_threshold: float = 0.85
    output_table: str = "processed_records"
    dead_letter_topic: str = "dlq.failed"
    processors: list[str] = field(default_factory=list)
    validators: list[str] = field(default_factory=list)


@dataclass
class PipelineMetrics:
    """Runtime metrics collected during pipeline execution."""
    pipeline_name: str
    total_records: int = 0
    succeeded: int = 0
    failed: int = 0
    retried: int = 0
    skipped_quality: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    throughput_per_sec: float = 0.0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
