"""
Pydantic schemas for Bill of Quantities (BOQ) Engine v2.

Supports:
- Table detection metadata
- Column mapping
- Row-level evidence (page, bbox, confidence)
- Hierarchy detection (sections, subsections)
- Validation results
- Table rejection reasons
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BOQItemEvidence(BaseModel):
    """Evidence trail for a single extracted BOQ row."""
    page: Optional[int] = Field(default=None, description="Page number where row was found")
    bbox: Optional[str] = Field(default=None, description="Bounding box coordinates (x0,y0,x1,y1)")
    confidence: float = Field(default=0.0, description="Extraction confidence 0.0-1.0")
    source_text: str = Field(default="", description="Raw text from document")
    extraction_method: str = Field(default="unknown", description="How this row was extracted")


class BOQItem(BaseModel):
    """A single line item extracted from a BOQ table."""
    item_no: Optional[str] = Field(default=None, description="Item number / reference")
    line_number: Optional[str] = Field(default=None, description="Original line number or row identifier")
    description: str = Field(default="", description="Item description / scope of work")
    specification: Optional[str] = Field(default=None, description="Technical specification text")
    quantity: Optional[float] = Field(default=None, description="Measured quantity")
    unit: Optional[str] = Field(default=None, description="Unit of measure (e.g. m², each, hour, lump sum)")
    rate: Optional[float] = Field(default=None, description="Unit rate")
    amount: Optional[float] = Field(default=None, description="Extended amount (qty × rate)")
    currency: Optional[str] = Field(default=None, description="ISO 4217 currency code if detected")
    section: Optional[str] = Field(default=None, description="Section heading this item belongs to")
    subsection: Optional[str] = Field(default=None, description="Subsection heading this item belongs to")
    trade_discipline: Optional[str] = Field(default=None, description="Deterministically classified trade discipline")
    notes: Optional[str] = Field(default=None, description="Notes or footnotes")
    is_subtotal: bool = Field(default=False, description="True if this row is a subtotal/section total")
    is_total: bool = Field(default=False, description="True if this row is a grand total")
    is_section_header: bool = Field(default=False, description="True if this row is a section/group header")
    hierarchy_level: Optional[int] = Field(default=None, description="Indentation/hierarchy level (0=top)")
    parent_item_no: Optional[str] = Field(default=None, description="Parent item reference when hierarchy is detected")
    duplicate_of: Optional[str] = Field(default=None, description="Duplicate row marker when a matching row already exists")
    evidence: BOQItemEvidence = Field(default_factory=BOQItemEvidence, description="Extraction evidence trail")

    class Config:
        json_schema_extra = {
            "example": {
                "item_no": "1.1",
                "description": "Supply and install 50mm diameter PVC pipe",
                "specification": "Class 6, SANS 966 compliant",
                "quantity": 150.0,
                "unit": "m",
                "rate": 85.50,
                "amount": 12825.00,
                "currency": "ZAR",
                "section": "Preliminaries",
                "hierarchy_level": 0,
                "evidence": {
                    "page": 3,
                    "bbox": "72.0,450.0,540.0,460.0",
                    "confidence": 0.95,
                    "source_text": "1.1  Supply PVC pipe  150.00  m  85.50  12825.00",
                    "extraction_method": "pdfplumber_tables",
                }
            }
        }


class BOQColumnMapping(BaseModel):
    """How columns were mapped for a detected BOQ table."""
    item_no: Optional[int] = None
    description: Optional[int] = None
    specification: Optional[int] = None
    quantity: Optional[int] = None
    unit: Optional[int] = None
    rate: Optional[int] = None
    amount: Optional[int] = None
    currency: Optional[int] = None
    section: Optional[int] = None
    notes: Optional[int] = None
    confidence: float = Field(default=0.0, description="Confidence in column mapping 0.0-1.0")


class BOQTableMetadata(BaseModel):
    """Metadata about a detected BOQ table."""
    page: int = Field(..., description="Page number")
    bbox: Optional[str] = Field(default=None, description="Bounding box on page")
    columns_mapped: int = Field(default=0, description="Number of columns successfully mapped")
    rows_extracted: int = Field(default=0, description="Number of data rows extracted")
    rows_rejected: int = Field(default=0, description="Number of rows rejected as non-BOQ")
    hierarchy_levels: int = Field(default=0, description="Number of hierarchy levels detected")
    mapping: Optional[BOQColumnMapping] = None


class BOQTableRejection(BaseModel):
    """Why a detected table was rejected (not a BOQ table)."""
    page: int = Field(..., description="Page number")
    reason: str = Field(..., description="Why this table was rejected")
    evidence: str = Field(default="", description="Evidence text from the table")
    table_type: str = Field(default="unknown", description="What the table appeared to be")
    header_text: str = Field(default="", description="First row of the rejected table")


class BOQValidationResult(BaseModel):
    """Validation results for BOQ extraction."""
    quantity_valid: bool = Field(default=False, description="Quantities passed validation")
    unit_valid: bool = Field(default=False, description="Units passed validation")
    currency_valid: bool = Field(default=False, description="Currency evidence found")
    total_valid: bool = Field(default=False, description="Totals passed validation")
    items_with_quantities: int = Field(default=0)
    items_with_rates: int = Field(default=0)
    items_with_amounts: int = Field(default=0)
    items_with_currency: int = Field(default=0)
    quantity_issues: List[str] = Field(default_factory=list)
    unit_issues: List[str] = Field(default_factory=list)
    currency_issues: List[str] = Field(default_factory=list)
    total_issues: List[str] = Field(default_factory=list)


class BOQTotals(BaseModel):
    """Aggregated totals extracted from a BOQ."""
    subtotal: Optional[float] = Field(default=None, description="Sum of all line item amounts")
    total_before_vat: Optional[float] = Field(default=None, description="Total amount excluding VAT")
    vat: Optional[float] = Field(default=None, description="VAT amount (if separately stated)")
    total_incl_vat: Optional[float] = Field(default=None, description="Total amount including VAT")
    page_count: int = Field(default=0, description="Number of pages processed")
    calculated_from_items: bool = Field(default=False, description="True if totals were calculated from line items")


class BOQResult(BaseModel):
    """Full BOQ Engine v2 extraction result."""
    filename: str = Field(..., description="Source PDF filename")
    page_count: int = Field(..., description="Number of pages processed")
    items: List[BOQItem] = Field(default_factory=list, description="Extracted BOQ line items")
    totals: BOQTotals = Field(default_factory=BOQTotals, description="Aggregated totals")
    extraction_method: str = Field(
        ..., description="Method used: boq_engine_v2, fallback_text"
    )
    confidence: str = Field(..., description="Overall confidence: High, Medium, Low")

    # BOQ Engine v2 metadata
    tables_detected: int = Field(default=0, description="Number of potential BOQ tables found")
    tables_accepted: int = Field(default=0, description="Number of tables accepted as BOQ")
    tables_rejected: int = Field(default=0, description="Number of tables rejected as non-BOQ")
    rejected_tables: List[BOQTableRejection] = Field(default_factory=list, description="Why each table was rejected")
    table_metadata: List[BOQTableMetadata] = Field(default_factory=list, description="Metadata for accepted tables")
    hierarchy_levels: int = Field(default=0, description="Number of hierarchy levels detected")
    validation: BOQValidationResult = Field(default_factory=BOQValidationResult, description="Validation results")
    warnings: List[str] = Field(default_factory=list, description="Warnings or issues encountered during extraction")

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "tender_boq_sample.pdf",
                "page_count": 3,
                "items": [],
                "extraction_method": "boq_engine_v2",
                "confidence": "High",
                "tables_detected": 4,
                "tables_accepted": 2,
                "tables_rejected": 2,
                "warnings": [],
            }
        }


class BOQExtractRequest(BaseModel):
    """Request payload for BOQ extraction from an uploaded PDF."""
    extract_totals: bool = Field(default=True, description="Whether to attempt extracting grand totals")
    page_range: Optional[str] = Field(
        default=None,
        description="Page range to process, e.g. '1-3' or '1,3,5'. Processes all pages if None.",
    )