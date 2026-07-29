"""
Pydantic schemas for tender upload and processing pipeline.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FieldEvidenceEntry(BaseModel):
    """Evidence for a single extracted field exposed by the processing API."""
    field_name: str = Field(..., description="Human-readable field name")
    value: Optional[Any] = Field(default=None, description="Extracted value from existing pipeline data, or None if not found")
    confidence: Optional[str] = Field(default=None, description="Confidence label for the extracted value")
    page_number: Optional[int] = Field(default=None, description="Page number where evidence was found")
    section: Optional[str] = Field(default=None, description="Document section or logical source area")
    paragraph_or_sentence: Optional[str] = Field(default=None, description="Exact paragraph or sentence supporting the value")
    detection_method: Optional[str] = Field(default=None, description="Deterministic detection method used")
    source_category: Optional[str] = Field(default=None, description="Source category such as title, body_text, boq, table, contract_value")
    recommended_action_if_missing: Optional[str] = Field(default=None, description="Recommended follow-up if the field was not found")


class ProcessingEvidence(BaseModel):
    """Structured evidence payload returned with processing results."""
    fields: Dict[str, FieldEvidenceEntry] = Field(default_factory=dict, description="Evidence entries keyed by stable field identifier")
    generated_from_existing_extractions: bool = Field(default=True, description="True when evidence was derived from existing pipeline outputs without duplicate scanning")
    version: str = Field(default="v1", description="Evidence payload version")


class DocumentSectionEvidence(BaseModel):
    """Detected document section with deterministic evidence."""
    section_type: str = Field(..., description="Normalized section type identifier")
    heading: str = Field(..., description="Detected heading text")
    page: Optional[int] = Field(default=None, description="Detected page number")
    confidence: Optional[str] = Field(default=None, description="Confidence label for the section detection")
    evidence: Optional[str] = Field(default=None, description="Supporting heading or sentence fragment")


class ProcessingJobCreate(BaseModel):
    """Returned immediately after upload."""
    job_id: str = Field(..., description="Unique job identifier (UUID4 hex)")
    status: str = Field("queued", description="Initial job status")


class ProcessingJobStatus(BaseModel):
    """Job status response for GET /api/process/status/{job_id}."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current status: queued, processing, extracting, boq_analysis, pricing, completed, failed")
    progress: Optional[str] = Field(default=None, description="Current stage description")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp of job creation")
    updated_at: Optional[str] = Field(default=None, description="ISO timestamp of last update")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4e5f6...",
                "status": "processing",
                "progress": "extracting_document",
                "created_at": "2026-05-13T12:00:00",
                "updated_at": "2026-05-13T12:01:30",
                "error_message": None,
            }
        }


class ExtractedBOQItem(BaseModel):
    """A single BOQ line item as returned in the result."""
    item_no: Optional[str] = None
    line_number: Optional[str] = None
    description: str = ""
    quantity: Optional[float] = None
    unit: Optional[str] = None
    rate: Optional[float] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    section: Optional[str] = None
    subsection: Optional[str] = None
    trade_discipline: Optional[str] = None
    hierarchy_level: Optional[int] = None
    parent_item_no: Optional[str] = None
    is_subtotal: bool = False
    is_total: bool = False
    duplicate_of: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)


class ProcessingResult(BaseModel):
    """Full processing result for GET /api/process/result/{job_id}.

    Supports three statuses:
      - completed:      All stages finished successfully
      - partial_success: Core stages (text extraction) succeeded,
                         but non-critical stages (e.g. pricing) failed.
                         Result includes all successfully extracted data
                         plus completed_stages / failed_stages / warnings.
      - failed:         Pipeline crashed completely. No extraction data.
    """
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Final status: completed, partial_success, or failed")
    filename: Optional[str] = Field(default=None, description="Original uploaded filename")

    # Stage tracking (present for completed and partial_success)
    completed_stages: List[str] = Field(default_factory=list,
        description="List of stage names that completed successfully")
    failed_stages: List[str] = Field(default_factory=list,
        description="List of stage names that failed")

    # Stage 1: Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="File metadata (size, pages, etc.)")

    # Stage 2: Document text
    full_text: Optional[str] = Field(default=None, description="Extracted full document text")
    text_length: Optional[int] = Field(default=None, description="Length of extracted text")

    # Stage 3: Extracted entities
    detected_sector: Optional[str] = Field(default=None, description="Detected industry sector")
    detected_duration_months: Optional[int] = Field(default=None, description="Detected contract duration in months")
    detected_locations: List[str] = Field(default_factory=list, description="Detected geographic locations")
    detected_workforce: Dict[str, Any] = Field(default_factory=dict, description="Detected workforce requirements")
    detected_schedule: Dict[str, Any] = Field(default_factory=dict, description="Detected schedule/timeline")
    detected_currency: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Detected currency with evidence. "
            "Never defaults to ZAR. "
            "Contains: currency_code, currency_symbol, currency_name, "
            "confidence, evidence, source_pages, source_text. "
            "Null/None if no reliable currency evidence found."
        ),
    )
    procurement_entities: Dict[str, Any] = Field(default_factory=dict, description="Deterministic procurement intelligence entity extraction")
    procurement_context: Dict[str, Any] = Field(default_factory=dict, description="Deterministic procurement context such as country, jurisdiction, tender type, procedure, language, and funding source")
    document_sections: List[DocumentSectionEvidence] = Field(default_factory=list, description="Detected document structure sections with evidence and confidence")
    work_category_filter: Dict[str, Any] = Field(
        default_factory=dict,
        description="Deterministic category filter applied before BOQ/workforce inference",
    )

    # Stage 4: BOQ items
    boq_items: List[ExtractedBOQItem] = Field(default_factory=list, description="Extracted BOQ line items")
    boq_confidence: Optional[str] = Field(default=None, description="BOQ extraction confidence")
    boq_summary: Dict[str, Any] = Field(default_factory=dict, description="Deterministic BOQ summary and totals")
    trade_summary: Dict[str, Any] = Field(default_factory=dict, description="Trade discipline grouping summary")
    cost_distribution: Dict[str, Any] = Field(default_factory=dict, description="Amount distribution by trade/section")
    extraction_confidence: Optional[str] = Field(default=None, description="Alias of BOQ extraction confidence for report integrations")
    missing_information: List[str] = Field(default_factory=list, description="Missing BOQ information or validation issues")

    # Stage 5: Pricing
    pricing_result: Optional[Dict[str, Any]] = Field(default=None, description="Pricing engine output")
    pricing_status: Optional[str] = Field(default=None,
        description="Pricing status: completed, failed, or None if not attempted")
    pricing_unavailable_reason: Optional[str] = Field(default=None,
        description="Reason pricing was unavailable or failed")

    # Forensic Compliance Engine: New Features
    win_probability_index: Optional[float] = Field(default=None, description="Win Probability Index (0-100%)")
    win_probability_explanation: Optional[str] = Field(default=None, description="One-sentence explanation of win probability calculation")
    critical_traps: List[str] = Field(default_factory=list, description="List of critical disqualification traps (prefixed with [CRITICAL_TRAP])")
    compliance_gaps: List[str] = Field(default_factory=list, description="Compliance gaps for a standard SME profile")

    # Stage 6: Final combined output
    evidence: ProcessingEvidence = Field(default_factory=ProcessingEvidence, description="Structured evidence for key extracted fields")
    warnings: List[str] = Field(default_factory=list, description="Any warnings encountered")
    extraction_method: Optional[str] = Field(default=None, description="Method used for primary extraction")
    pipeline_version: Optional[str] = Field(default="v1", description="Pipeline version identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4...",
                "status": "completed",
                "filename": "tender_doc.pdf",
                "completed_stages": [
                    "metadata_extraction", "text_extraction", "entity_extraction",
                    "boq_analysis", "pricing_calculation", "finalisation"
                ],
                "failed_stages": [],
                "metadata": {"size_bytes": 245000, "page_count": 5, "file_type": "pdf"},
                "detected_sector": "cleaning",
                "detected_duration_months": 12,
                "detected_locations": ["gauteng"],
                "boq_items": [
                    {"item_no": "1.1", "description": "Cleaning services", "quantity": 150.0, "unit": "hrs", "rate": 85.0, "amount": 12750.0}
                ],
                "pricing_result": {"total_monthly": 45322.08, "confidence": "High"},
                "pricing_status": "completed",
                "warnings": [],
            }
        }


class ProcessUploadResponse(BaseModel):
    """Response after successful upload."""
    job_id: str = Field(..., description="Unique job identifier (UUID4 hex)")
    status: str = Field("queued", description="Initial status")
    filename: str = Field(..., description="Original filename")
    message: str = Field("File uploaded and queued for processing", description="User-friendly message")


class RetryRequest(BaseModel):
    """Request body for POST /api/process/retry/{job_id}."""
    stages: List[str] = Field(
        ...,
        description=(
            "List of stage names to retry. "
            "Valid stages: metadata_extraction, text_extraction, "
            "entity_extraction, boq_analysis, pricing_calculation. "
            "Dependencies are resolved automatically."
        ),
        examples=[["pricing_calculation"], ["text_extraction", "boq_analysis"]],
    )


class RetryResponse(BaseModel):
    """Response from a retry operation."""
    job_id: str = Field(..., description="The job ID that was retried")
    status: str = Field(..., description="Final status after retry: completed, partial_success, or failed")
    retry_count: int = Field(default=0, description="Total retry count for this job")
    retried_stages: List[str] = Field(default_factory=list, description="Stages that were re-executed")
    last_retry_at: Optional[str] = Field(default=None, description="ISO timestamp of last retry")
    stage_failures: List[Dict[str, Any]] = Field(default_factory=list, description="Structured failure metadata for failed stages")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4...",
                "status": "partial_success",
                "retry_count": 1,
                "retried_stages": ["text_extraction", "entity_extraction", "pricing_calculation"],
                "last_retry_at": "2026-05-16T12:00:00",
                "stage_failures": [
                    {
                        "stage": "pricing_calculation",
                        "reason": "missing_sector",
                        "recoverable": True,
                        "retryable": True,
                        "description": "Pricing could not be calculated."
                    }
                ],
            }
        }


class ProcessingHistoryItem(BaseModel):
    """
    Lightweight history summary for a single processing job.
    
    Returned by GET /api/process/history.
    Designed to survive partial/missing data — all fields are optional
    with safe defaults so the endpoint never crashes on corrupt records.
    """
    job_id: str = Field(..., description="Unique job identifier")
    filename: Optional[str] = Field(default=None, description="Original uploaded filename")
    status: str = Field("unknown", description="Job status")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp of creation")
    updated_at: Optional[str] = Field(default=None, description="ISO timestamp of last update")
    sector: Optional[str] = Field(default=None, description="Detected sector from processed result")
    confidence: Optional[str] = Field(default=None, description="Extraction confidence level")
    warnings_count: int = Field(default=0, description="Number of warnings from processing")
    has_pricing: bool = Field(default=False, description="Whether pricing data is available")
    error_message: Optional[str] = Field(default=None, description="Error message if job failed")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4...",
                "filename": "tender_doc.pdf",
                "status": "completed",
                "created_at": "2026-05-13T12:00:00",
                "updated_at": "2026-05-13T12:02:30",
                "sector": "cleaning",
                "confidence": "High",
                "warnings_count": 0,
                "has_pricing": True,
                "error_message": None,
            }
        }
