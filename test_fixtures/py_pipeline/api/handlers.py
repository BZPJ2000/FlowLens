"""API handlers — entry point that creates records and triggers pipeline."""
import time
import asyncio
from typing import Any
from dataclasses import asdict

from models.schemas import (
    RawRecord,
    PipelineConfig,
    PipelineMetrics,
    PipelineStatus,
    DataSource,
)
from pipeline.runner import PipelineRunner
from utils.helpers import generate_record_id, timestamp_to_iso


class IngestAPI:
    """Simulated API for data ingestion."""

    def __init__(self):
        self._runner: PipelineRunner | None = None
        self._request_count: int = 0

    def create_pipeline(self, name: str, source: DataSource) -> PipelineRunner:
        config = PipelineConfig(
            name=name,
            source=source,
            batch_size=50,
            quality_threshold=0.80,
            processors=["quality_filter", "normalizer", "enricher"],
            validators=["required_fields", "schema_check"],
        )
        self._runner = PipelineRunner(config)
        self._runner.register_default_processors()
        return self._runner

    def ingest_event(
        self,
        source: DataSource,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> RawRecord:
        """Ingest a single event — creates a RawRecord for the pipeline."""
        self._request_count += 1
        record_id = generate_record_id(source.value, payload)

        record = RawRecord(
            record_id=record_id,
            source=source,
            payload=payload,
            headers=headers or {},
            raw_size_bytes=len(str(payload).encode()),
            partition_key=f"pk_{self._request_count % 4}",
        )
        return record

    def ingest_batch(
        self,
        source: DataSource,
        events: list[dict[str, Any]],
    ) -> list[RawRecord]:
        """Ingest a batch of events."""
        return [self.ingest_event(source, event) for event in events]

    async def run_pipeline(
        self, pipeline_name: str, source: DataSource, events: list[dict[str, Any]]
    ) -> PipelineMetrics:
        """Full flow: create pipeline → ingest → process → return metrics."""
        runner = self.create_pipeline(pipeline_name, source)
        records = self.ingest_batch(source, events)

        metrics = await runner.run_batch(records)
        return metrics

    def get_status(self) -> dict[str, Any]:
        if not self._runner:
            return {"status": "idle", "requests": self._request_count}
        return {
            "requests": self._request_count,
            **self._runner.get_status_summary(),
        }


# Singleton
ingest_api = IngestAPI()
