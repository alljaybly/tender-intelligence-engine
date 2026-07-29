"""
TenderResult model — stores all extraction and processing outputs.
"""
from typing import Any, Dict, Optional


class TenderResult:
    """Persistent processing result linked to a tender via tender_id (job_id)."""
    TABLE_NAME = "tender_results"

    __slots__ = (
        "id", "tender_id", "raw_text", "sector", "sector_confidence",
        "duration_months", "locations_json", "workforce_json",
        "schedule_json", "boq_json", "boq_confidence", "pricing_json",
        "pricing_mode", "warnings_json", "evidence_json", "extraction_method",
        "pipeline_version", "created_at",
    )

    def __init__(
        self,
        id: int = 0,
        tender_id: str = "",
        raw_text: Optional[str] = None,
        sector: Optional[str] = None,
        sector_confidence: Optional[str] = None,
        duration_months: Optional[int] = None,
        locations_json: Optional[str] = None,
        workforce_json: Optional[str] = None,
        schedule_json: Optional[str] = None,
        boq_json: Optional[str] = None,
        boq_confidence: Optional[str] = None,
        pricing_json: Optional[str] = None,
        pricing_mode: Optional[str] = None,
        warnings_json: Optional[str] = None,
        evidence_json: Optional[str] = None,
        extraction_method: Optional[str] = None,
        pipeline_version: str = "v1",
        created_at: Optional[str] = None,
    ):
        self.id = id
        self.tender_id = tender_id
        self.raw_text = raw_text
        self.sector = sector
        self.sector_confidence = sector_confidence
        self.duration_months = duration_months
        self.locations_json = locations_json
        self.workforce_json = workforce_json
        self.schedule_json = schedule_json
        self.boq_json = boq_json
        self.boq_confidence = boq_confidence
        self.pricing_json = pricing_json
        self.pricing_mode = pricing_mode
        self.warnings_json = warnings_json
        self.evidence_json = evidence_json
        self.extraction_method = extraction_method
        self.pipeline_version = pipeline_version
        self.created_at = created_at

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}

    DDL = """
        CREATE TABLE IF NOT EXISTS tender_results (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id         TEXT NOT NULL,
            raw_text          TEXT,
            sector            TEXT,
            sector_confidence TEXT,
            duration_months   INTEGER,
            locations_json    TEXT,
            workforce_json    TEXT,
            schedule_json     TEXT,
            boq_json          TEXT,
            boq_confidence    TEXT,
            pricing_json      TEXT,
            pricing_mode      TEXT DEFAULT 'estimated',
            warnings_json     TEXT,
            evidence_json     TEXT,
            extraction_method TEXT,
            pipeline_version  TEXT DEFAULT 'v1',
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tender_id) REFERENCES tenders(job_id)
        );
        CREATE INDEX IF NOT EXISTS idx_tender_results_tender_id ON tender_results(tender_id);
    """