"""
ProcessingEvent model — per-stage audit trail for tender processing.
"""
from typing import Any, Dict, Optional


class ProcessingEvent:
    """An individual stage event in the tender processing pipeline."""
    TABLE_NAME = "processing_events"

    __slots__ = (
        "id", "tender_id", "stage", "status", "details", "duration_ms", "created_at",
    )

    def __init__(
        self,
        id: int = 0,
        tender_id: str = "",
        stage: str = "",
        status: str = "pending",
        details: Optional[str] = None,
        duration_ms: Optional[int] = None,
        created_at: Optional[str] = None,
    ):
        self.id = id
        self.tender_id = tender_id
        self.stage = stage
        self.status = status
        self.details = details
        self.duration_ms = duration_ms
        self.created_at = created_at

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}

    DDL = """
        CREATE TABLE IF NOT EXISTS processing_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id   TEXT NOT NULL,
            stage       TEXT NOT NULL,
            status      TEXT DEFAULT 'pending',
            details     TEXT,
            duration_ms INTEGER,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tender_id) REFERENCES tenders(job_id)
        );
        CREATE INDEX IF NOT EXISTS idx_processing_events_tender_id ON processing_events(tender_id);
        CREATE INDEX IF NOT EXISTS idx_processing_events_stage ON processing_events(stage);
    """