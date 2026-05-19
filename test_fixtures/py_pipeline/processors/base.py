"""Base processor class — all concrete processors inherit from this."""
import time
from abc import ABC, abstractmethod
from typing import Any

from models.schemas import RawRecord, ProcessedRecord, PipelineConfig, DataSource


class BaseProcessor(ABC):
    """Abstract base for data processors.

    Each processor receives a RawRecord and returns a ProcessedRecord,
    optionally enriching/modifying the data in between.
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.processed_count: int = 0
        self.error_count: int = 0

    @abstractmethod
    def process(self, record: RawRecord) -> ProcessedRecord:
        """Transform a raw record into a processed record."""
        ...

    def pre_process(self, record: RawRecord) -> RawRecord:
        """Hook: called before process() — override in subclasses."""
        return record

    def post_process(self, record: ProcessedRecord) -> ProcessedRecord:
        """Hook: called after process() — override in subclasses."""
        return record

    def execute(self, record: RawRecord) -> ProcessedRecord:
        """Full execution: pre → process → post, with timing."""
        start = time.time()
        try:
            record = self.pre_process(record)
            result = self.process(record)
            result = self.post_process(result)
            result.processing_latency_ms = round((time.time() - start) * 1000, 2)
            result.transformed_by = self.__class__.__name__
            self.processed_count += 1
            return result
        except Exception as e:
            self.error_count += 1
            raise ProcessorError(
                self.__class__.__name__,
                record.record_id,
                str(e),
            )

    def get_stats(self) -> dict[str, int]:
        return {
            "processed": self.processed_count,
            "errors": self.error_count,
            "processor": self.__class__.__name__,
        }


class ProcessorError(Exception):
    def __init__(self, processor_name: str, record_id: str, message: str):
        self.processor_name = processor_name
        self.record_id = record_id
        super().__init__(f"[{processor_name}] Failed on {record_id}: {message}")
