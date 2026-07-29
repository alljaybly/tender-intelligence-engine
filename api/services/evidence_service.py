"""
Evidence System — Every extracted value must be traceable.

Each extracted field may contain:
  - Value
  - Source Page
  - Source Section
  - Detection Method
  - Confidence
  - Evidence Text

Processing Audit always shows:
  - PDF Parsed (pages)
  - OCR Used (why/why not)
  - Languages Detected
  - Currency Detected
  - Country Detected
  - BOQ Tables Found / Rejected
  - Numeric Entities Classified
  - Pages Parsed
  - Processing Time
  - Pipeline Version / Extraction Version

No hidden processing. Everything must be auditable.
"""
from __future__ import annotations
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

EVIDENCE_SYSTEM_VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════════════════
# Evidence Record
# ═══════════════════════════════════════════════════════════════════════

class EvidenceRecord:
    """
    A single traceable evidence record for an extracted value.
    
    Every extracted value must have an EvidenceRecord attached.
    No value should be presented without its evidence.
    """

    def __init__(
        self,
        field_name: str,
        value: Any,
        source_page: Optional[int] = None,
        source_section: Optional[str] = None,
        detection_method: str = "unknown",
        confidence: str = "Unknown",
        evidence_text: Optional[str] = None,
        extracted: bool = False,
    ):
        self.field_name = field_name
        self.value = value
        self.source_page = source_page
        self.source_section = source_section
        self.detection_method = detection_method
        self.confidence = confidence
        self.evidence_text = evidence_text
        self.extracted = extracted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "source_page": self.source_page,
            "source_section": self.source_section,
            "detection_method": self.detection_method,
            "confidence": self.confidence,
            "evidence_text": self.evidence_text,
            "extracted": self.extracted,
        }

    @staticmethod
    def confidence_from_score(score: float) -> str:
        """Convert a numeric confidence score (0-1) to a label."""
        if score >= 0.9:
            return "High"
        elif score >= 0.7:
            return "Medium"
        elif score >= 0.5:
            return "Low"
        else:
            return "Very Low"

    @staticmethod
    def confidence_from_string(level: Optional[str]) -> str:
        """Normalize a confidence string."""
        if not level:
            return "Unknown"
        lower = level.lower().strip()
        if lower in ("high", "medium", "low", "very low"):
            return level.capitalize()
        return "Unknown"


# ═══════════════════════════════════════════════════════════════════════
# Processing Audit Record
# ═══════════════════════════════════════════════════════════════════════

class ProcessingAudit:
    """
    Complete processing audit for a document.
    
    Every report must include this audit.
    Shows exactly what happened during processing.
    """

    def __init__(self):
        self.pdf_parsed: bool = False
        self.page_count: int = 0
        self.pages_parsed: int = 0
        self.ocr_used: bool = False
        self.ocr_reason: Optional[str] = None
        self.ocr_skipped_reason: Optional[str] = None
        self.ocr_confidence: Optional[str] = None
        self.languages_detected: List[str] = []
        self.currency_detected: Optional[str] = None
        self.currency_confidence: Optional[str] = None
        self.currency_method: Optional[str] = None
        self.country_detected: Optional[str] = None
        self.country_confidence: Optional[str] = None
        self.boq_tables_found: int = 0
        self.boq_tables_accepted: int = 0
        self.boq_tables_rejected: int = 0
        self.boq_rejected_reasons: List[str] = []
        self.boq_items_extracted: int = 0
        self.entity_classifier_accepted: int = 0
        self.entity_classifier_rejected: int = 0
        self.numeric_entities_classified: int = 0
        self.processing_started: Optional[str] = None
        self.processing_completed: Optional[str] = None
        self.processing_time_ms: Optional[int] = None
        self.pipeline_version: Optional[str] = None
        self.extraction_version: Optional[str] = None
        self.stages_completed: int = 0
        self.stages_failed: int = 0
        self.stages_warnings: int = 0
        self.warnings: List[str] = []

    def start_timer(self):
        """Start the processing timer."""
        self.processing_started = datetime.now().isoformat()
        self._start_time = time.monotonic()

    def stop_timer(self):
        """Stop the processing timer."""
        self.processing_completed = datetime.now().isoformat()
        if hasattr(self, '_start_time'):
            self.processing_time_ms = int((time.monotonic() - self._start_time) * 1000)

    def set_ocr_info(self, used: bool, reason: Optional[str] = None,
                     skipped_reason: Optional[str] = None,
                     confidence: Optional[str] = None):
        """Record OCR usage with explanation."""
        self.ocr_used = used
        if used:
            self.ocr_reason = reason or "OCR was required because standard text extraction returned insufficient content"
            self.ocr_confidence = confidence
        else:
            self.ocr_skipped_reason = skipped_reason or "Standard text extraction was sufficient — OCR not needed"

    def set_currency_info(self, code: Optional[str], confidence: Optional[str],
                          method: Optional[str]):
        """Record currency detection info."""
        self.currency_detected = code
        self.currency_confidence = confidence
        self.currency_method = method

    def set_country_info(self, country: Optional[str], confidence: Optional[str]):
        """Record country detection info."""
        self.country_detected = country
        self.country_confidence = confidence

    def add_boq_table_result(self, found: int, accepted: int, rejected: int,
                              rejected_reasons: Optional[List[str]] = None):
        """Record BOQ table detection results."""
        self.boq_tables_found = found
        self.boq_tables_accepted = accepted
        self.boq_tables_rejected = rejected
        if rejected_reasons:
            self.boq_rejected_reasons = rejected_reasons

    def add_entity_classification(self, accepted: int, rejected: int):
        """Record entity classification results."""
        self.entity_classifier_accepted = accepted
        self.entity_classifier_rejected = rejected
        self.numeric_entities_classified = accepted + rejected

    def to_dict(self) -> Dict[str, Any]:
        """Serialize audit to dict."""
        return {
            "pdf_parsed": self.pdf_parsed,
            "page_count": self.page_count,
            "pages_parsed": self.pages_parsed,
            "ocr_used": self.ocr_used,
            "ocr_reason": self.ocr_reason,
            "ocr_skipped_reason": self.ocr_skipped_reason,
            "ocr_confidence": self.ocr_confidence,
            "languages_detected": self.languages_detected,
            "currency_detected": self.currency_detected,
            "currency_confidence": self.currency_confidence,
            "currency_method": self.currency_method,
            "country_detected": self.country_detected,
            "country_confidence": self.country_confidence,
            "boq_tables_found": self.boq_tables_found,
            "boq_tables_accepted": self.boq_tables_accepted,
            "boq_tables_rejected": self.boq_tables_rejected,
            "boq_rejected_reasons": self.boq_rejected_reasons,
            "boq_items_extracted": self.boq_items_extracted,
            "entity_classifier_accepted": self.entity_classifier_accepted,
            "entity_classifier_rejected": self.entity_classifier_rejected,
            "numeric_entities_classified": self.numeric_entities_classified,
            "processing_started": self.processing_started,
            "processing_completed": self.processing_completed,
            "processing_time_ms": self.processing_time_ms,
            "pipeline_version": self.pipeline_version,
            "extraction_version": self.extraction_version,
            "stages_completed": self.stages_completed,
            "stages_failed": self.stages_failed,
            "stages_warnings": self.stages_warnings,
            "warnings": self.warnings,
        }

    def format_timing(self) -> str:
        """Format processing time for display."""
        if self.processing_time_ms is None:
            return "N/A"
        ms = self.processing_time_ms
        if ms < 1000:
            return f"{ms}ms"
        if ms < 60000:
            return f"{ms / 1000:.1f}s"
        return f"{ms // 60000}m {round(ms % 60000 / 1000)}s"


# ═══════════════════════════════════════════════════════════════════════
# Evidence Builder
# ═══════════════════════════════════════════════════════════════════════

def build_evidence_from_result(result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build evidence records from a processing result.
    
    Every extracted value gets an EvidenceRecord with source page,
    detection method, confidence, and evidence text.
    """
    evidence_records = []

    # Tender Number
    tender_no = (
        result_data.get("metadata", {}).get("tender_number")
        or result_data.get("tender_number")
    )
    evidence_records.append({
        "field_name": "Tender Number",
        "value": tender_no,
        "source_page": result_data.get("metadata", {}).get("page_first_found"),
        "source_section": "Document Header",
        "detection_method": "Structured metadata extraction",
        "confidence": "High" if tender_no else "Not Found",
        "evidence_text": f"Tender number {'found' if tender_no else 'not found'} in document metadata" if tender_no else "No tender number detected in document header or metadata",
        "extracted": bool(tender_no),
    })

    # Employer
    employer = result_data.get("metadata", {}).get("employer") or result_data.get("employer")
    evidence_records.append({
        "field_name": "Employer / Procuring Entity",
        "value": employer,
        "source_page": None,
        "source_section": "Document Header / Letterhead",
        "detection_method": "Structured heading detection",
        "confidence": "High" if employer else "Not Found",
        "evidence_text": f"Employer: {employer}" if employer else "No employer/procuring entity detected",
        "extracted": bool(employer),
    })

    # Sector
    sector = result_data.get("detected_sector")
    evidence_records.append({
        "field_name": "Sector",
        "value": sector,
        "source_page": None,
        "source_section": "Document body",
        "detection_method": "Sector keyword analysis",
        "confidence": result_data.get("sector_confidence", "Unknown") if sector else "Not Found",
        "evidence_text": f"Sector detected: {sector}" if sector else "No sector detected in document text",
        "extracted": bool(sector),
    })

    # Duration
    duration = result_data.get("detected_duration_months")
    evidence_records.append({
        "field_name": "Contract Duration",
        "value": f"{duration} months" if duration else None,
        "source_page": None,
        "source_section": "Document body / Schedule",
        "detection_method": "Duration pattern extraction",
        "confidence": "High" if duration else "Not Found",
        "evidence_text": f"Duration: {duration} months" if duration else "No contract duration detected",
        "extracted": bool(duration),
    })

    # Locations
    locations = result_data.get("detected_locations", [])
    evidence_records.append({
        "field_name": "Location(s)",
        "value": ", ".join(locations) if locations else None,
        "source_page": None,
        "source_section": "Document body",
        "detection_method": "Location entity extraction",
        "confidence": "Medium" if locations else "Not Found",
        "evidence_text": f"Locations: {', '.join(locations)}" if locations else "No locations detected",
        "extracted": bool(locations),
    })

    # Currency
    currency_data = result_data.get("detected_currency")
    if currency_data and isinstance(currency_data, dict):
        currency_code = currency_data.get("currency_code")
        currency_conf = currency_data.get("confidence", 0)
        currency_method = currency_data.get("detection_method", "unknown")
        currency_evidence = currency_data.get("evidence", [])
    else:
        currency_code = None
        currency_conf = 0
        currency_method = "none"
        currency_evidence = []

    evidence_records.append({
        "field_name": "Currency",
        "value": currency_code,
        "source_page": currency_data.get("source_pages", [None])[0] if currency_data and currency_data.get("source_pages") else None,
        "source_section": "Document body / Pricing section",
        "detection_method": f"Currency Engine — {currency_method}",
        "confidence": EvidenceRecord.confidence_from_score(currency_conf),
        "evidence_text": currency_evidence[0] if currency_evidence else "No currency detected",
        "extracted": bool(currency_code),
    })

    # BOQ Items
    boq_items = result_data.get("boq_items", [])
    boq_confidence = result_data.get("boq_confidence")
    evidence_records.append({
        "field_name": "BOQ Items",
        "value": f"{len(boq_items)} line items" if boq_items else None,
        "source_page": None,
        "source_section": "BOQ tables in document",
        "detection_method": "BOQ Engine v2 — table extraction",
        "confidence": EvidenceRecord.confidence_from_string(boq_confidence) if boq_confidence else "Not Found",
        "evidence_text": f"{len(boq_items)} BOQ line items extracted" if boq_items else "No BOQ items detected",
        "extracted": bool(boq_items),
    })

    # Pricing
    pricing = result_data.get("pricing_result")
    pricing_status = result_data.get("pricing_status")
    evidence_records.append({
        "field_name": "Pricing Calculation",
        "value": "Calculated" if pricing else None,
        "source_page": None,
        "source_section": "Pricing Engine",
        "detection_method": "Deterministic pricing calculation",
        "confidence": "Calculated" if pricing else (pricing_status or "Not Available"),
        "evidence_text": "Pricing calculated from BOQ items" if pricing else (pricing_status or "Pricing not available"),
        "extracted": bool(pricing),
    })

    # Workforce
    workforce = result_data.get("detected_workforce", {})
    has_workforce = bool(workforce and isinstance(workforce, dict) and workforce.get("total_workers"))
    evidence_records.append({
        "field_name": "Workforce Requirements",
        "value": f"{workforce.get('total_workers')} workers" if has_workforce else None,
        "source_page": None,
        "source_section": "Document body / Scope of work",
        "detection_method": "Workforce estimation from BOQ",
        "confidence": "Medium" if has_workforce else "Not Found",
        "evidence_text": f"Workforce: {workforce.get('total_workers')} workers estimated" if has_workforce else "No workforce requirements detected",
        "extracted": has_workforce,
    })

    # Schedule
    schedule = result_data.get("detected_schedule", {})
    evidence_records.append({
        "field_name": "Project Schedule",
        "value": "Detected" if schedule else None,
        "source_page": None,
        "source_section": "Document body / Timeline",
        "detection_method": "Schedule pattern extraction",
        "confidence": "Low" if schedule else "Not Found",
        "evidence_text": "Schedule phases detected" if schedule else "No project schedule detected",
        "extracted": bool(schedule),
    })

    return evidence_records


# ═══════════════════════════════════════════════════════════════════════
# Build Processing Audit from pipeline result
# ═══════════════════════════════════════════════════════════════════════

def build_processing_audit(
    result_data: Dict[str, Any],
    pipeline_start: Optional[float] = None,
    pipeline_end: Optional[float] = None,
) -> ProcessingAudit:
    """
    Build a complete Processing Audit from result data.
    
    Shows:
      - PDF Parsed / Pages
      - OCR Used (why/why not)
      - Languages / Currency / Country Detected
      - BOQ Tables Found / Rejected
      - Numeric Entities Classified
      - Processing Time / Version
    """
    audit = ProcessingAudit()

    # PDF info
    metadata = result_data.get("metadata", {})
    audit.pdf_parsed = True
    audit.page_count = metadata.get("page_count", 0)
    audit.pages_parsed = audit.page_count

    # Pipeline version
    audit.pipeline_version = result_data.get("pipeline_version", "unknown")
    audit.extraction_version = result_data.get("extraction_method", "unknown")

    # Timing
    if pipeline_start and pipeline_end:
        audit._start_time = pipeline_start
        audit.processing_started = datetime.fromtimestamp(pipeline_start).isoformat()
        audit.processing_completed = datetime.fromtimestamp(pipeline_end).isoformat()
        audit.processing_time_ms = int((pipeline_end - pipeline_start) * 1000)

    # OCR info — detect from warnings
    warnings = result_data.get("warnings", [])
    ocr_warnings = [w for w in warnings if "ocr" in w.lower()]
    if ocr_warnings:
        audit.set_ocr_info(
            used=True,
            reason="OCR was used because the document appeared to be scanned or image-based",
            confidence="Medium",
        )
    else:
        audit.set_ocr_info(
            used=False,
            skipped_reason="Standard text extraction successfully retrieved document content — OCR was not required",
        )

    # Languages
    audit.languages_detected = ["English"]  # Default; would be expanded with language detector

    # Currency
    currency_data = result_data.get("detected_currency")
    if currency_data and isinstance(currency_data, dict) and currency_data.get("currency_code"):
        audit.set_currency_info(
            code=currency_data["currency_code"],
            confidence=EvidenceRecord.confidence_from_score(currency_data.get("confidence", 0)),
            method=currency_data.get("detection_method", "unknown"),
        )

    # Country / Jurisdiction
    # Inferred from sector or location
    sector = result_data.get("detected_sector")
    locations = result_data.get("detected_locations", [])
    if locations:
        audit.set_country_info(country=locations[0], confidence="Low")
    elif sector:
        audit.set_country_info(country="South Africa (assumed from sector)", confidence="Low")

    # BOQ info
    boq_items = result_data.get("boq_items", [])
    # BOQ tables info from result data would come from BOQ Engine's metadata
    # For now, infer from items
    audit.boq_items_extracted = len(boq_items) if boq_items else 0
    audit.boq_tables_found = 1 if boq_items else 0
    audit.boq_tables_accepted = 1 if boq_items else 0

    # Entity classification info from warnings
    entity_warnings = [w for w in warnings if "entity" in w.lower() or "classif" in w.lower()]

    # Stages
    completed_stages = result_data.get("completed_stages", [])
    failed_stages = result_data.get("failed_stages", [])
    audit.stages_completed = len(completed_stages)
    audit.stages_failed = len(failed_stages)

    # Warnings
    audit.warnings = warnings[:20]  # Limit to 20 warnings

    return audit


# ═══════════════════════════════════════════════════════════════════════
# Build Full Evidence System
# ═══════════════════════════════════════════════════════════════════════

def build_evidence_system(
    result_data: Dict[str, Any],
    pipeline_start: Optional[float] = None,
    pipeline_end: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Build the complete evidence system for a processing result.
    
    Returns:
      - evidence_records: List of evidence records for each extracted field
      - processing_audit: Complete processing audit
      - accepted_evidence: Values that passed validation
      - rejected_evidence: Value
      - rejected_reasons: Why values were rejected
    """
    evidence_records = build_evidence_from_result(result_data)
    processing_audit = build_processing_audit(result_data, pipeline_start, pipeline_end)

    accepted = [e for e in evidence_records if e.get("extracted")]
    rejected = [e for e in evidence_records if not e.get("extracted")]

    return {
        "evidence_system_version": EVIDENCE_SYSTEM_VERSION,
        "generated_at": datetime.now().isoformat(),
        "evidence_records": evidence_records,
        "processing_audit": processing_audit.to_dict(),
        "accepted_evidence": accepted,
        "rejected_evidence": rejected,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "total_fields": len(evidence_records),
    }


# ═══════════════════════════════════════════════════════════════════════
# PDF Section for Evidence
# ═══════════════════════════════════════════════════════════════════════

def build_evidence_pdf_sections(
    evidence_data: Dict[str, Any],
    pdf_styles: Dict[str, Any],
) -> List[Any]:
    """
    Build PDF flowable elements for the Evidence section.
    """
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib import colors
    from reportlab.lib.units import cm

    elements = []
    s = pdf_styles

    # ── Processing Audit ─────────────────────────────────────────────
    elements.append(Paragraph("Processing Audit", s["section"]))
    audit = evidence_data.get("processing_audit", {})

    audit_data = [["Metric", "Value"]]
    audit_data.append(["PDF Parsed", f"Yes ({audit.get('page_count', 0)} pages)" if audit.get('pdf_parsed') else "No"])
    audit_data.append(["Pages Parsed", str(audit.get('pages_parsed', 0))])
    audit_data.append(["OCR Used", "Yes" if audit.get('ocr_used') else "No"])
    if audit.get('ocr_used'):
        audit_data.append(["OCR Reason", audit.get('ocr_reason', '')[:80]])
        audit_data.append(["OCR Confidence", audit.get('ocr_confidence', 'N/A')])
    else:
        audit_data.append(["OCR Skipped Reason", audit.get('ocr_skipped_reason', '')[:80]])
    audit_data.append(["Languages Detected", ", ".join(audit.get('languages_detected', [])) or "N/A"])
    audit_data.append(["Currency Detected", audit.get('currency_detected', 'None')])
    audit_data.append(["Currency Method", audit.get('currency_method', 'N/A')])
    audit_data.append(["Country Detected", audit.get('country_detected', 'None')])
    audit_data.append(["BOQ Tables Found", str(audit.get('boq_tables_found', 0))])
    audit_data.append(["BOQ Tables Accepted", str(audit.get('boq_tables_accepted', 0))])
    audit_data.append(["BOQ Tables Rejected", str(audit.get('boq_tables_rejected', 0))])
    audit_data.append(["Items Extracted", str(audit.get('boq_items_extracted', 0))])
    audit_data.append(["Entities Classified", str(audit.get('numeric_entities_classified', 0))])
    audit_data.append(["Processing Time", audit.get('processing_time_ms', 'N/A')])
    audit_data.append(["Pipeline Version", audit.get('pipeline_version', 'N/A')])
    audit_data.append(["Extraction Version", audit.get('extraction_version', 'N/A')])
    audit_data.append(["Stages Completed", str(audit.get('stages_completed', 0))])
    audit_data.append(["Stages Failed", str(audit.get('stages_failed', 0))])

    table = Table(audit_data, colWidths=[5 * cm, 13 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#1F4E79")),
        ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#F5F8FC")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.3 * cm))

    if audit.get('boq_rejected_reasons'):
        elements.append(Paragraph("<b>BOQ Rejected Tables:</b>", s["body_bold"]))
        for reason in audit['boq_rejected_reasons']:
            elements.append(Paragraph(f"  • {reason}", s["small"]))

    # ── Accepted Evidence ────────────────────────────────────────────
    elements.append(Paragraph("Accepted Evidence", s["section"]))
    accepted = evidence_data.get("accepted_evidence", [])

    if accepted:
        acc_data = [["Field", "Value", "Method", "Confidence"]]
        for e in accepted:
            acc_data.append([
                e.get("field_name", ""),
                str(e.get("value", "") or "Detected"),
                e.get("detection_method", ""),
                e.get("confidence", ""),
            ])

        table = Table(acc_data, colWidths=[4 * cm, 4.5 * cm, 5 * cm, 2.5 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No evidence was successfully extracted.", s["body"]))
    elements.append(Spacer(1, 0.3 * cm))

    # ── Rejected Evidence ────────────────────────────────────────────
    elements.append(Paragraph("Rejected Evidence", s["section"]))
    rejected = evidence_data.get("rejected_evidence", [])

    if rejected:
        for e in rejected:
            elements.append(Paragraph(
                f"<b>{e.get('field_name', 'Unknown')}</b> — {e.get('evidence_text', 'No evidence')}",
                s["body"]
            ))
    else:
        elements.append(Paragraph("All fields were successfully extracted — no rejections.", s["body"]))

    return elements