"""Pipeline runner — orchestrates the full data processing flow."""
import time
import asyncio
from typing import Any, AsyncIterator

from models.schemas import (
    RawRecord,
    ProcessedRecord,
    ValidationResult,
    PipelineConfig,
    PipelineMetrics,
    PipelineStatus,
    DataSource,
)
from processors.base import BaseProcessor, ProcessorError
from processors.transform import FieldNormalizer, DataEnricher, QualityFilter
from utils.helpers import (
    generate_record_id,
    batch_records,
    calculate_latency_p99,
    merge_metrics,
    timestamp_to_iso,
)


class PipelineRunner:
    """Orchestrates the pipeline: ingest → process → validate → output."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.status = PipelineStatus.PENDING
        self.metrics = PipelineMetrics(pipeline_name=config.name)
        self._processors: list[BaseProcessor] = []
        self._validators: list[callable] = []

    def register_processor(self, processor: BaseProcessor) -> None:
        """Register a processor in the pipeline chain."""
        self._processors.append(processor)

    def register_default_processors(self) -> None:
        """Register the standard processor chain."""
        self.register_processor(QualityFilter(self.config))
        self.register_processor(FieldNormalizer(self.config))
        self.register_processor(DataEnricher(self.config))

    async def run_batch(self, raw_records: list[RawRecord]) -> PipelineMetrics:
        """Run the pipeline on a batch of records."""
        self.metrics.started_at = time.time()
        self.status = PipelineStatus.INGESTING
        self.metrics.total_records = len(raw_records)

        latencies: list[float] = []
        processed: list[ProcessedRecord] = []
        failed_record_ids: list[str] = []

        for batch in batch_records(raw_records, self.config.batch_size):
            self.status = PipelineStatus.PROCESSING

            for record in batch:
                try:
                    result = await self._process_chain(record)
                    processed.append(result)
                    latencies.append(result.processing_latency_ms)
                    self.metrics.succeeded += 1

                    if result.quality_score < self.config.quality_threshold:
                        self.metrics.skipped_quality += 1

                except ProcessorError as e:
                    self.metrics.failed += 1
                    failed_record_ids.append(e.record_id)

                    if self.metrics.failed <= self.config.max_retries:
                        self.metrics.retried += 1
                        self.status = PipelineStatus.RETRYING

        # Validate all processed records
        self.status = PipelineStatus.VALIDATING
        valid_count = 0
        for rec in processed:
            validation = await self._validate_record(rec)
            if validation.is_valid:
                valid_count += 1

        # Finalize metrics
        elapsed = time.time() - (self.metrics.started_at or time.time())
        self.metrics.avg_latency_ms = (
            sum(latencies) / len(latencies) if latencies else 0
        )
        self.metrics.p99_latency_ms = calculate_latency_p99(latencies)
        self.metrics.throughput_per_sec = (
            self.metrics.total_records / elapsed if elapsed > 0 else 0
        )
        self.metrics.finished_at = time.time()
        self.status = PipelineStatus.COMPLETED

        return self.metrics

    async def _process_chain(self, record: RawRecord) -> ProcessedRecord:
        """Run a single record through all registered processors in sequence."""
        result: Any = record
        for processor in self._processors:
            if isinstance(result, RawRecord):
                result = processor.execute(result)
            elif isinstance(result, ProcessedRecord):
                # Re-wrap as RawRecord for next processor
                rewrapped = RawRecord(
                    record_id=result.record_id,
                    source=result.source,
                    payload=result.data,
                    headers={"schema_version": str(result.schema_version)},
                )
                result = processor.execute(rewrapped)
        if isinstance(result, RawRecord):
            raise ProcessorError("PipelineRunner", record.record_id, "No processor produced output")
        return result

    async def _validate_record(self, record: ProcessedRecord) -> ValidationResult:
        """Run validation checks on a processed record."""
        checks_passed = 0
        checks_failed = 0
        failures: list[dict[str, str]] = []

        # Required field check
        required_field_checks = [
            "user_id" in record.data,
            bool(record.data.get("event_type")),
            record.quality_score >= self.config.quality_threshold,
        ]
        for check in required_field_checks:
            if check:
                checks_passed += 1
            else:
                checks_failed += 1
                failures.append({"check": "required_fields", "message": "Missing required field"})

        return ValidationResult(
            record_id=record.record_id,
            is_valid=checks_failed == 0,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            failures=failures,
        )

    def get_status_summary(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "metrics": {
                "total": self.metrics.total_records,
                "succeeded": self.metrics.succeeded,
                "failed": self.metrics.failed,
                "throughput": f"{self.metrics.throughput_per_sec:.1f}/s",
            },
            "started": timestamp_to_iso(self.metrics.started_at or 0),
            "finished": timestamp_to_iso(self.metrics.finished_at or 0),
        }
