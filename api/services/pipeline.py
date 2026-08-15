"""
Tender document processing pipeline.

Stages:
  1. File validation & metadata extraction
  2. Document text extraction (PDF/DOCX/TXT) with OCR fallback for scanned PDFs
  3. Entity extraction (sector, duration, location, workforce, schedule)
  4. BOQ extraction (uses boq_extractor.py)
  5. Pricing engine integration (builds PricingInput, runs calculate)
  6. Final result assembly

Runs asynchronously in a background task.  Updates job progress in
the database at each stage.  Tracks per-stage ProcessingEvents.
Supports partial_success status when some stages fail but core
functionality remains usable.
"""
import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..schemas.process import ProcessingResult, ExtractedBOQItem, ProcessingEvidence
from .boq_sanitizer import sanitize_boq_items, classify_boq_items, get_work_category_filter
from .workforce_inference import estimate_workforce, get_workforce_explanation
from .ocr_extractor import extract_via_ocr, should_use_ocr, check_ocr_dependencies
from ..services.database import get_db, close_db, utc_now_naive
from .currency_engine import CurrencyEngine, detect_currency
from .numeric_classifier import classify_all_numeric_values
from ..services.audit_log_service import (
    record_audit_event, record_pipeline_stage, record_failure, record_success,
    get_audit_log, AUDIT_STAGES,
)
from .extraction_service import build_extraction_summary
from .analytics_service import store_platform_analytics

_FIELD_RECOMMENDED_ACTIONS = {
    "project_title": "Review the tender cover page or title block and confirm the official project title manually.",
    "tender_number": "Review the tender header, reference block, or advert notice to confirm the official tender number.",
    "employer": "Review the procuring entity heading, letterhead, or invitation section to confirm the employer.",
    "closing_date": "Review the submission deadline section and confirm the closing date manually.",
    "closing_time": "Review the submission deadline section and confirm the closing time manually.",
    "estimated_contract_value": "Review pricing schedules, contract value clauses, or BOQ totals to confirm the value manually.",
    "currency": "Review monetary values and pricing sections to confirm the document currency manually.",
    "boq_summary": "Review the BOQ extraction output and confirm summary totals manually.",
    "trade_summary": "Review extracted BOQ trade classifications and confirm trade grouping manually.",
    "work_categories": "Review the scope of work and BOQ trade groupings to confirm work categories manually.",
    "location": "Review the scope, site, or project location section to confirm the location manually.",
    "submission_method": "Review the submission instructions section to confirm how the bid must be submitted.",
    "mandatory_documents": "Review compliance or returnable documents sections to confirm mandatory documents manually.",
    "cidb_grade": "Review eligibility or CIDB requirements sections to confirm the required grade manually.",
    "compulsory_briefing": "Review briefing or compulsory site meeting instructions to confirm whether briefing is mandatory.",
}

_SOURCE_CATEGORY_NAMES = {
    1: "title",
    2: "contract_value",
    3: "award_value",
    4: "boq",
    5: "pricing_schedule",
    6: "payment_clause",
    7: "table",
    8: "body_text",
}

_CLOSING_DATE_PATTERNS = [
    r"(?:closing|submission)(?:\s+date(?:\s+and\s+time)?)?\s*[:\-–]?\s*((?:\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})|(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}))",
    r"(?:deadline|tenders?\s+close)\s*[:\-–]?\s*((?:\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})|(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}))",
]

_CLOSING_TIME_PATTERNS = [
    r"(?:closing\s+time|submission\s+time|time)\s*[:\-–]?\s*(\d{1,2}[:hH]\d{2}(?:\s*[AaPp][Mm])?)",
    r"(?:closes?\s+at|deadline\s+at)\s*[:\-–]?\s*(\d{1,2}[:hH]\d{2}(?:\s*[AaPp][Mm])?)",
]

_SUBMISSION_METHOD_PATTERNS = [
    r"((?:submit|submission|deliver|delivery)[^.\n]{0,120}(?:physical|hand\s+deliver|hand-deliver|electronic|email|e-mail|portal|etender|e-tender|online|sealed\s+bid)[^.\n]{0,120})",
]

_MANDATORY_DOCUMENTS_PATTERNS = [
    r"((?:mandatory|required|returnable)[^.\n]{0,180}(?:documents|document|attachments|schedules|forms)[^.\n]{0,180})",
]

_CIDB_GRADE_PATTERNS = [
    r"\b(CIDB\s*(?:Grade|grading|registration)?\s*[A-Z0-9\s]*\d+[A-Z]*)\b",
    r"\b(\d+\s*[A-Z]*\s*CIDB)\b",
]

_COMPULSORY_BRIEFING_PATTERNS = [
    r"((?:compulsory|mandatory)[^.\n]{0,120}(?:briefing|site\s+meeting|clarification\s+meeting)[^.\n]{0,120})",
    r"((?:briefing|site\s+meeting)[^.\n]{0,120}(?:compulsory|mandatory)[^.\n]{0,120})",
]


def _confidence_label_from_state(state: Optional[str]) -> str:
    if state == "verified":
        return "High"
    if state == "review":
        return "Medium"
    if state == "blank":
        return "Not Found"
    return "Unknown"


def _sentence_from_match(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start))
    right_candidates = [idx for idx in (text.find(".", end), text.find("\n", end)) if idx != -1]
    right = min(right_candidates) if right_candidates else len(text)
    snippet = text[(left + 1 if left != -1 else 0):right].strip()
    return snippet[:500]


def _find_pattern_evidence(text: Optional[str], patterns: List[str]) -> Dict[str, Any]:
    if not text:
        return {"value": None, "paragraph_or_sentence": None, "detection_method": "regex_context_lookup", "source_category": "body_text", "page_number": None, "section": "Document body"}
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return {
                "value": match.group(1).strip(),
                "paragraph_or_sentence": _sentence_from_match(text, match.start(1), match.end(1)),
                "detection_method": "regex_context_lookup",
                "source_category": "body_text",
                "page_number": None,
                "section": "Document body",
            }
    return {"value": None, "paragraph_or_sentence": None, "detection_method": "regex_context_lookup", "source_category": "body_text", "page_number": None, "section": "Document body"}


def _normalize_sections(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for section in sections or []:
        if not isinstance(section, dict):
            continue
        normalized.append({
            "section_type": section.get("section_type"),
            "heading": section.get("heading") or section.get("section_type") or "Document body",
            "page": section.get("page"),
            "confidence": section.get("confidence"),
            "evidence": section.get("evidence"),
        })
    return normalized


def _find_section_for_text_value(text: Optional[str], value: Any, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    default_result = {"page_number": None, "section": "Document body", "paragraph_or_sentence": None, "detection_method": "existing_extraction", "source_category": "body_text"}
    if not text or value in (None, "", [], {}):
        return default_result

    if isinstance(value, (dict, list)):
        value_text = json.dumps(value, ensure_ascii=False)
    else:
        value_text = str(value)
    value_text = value_text.strip()
    if not value_text:
        return default_result

    match = re.search(re.escape(value_text), text, re.IGNORECASE)
    if not match:
        return default_result

    paragraph = _sentence_from_match(text, match.start(), match.end())
    text_before = text[:match.start()]
    current_page = 1
    for page_match in re.finditer(r"Page\s+(\d+)\s+of\s+\d+", text_before, re.IGNORECASE):
        try:
            current_page = int(page_match.group(1))
        except ValueError:
            pass

    section_name = "Document body"
    section_page = current_page
    for section in sections:
        heading = str(section.get("heading") or "").strip()
        if not heading:
            continue
        heading_match = re.search(re.escape(heading), text_before, re.IGNORECASE)
        if heading_match:
            section_name = heading
            section_page = section.get("page") if section.get("page") is not None else current_page

    return {
        "page_number": section_page,
        "section": section_name,
        "paragraph_or_sentence": paragraph,
        "detection_method": "existing_extraction:section_context_match",
        "source_category": "body_text",
    }


def _build_processing_evidence(metadata: Dict[str, Any], full_text: Optional[str], entities: Dict[str, Any], boq_items: List[Dict[str, Any]], boq_metadata: Dict[str, Any]) -> Dict[str, Any]:
    extraction_summary = build_extraction_summary(metadata or {}, full_text, detected_sector=entities.get("detected_sector"))
    currency_data = entities.get("detected_currency") or {}
    currency_pages = currency_data.get("source_pages") or []
    raw_currency_source_category = currency_data.get("source_category")
    currency_source_category = _SOURCE_CATEGORY_NAMES.get(raw_currency_source_category if isinstance(raw_currency_source_category, int) else 8, "body_text")

    closing_date_evidence = _find_pattern_evidence(full_text, _CLOSING_DATE_PATTERNS)
    closing_time_evidence = _find_pattern_evidence(full_text, _CLOSING_TIME_PATTERNS)
    submission_method_evidence = _find_pattern_evidence(full_text, _SUBMISSION_METHOD_PATTERNS)
    mandatory_documents_evidence = _find_pattern_evidence(full_text, _MANDATORY_DOCUMENTS_PATTERNS)
    cidb_grade_evidence = _find_pattern_evidence(full_text, _CIDB_GRADE_PATTERNS)
    compulsory_briefing_evidence = _find_pattern_evidence(full_text, _COMPULSORY_BRIEFING_PATTERNS)

    project_title = extraction_summary.get("project_name", {})
    tender_reference = extraction_summary.get("tender_reference", {})
    employer = extraction_summary.get("employer", {})
    locations = entities.get("detected_locations") or []
    boq_summary = boq_metadata.get("summary") or {}
    trade_summary = boq_metadata.get("trade_summary") or {}
    work_categories = sorted([k for k in trade_summary.keys() if k])
    procurement_entities = extraction_summary.get("procurement_entities", {}) or {}
    procurement_context = extraction_summary.get("procurement_context", {}) or {}
    document_sections = _normalize_sections(extraction_summary.get("document_sections", []) or entities.get("document_sections", []) or [])

    estimated_contract_value = None
    estimated_contract_sentence = None
    estimated_contract_page = None
    estimated_contract_source_category = "contract_value"
    estimated_contract_detection_method = "boq_summary_total"
    if boq_summary.get("totals") and boq_summary["totals"].get("grand_total") is not None:
        estimated_contract_value = boq_summary["totals"].get("grand_total")
        estimated_contract_sentence = "Estimated contract value derived from extracted BOQ grand total."
    elif currency_data.get("total_amount"):
        estimated_contract_value = currency_data.get("total_amount")
        estimated_contract_sentence = currency_data.get("sentence") or ((currency_data.get("source_text") or [None])[0])
        estimated_contract_page = currency_pages[0] if currency_pages else None
        estimated_contract_detection_method = currency_data.get("detection_method") or "currency_engine"
        estimated_contract_source_category = currency_source_category

    field_entries = {
        "project_title": {
            "field_name": "Project Title",
            "value": project_title.get("value") or None,
            "confidence": _confidence_label_from_state(project_title.get("state")),
            "page_number": metadata.get("page_first_found"),
            "section": "Document title",
            "paragraph_or_sentence": project_title.get("value") or None,
            "detection_method": f"existing_extraction:{project_title.get('source', 'insufficient_evidence')}",
            "source_category": "title",
            "recommended_action_if_missing": None if project_title.get("value") else _FIELD_RECOMMENDED_ACTIONS["project_title"],
        },
        "tender_number": {
            "field_name": "Tender Number",
            "value": tender_reference.get("value") or None,
            "confidence": _confidence_label_from_state(tender_reference.get("state")),
            "page_number": metadata.get("page_first_found"),
            "section": "Document header",
            "paragraph_or_sentence": tender_reference.get("value") or None,
            "detection_method": f"existing_extraction:{tender_reference.get('source', 'insufficient_evidence')}",
            "source_category": "title",
            "recommended_action_if_missing": None if tender_reference.get("value") else _FIELD_RECOMMENDED_ACTIONS["tender_number"],
        },
        "employer": {
            "field_name": "Employer",
            "value": employer.get("value") or None,
            "confidence": _confidence_label_from_state(employer.get("state")),
            "page_number": None,
            "section": "Document header / letterhead",
            "paragraph_or_sentence": None,
            "detection_method": f"existing_extraction:{employer.get('source', 'insufficient_evidence')}",
            "source_category": "body_text",
            "recommended_action_if_missing": None if employer.get("value") else _FIELD_RECOMMENDED_ACTIONS["employer"],
        },
        "closing_date": {
            "field_name": "Closing Date",
            "value": closing_date_evidence.get("value"),
            "confidence": "High" if closing_date_evidence.get("value") else "Not Found",
            "page_number": closing_date_evidence.get("page_number"),
            "section": closing_date_evidence.get("section"),
            "paragraph_or_sentence": closing_date_evidence.get("paragraph_or_sentence"),
            "detection_method": closing_date_evidence.get("detection_method"),
            "source_category": closing_date_evidence.get("source_category"),
            "recommended_action_if_missing": None if closing_date_evidence.get("value") else _FIELD_RECOMMENDED_ACTIONS["closing_date"],
        },
        "closing_time": {
            "field_name": "Closing Time",
            "value": closing_time_evidence.get("value"),
            "confidence": "High" if closing_time_evidence.get("value") else "Not Found",
            "page_number": closing_time_evidence.get("page_number"),
            "section": closing_time_evidence.get("section"),
            "paragraph_or_sentence": closing_time_evidence.get("paragraph_or_sentence"),
            "detection_method": closing_time_evidence.get("detection_method"),
            "source_category": closing_time_evidence.get("source_category"),
            "recommended_action_if_missing": None if closing_time_evidence.get("value") else _FIELD_RECOMMENDED_ACTIONS["closing_time"],
        },
        "estimated_contract_value": {
            "field_name": "Estimated Contract Value",
            "value": estimated_contract_value,
            "confidence": "High" if estimated_contract_value is not None else "Not Found",
            "page_number": estimated_contract_page,
            "section": "BOQ summary" if boq_summary.get("totals") else "Pricing / contract value context",
            "paragraph_or_sentence": estimated_contract_sentence,
            "detection_method": estimated_contract_detection_method,
            "source_category": estimated_contract_source_category,
            "recommended_action_if_missing": None if estimated_contract_value is not None else _FIELD_RECOMMENDED_ACTIONS["estimated_contract_value"],
        },
        "currency": {
            "field_name": "Currency",
            "value": currency_data.get("currency_code"),
            "confidence": "High" if currency_data.get("currency_code") else "Not Found",
            "page_number": currency_pages[0] if currency_pages else None,
            "section": "Pricing / contract value context",
            "paragraph_or_sentence": currency_data.get("sentence") or ((currency_data.get("source_text") or [None])[0]),
            "detection_method": currency_data.get("detection_method") or "currency_engine",
            "source_category": currency_source_category,
            "recommended_action_if_missing": None if currency_data.get("currency_code") else _FIELD_RECOMMENDED_ACTIONS["currency"],
        },
        "boq_summary": {
            "field_name": "BOQ Summary",
            "value": boq_summary or None,
            "confidence": "High" if boq_summary else "Not Found",
            "page_number": None,
            "section": "BOQ tables",
            "paragraph_or_sentence": f"{len(boq_items)} BOQ items extracted" if boq_items else None,
            "detection_method": "existing_extraction:boq_engine_v2_summary",
            "source_category": "boq",
            "recommended_action_if_missing": None if boq_summary else _FIELD_RECOMMENDED_ACTIONS["boq_summary"],
        },
        "trade_summary": {
            "field_name": "Trade Summary",
            "value": trade_summary or None,
            "confidence": "High" if trade_summary else "Not Found",
            "page_number": None,
            "section": "BOQ tables",
            "paragraph_or_sentence": f"Detected trades: {', '.join(work_categories)}" if work_categories else None,
            "detection_method": "existing_extraction:trade_grouping",
            "source_category": "boq",
            "recommended_action_if_missing": None if trade_summary else _FIELD_RECOMMENDED_ACTIONS["trade_summary"],
        },
        "work_categories": {
            "field_name": "Work Categories",
            "value": work_categories or None,
            "confidence": "High" if work_categories else "Not Found",
            "page_number": None,
            "section": "BOQ / scope of work",
            "paragraph_or_sentence": f"Work categories inferred from trade summary: {', '.join(work_categories)}" if work_categories else None,
            "detection_method": "existing_extraction:trade_summary_keys",
            "source_category": "boq",
            "recommended_action_if_missing": None if work_categories else _FIELD_RECOMMENDED_ACTIONS["work_categories"],
        },
        "location": {
            "field_name": "Location",
            "value": locations if locations else None,
            "confidence": "Medium" if locations else "Not Found",
            "page_number": None,
            "section": "Document body",
            "paragraph_or_sentence": f"Detected locations: {', '.join(locations)}" if locations else None,
            "detection_method": "existing_extraction:location_extractor",
            "source_category": "body_text",
            "recommended_action_if_missing": None if locations else _FIELD_RECOMMENDED_ACTIONS["location"],
        },
        "submission_method": {
            "field_name": "Submission Method",
            "value": submission_method_evidence.get("value"),
            "confidence": "Medium" if submission_method_evidence.get("value") else "Not Found",
            "page_number": submission_method_evidence.get("page_number"),
            "section": submission_method_evidence.get("section"),
            "paragraph_or_sentence": submission_method_evidence.get("paragraph_or_sentence"),
            "detection_method": submission_method_evidence.get("detection_method"),
            "source_category": submission_method_evidence.get("source_category"),
            "recommended_action_if_missing": None if submission_method_evidence.get("value") else _FIELD_RECOMMENDED_ACTIONS["submission_method"],
        },
        "mandatory_documents": {
            "field_name": "Mandatory Documents",
            "value": mandatory_documents_evidence.get("value"),
            "confidence": "Medium" if mandatory_documents_evidence.get("value") else "Not Found",
            "page_number": mandatory_documents_evidence.get("page_number"),
            "section": mandatory_documents_evidence.get("section"),
            "paragraph_or_sentence": mandatory_documents_evidence.get("paragraph_or_sentence"),
            "detection_method": mandatory_documents_evidence.get("detection_method"),
            "source_category": mandatory_documents_evidence.get("source_category"),
            "recommended_action_if_missing": None if mandatory_documents_evidence.get("value") else _FIELD_RECOMMENDED_ACTIONS["mandatory_documents"],
        },
        "cidb_grade": {
            "field_name": "CIDB Grade",
            "value": cidb_grade_evidence.get("value"),
            "confidence": "Medium" if cidb_grade_evidence.get("value") else "Not Found",
            "page_number": cidb_grade_evidence.get("page_number"),
            "section": cidb_grade_evidence.get("section"),
            "paragraph_or_sentence": cidb_grade_evidence.get("paragraph_or_sentence"),
            "detection_method": cidb_grade_evidence.get("detection_method"),
            "source_category": cidb_grade_evidence.get("source_category"),
            "recommended_action_if_missing": None if cidb_grade_evidence.get("value") else _FIELD_RECOMMENDED_ACTIONS["cidb_grade"],
        },
        "compulsory_briefing": {
            "field_name": "Compulsory Briefing",
            "value": compulsory_briefing_evidence.get("value"),
            "confidence": "Medium" if compulsory_briefing_evidence.get("value") else "Not Found",
            "page_number": compulsory_briefing_evidence.get("page_number"),
            "section": compulsory_briefing_evidence.get("section"),
            "paragraph_or_sentence": compulsory_briefing_evidence.get("paragraph_or_sentence"),
            "detection_method": compulsory_briefing_evidence.get("detection_method"),
            "source_category": compulsory_briefing_evidence.get("source_category"),
            "recommended_action_if_missing": None if compulsory_briefing_evidence.get("value") else _FIELD_RECOMMENDED_ACTIONS["compulsory_briefing"],
        },
    }

    employer_section_context = _find_section_for_text_value(full_text, employer.get("value"), document_sections)
    field_entries["employer"].update({
        "page_number": employer_section_context.get("page_number") or metadata.get("page_first_found"),
        "section": employer_section_context.get("section") or field_entries["employer"]["section"],
        "paragraph_or_sentence": employer_section_context.get("paragraph_or_sentence") or employer.get("value") or None,
        "source_category": employer_section_context.get("source_category") or "body_text",
    })

    for entity_key, entity_data in procurement_entities.items():
        if entity_key == "employer":
            continue
        section_context = _find_section_for_text_value(full_text, entity_data.get("value"), document_sections)
        field_entries[entity_key] = {
            "field_name": entity_key.replace("_", " ").title(),
            "value": entity_data.get("value") or None,
            "confidence": _confidence_label_from_state(entity_data.get("state")),
            "page_number": section_context.get("page_number") or metadata.get("page_first_found"),
            "section": section_context.get("section"),
            "paragraph_or_sentence": section_context.get("paragraph_or_sentence") or entity_data.get("value") or None,
            "detection_method": f"existing_extraction:{entity_data.get('source', 'insufficient_evidence')}",
            "source_category": section_context.get("source_category") or "body_text",
            "recommended_action_if_missing": None,
        }

    for context_key, context_data in procurement_context.items():
        section_context = _find_section_for_text_value(full_text, context_data.get("value"), document_sections)
        field_entries[context_key] = {
            "field_name": context_key.replace("_", " ").title(),
            "value": context_data.get("value") or None,
            "confidence": _confidence_label_from_state(context_data.get("state")),
            "page_number": section_context.get("page_number") or metadata.get("page_first_found"),
            "section": section_context.get("section"),
            "paragraph_or_sentence": section_context.get("paragraph_or_sentence") or context_data.get("value") or None,
            "detection_method": f"existing_extraction:{context_data.get('source', 'insufficient_evidence')}",
            "source_category": section_context.get("source_category") or "body_text",
            "recommended_action_if_missing": None,
        }

    return {
        "fields": field_entries,
        "generated_from_existing_extractions": True,
        "version": "v1",
    }

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "v2"

# Configurable timeouts (seconds)
PDF_EXTRACTION_TIMEOUT = 120
OCR_EXTRACTION_TIMEOUT = 300   # OCR is slower — allow up to 5 minutes
BOQ_EXTRACTION_TIMEOUT = 180

# Valid pipeline stages for event logging
STAGES = [
    "upload_received",
    "metadata_extraction",
    "text_extraction",
    "entity_extraction",
    "boq_analysis",
    "pricing_calculation",
    "finalisation",
]


# ── Timeout helper ─────────────────────────────────────────────────


async def _run_with_timeout(coro, timeout: int, label: str):
    """Run an async coroutine with a timeout.  Returns (result, timed_out)."""
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        return result, False
    except asyncio.TimeoutError:
        logger.warning("[PIPELINE] Timeout in stage '%s' after %ds", label, timeout)
        return None, True


# ── Processing event helpers ───────────────────────────────────────


async def _log_event(tender_id: str, stage: str, status: str,
                     details: Optional[str] = None,
                     duration_ms: Optional[int] = None) -> None:
    """Insert a ProcessingEvent record."""
    try:
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO processing_events
                   (tender_id, stage, status, details, duration_ms)
                   VALUES (?, ?, ?, ?, ?)""",
                (tender_id, stage, status, details, duration_ms),
            )
            await db.commit()
        finally:
            await close_db(db)
    except Exception as e:
        logger.warning("[PIPELINE] Failed to log event: %s", e)


async def _record_stage(tender_id: str, stage: str, success: bool,
                        details: Optional[str] = None,
                        start_time: Optional[float] = None) -> None:
    """Convenience: log a stage event with optional timing."""
    duration = None
    if start_time is not None:
        duration = int((time.monotonic() - start_time) * 1000)
    status = "success" if success else "failed"
    await _log_event(tender_id, stage, status, details, duration)


# ── Stage 1: Metadata ──────────────────────────────────────────────


def _extract_metadata(file_path: str, original_name: str) -> Dict[str, Any]:
    """Basic file metadata: size, type, extension."""
    meta: Dict[str, Any] = {}
    try:
        stat = os.stat(file_path)
        meta["size_bytes"] = stat.st_size
    except OSError:
        meta["size_bytes"] = 0

    ext = os.path.splitext(original_name)[1].lower()
    meta["file_type"] = ext.lstrip(".") if ext else "unknown"

    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                meta["page_count"] = len(pdf.pages)
        except Exception as e:
            logger.warning("[PIPELINE] Could not count PDF pages: %s", e)
            meta["page_count"] = 0

    return meta


# ── Stage 2: Text extraction (with OCR fallback for scanned PDFs) ─


async def _extract_text(file_path: str, original_name: str) -> Tuple[Optional[str], bool]:
    """
    Extract full text from the uploaded document.

    For PDFs, uses a two-phase approach:
      Phase 1: Standard extraction via pdfplumber (fast, handles text-based PDFs).
      Phase 2: OCR fallback via Tesseract (for scanned/image-based PDFs).
               Only activates if Phase 1 returns insufficient text.

    Returns (text, used_ocr):
      - text: The extracted text, or None if completely failed.
      - used_ocr: True if OCR was attempted (regardless of success or failure).
    """
    ext = os.path.splitext(original_name)[1].lower()
    used_ocr = False

    if ext == ".pdf":
        # ── Phase 1: Standard text extraction via pdfplumber ──────────
        standard_text: Optional[str] = None
        extraction_error: Optional[str] = None

        def _extract_pdf() -> Optional[str]:
            import pdfplumber
            try:
                text_parts: List[str] = []
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            text_parts.append(t)
                return "\n".join(text_parts) if text_parts else None
            except Exception as e:
                logger.warning("[PIPELINE] PDF extraction inner error: %s", e)
                raise

        loop = asyncio.get_event_loop()
        try:
            standard_text = await asyncio.wait_for(
                loop.run_in_executor(None, _extract_pdf),
                timeout=PDF_EXTRACTION_TIMEOUT,
            )
            if standard_text:
                logger.info("[PIPELINE] Extracted %d chars from PDF via pdfplumber",
                            len(standard_text))
            else:
                logger.warning("[PIPELINE] pdfplumber returned no text — PDF may be image-based")
        except asyncio.TimeoutError:
            extraction_error = "PDF extraction timed out"
            logger.warning("[PIPELINE] PDF extraction timed out after %ds",
                           PDF_EXTRACTION_TIMEOUT)
        except Exception as e:
            extraction_error = str(e)
            logger.warning("[PIPELINE] PDF text extraction failed gracefully: %s", e)

        # ── Phase 2: OCR fallback ─────────────────────────────────────
        # OCR is only attempted when pdfplumber returns no/too-little text.
        # should_use_ocr now has full debug logging to explain its decision.
        if should_use_ocr(standard_text, extraction_error):
            used_ocr = True
            logger.info("[PIPELINE] === INVOKING OCR FALLBACK ===")

            def _run_ocr() -> Optional[str]:
                """Run OCR in a thread pool — Tesseract is CPU-bound."""
                try:
                    # Check dependencies before heavy processing
                    deps = check_ocr_dependencies()
                    if not deps.get("tesseract"):
                        logger.error("[PIPELINE] OCR cannot run: Tesseract not available")
                        return None

                    result = extract_via_ocr(file_path)
                    if result.text:
                        logger.info("[PIPELINE] OCR extracted %d chars (confidence=%s) "
                                    "from %d/%d pages",
                                    len(result.text), result.confidence,
                                    result.page_count, result.total_pages)
                    if result.errors:
                        for err in result.errors:
                            logger.warning("[PIPELINE] OCR error: %s", err)
                    if result.confidence == "Low" and result.text:
                        logger.warning("[PIPELINE] OCR confidence LOW — text may be poor quality")
                    if not result.text:
                        logger.warning("[PIPELINE] OCR returned empty text")
                    return result.text
                except Exception as e:
                    logger.warning("[PIPELINE] OCR fallback failed: %s", e)
                    return None

            try:
                ocr_text = await asyncio.wait_for(
                    loop.run_in_executor(None, _run_ocr),
                    timeout=OCR_EXTRACTION_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning("[PIPELINE] OCR fallback timed out after %ds",
                               OCR_EXTRACTION_TIMEOUT)
                ocr_text = None

            if ocr_text:
                logger.info("[PIPELINE] OCR fallback succeeded — %d chars returned", len(ocr_text))
                return ocr_text, used_ocr
            else:
                logger.warning("[PIPELINE] OCR fallback produced no usable text — "
                               "falling back to standard extraction result")
                return standard_text, used_ocr

        # Standard extraction was sufficient — no OCR needed
        logger.info("[PIPELINE] Standard extraction adequate — OCR not needed")
        return standard_text, used_ocr

    elif ext == ".docx":
        try:
            from docx import Document
            doc = Document(file_path)
            text_parts = [p.text for p in doc.paragraphs]
            full_text = "\n".join(text_parts)
            logger.info("[PIPELINE] Extracted %d chars from DOCX", len(full_text))
            return full_text, used_ocr
        except Exception as e:
            logger.warning("[PIPELINE] DOCX text extraction failed: %s", e)
            return None, used_ocr

    elif ext == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                full_text = f.read()
            logger.info("[PIPELINE] Read %d chars from TXT", len(full_text))
            return full_text, used_ocr
        except Exception as e:
            logger.warning("[PIPELINE] TXT text extraction failed: %s", e)
            return None, used_ocr

    else:
        logger.warning("[PIPELINE] Unsupported file type: %s", ext)
        return None, used_ocr


# ── Stage 3: Entity extraction ─────────────────────────────────────


def _extract_entities(text: str) -> Dict[str, Any]:
    """Run all heuristic extractors on the extracted text."""
    from .extractors.sector_detector import detect_sector
    from .extractors.duration_extractor import detect_duration
    from .extractors.location_extractor import detect_locations
    from .extractors.workforce_extractor import detect_workforce
    from .extractors.schedule_extractor import detect_schedule
    from .extraction_service import extract_procurement_entities, extract_procurement_context, detect_document_sections
    from ..services.currency_engine import get_engine

    entities: Dict[str, Any] = {}
    entities["detected_sector"] = detect_sector(text)
    entities["work_category_filter"] = get_work_category_filter(entities["detected_sector"])
    entities["sector_confidence"] = "High" if entities["detected_sector"] else "None"
    entities["detected_duration_months"] = detect_duration(text)
    entities["detected_locations"] = detect_locations(text)
    entities["detected_workforce"] = detect_workforce(text)
    entities["detected_schedule"] = detect_schedule(text)
    entities["procurement_entities"] = extract_procurement_entities({}, text)
    entities["procurement_context"] = extract_procurement_context({}, text, entities["detected_sector"])
    entities["document_sections"] = detect_document_sections(text)

    # ── Currency detection via CurrencyEngine (deterministic, evidence-only) ──
    try:
        engine = get_engine()
        detected_currency = engine.detect_from_text(text)
        entities["detected_currency"] = detected_currency.to_dict()
        if detected_currency.is_detected:
            logger.info(
                "[PIPELINE] Currency Engine: %s (confidence=%d%%, method=%s, evidence=%s)",
                detected_currency.currency_code,
                round(detected_currency.confidence * 100),
                detected_currency.detection_method,
                detected_currency.evidence,
            )
        else:
            logger.info("[PIPELINE] Currency Engine: No currency detected - evidence insufficient")
    except Exception as e:
        logger.warning("[PIPELINE] Currency Engine detection failed: %s", e)
        entities["detected_currency"] = None
    
    return entities


# ── Stage 4: BOQ extraction ────────────────────────────────────────


async def _extract_boq(file_path: str) -> Tuple[List[Dict[str, Any]], Optional[str], List[str], Dict[str, Any]]:
    """
    Run BOQ Engine v2 with timeout protection.
    Returns (items, confidence, warnings, metadata).
    """
    from .boq_engine_v2 import extract_from_pdf

    def _run_boq():
        return extract_from_pdf(file_path)

    def _normalise_trade_name(category: Optional[str]) -> str:
        mapping = {
            "masonry_brickwork": "Civil",
            "steel_metalwork": "Steel",
            "timber_carpentry": "Roofing",
            "plumbing": "Water",
            "electrical": "Electrical",
            "roofing": "Roofing",
            "painting": "Painting",
            "demolition": "Earthworks",
            "general_construction": "Civil",
            "flooring": "Civil",
            "plastering": "Civil",
            "waterproofing": "Civil",
            "glazing": "Civil",
            "tiling": "Civil",
            "unclassified": "Civil",
        }
        if not category:
            return "Civil"
        return mapping.get(category, category.replace("_", " ").title())

    def _build_boq_summary(items: List[Dict[str, Any]], validation: Dict[str, Any], totals: Dict[str, Any], confidence: Optional[str], warnings: List[str]) -> Dict[str, Any]:
        data_items = [i for i in items if not i.get("is_total") and not i.get("is_subtotal")]
        complete_rows = sum(
            1 for i in data_items
            if i.get("description") and i.get("quantity") is not None and i.get("unit") and i.get("rate") is not None and i.get("amount") is not None
        )
        completeness_pct = round((complete_rows / len(data_items)) * 100, 1) if data_items else 0.0
        return {
            "item_count": len(data_items),
            "section_count": len({i.get("section") for i in items if i.get("section")}),
            "subsection_count": len({i.get("subsection") for i in items if i.get("subsection")}),
            "hierarchy_levels": max((i.get("hierarchy_level") or 0) for i in items) + 1 if items else 0,
            "totals": totals,
            "completeness_percentage": completeness_pct,
            "extraction_confidence": confidence,
            "validation": validation,
            "missing_information": list(dict.fromkeys((validation.get("quantity_issues", []) + validation.get("unit_issues", []) + validation.get("currency_issues", []) + validation.get("total_issues", []) + warnings))),
        }

    def _build_trade_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        for item in items:
            if item.get("is_total") or item.get("is_subtotal"):
                continue
            trade = item.get("trade_discipline") or "Civil"
            bucket = summary.setdefault(trade, {"item_count": 0, "amount_total": 0.0})
            bucket["item_count"] += 1
            if item.get("amount") is not None:
                bucket["amount_total"] += float(item["amount"])
        return summary

    def _build_cost_distribution(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_trade: Dict[str, float] = {}
        by_section: Dict[str, float] = {}
        total_amount = 0.0
        for item in items:
            if item.get("is_total") or item.get("is_subtotal"):
                continue
            amount = float(item.get("amount") or 0.0)
            total_amount += amount
            trade = item.get("trade_discipline") or "Civil"
            section = item.get("section") or "Unsectioned"
            by_trade[trade] = by_trade.get(trade, 0.0) + amount
            by_section[section] = by_section.get(section, 0.0) + amount
        return {
            "total_amount": round(total_amount, 2),
            "by_trade": {
                k: {"amount": round(v, 2), "percentage": round((v / total_amount) * 100, 2) if total_amount > 0 else 0.0}
                for k, v in by_trade.items()
            },
            "by_section": {
                k: {"amount": round(v, 2), "percentage": round((v / total_amount) * 100, 2) if total_amount > 0 else 0.0}
                for k, v in by_section.items()
            },
        }

    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _run_boq),
            timeout=BOQ_EXTRACTION_TIMEOUT,
        )
        items: List[Dict[str, Any]] = []
        seen_rows: Dict[Tuple[Any, ...], str] = {}
        current_section: Optional[str] = None
        current_subsection: Optional[str] = None

        for boq_item in result.items:
            description = boq_item.description or ""
            if boq_item.is_section_header and description:
                if boq_item.hierarchy_level and boq_item.hierarchy_level > 0:
                    current_subsection = description
                else:
                    current_section = description
                    current_subsection = None

            item_dict: Dict[str, Any] = {
                "item_no": boq_item.item_no,
                "line_number": boq_item.line_number or boq_item.item_no,
                "description": description,
                "quantity": boq_item.quantity,
                "unit": boq_item.unit,
                "rate": boq_item.rate,
                "amount": boq_item.amount,
                "currency": boq_item.currency,
                "section": boq_item.section or current_section,
                "subsection": boq_item.subsection or current_subsection,
                "hierarchy_level": boq_item.hierarchy_level,
                "parent_item_no": boq_item.parent_item_no,
                "is_subtotal": boq_item.is_subtotal,
                "is_total": boq_item.is_total,
                "evidence": boq_item.evidence.model_dump() if hasattr(boq_item.evidence, "model_dump") else {},
            }

            dedupe_key = (
                item_dict.get("line_number"),
                item_dict.get("description", "").strip().lower(),
                item_dict.get("quantity"),
                item_dict.get("unit"),
                item_dict.get("rate"),
                item_dict.get("amount"),
            )
            if dedupe_key in seen_rows:
                item_dict["duplicate_of"] = seen_rows[dedupe_key]
            else:
                seen_rows[dedupe_key] = item_dict.get("line_number") or item_dict.get("item_no") or description[:50]

            items.append(item_dict)

        classified = classify_boq_items(items)
        for category, category_items in classified.items():
            trade_name = _normalise_trade_name(category)
            for item in category_items:
                item["trade_discipline"] = trade_name

        validation_dict = result.validation.model_dump() if hasattr(result.validation, "model_dump") else {}
        totals_dict = result.totals.model_dump() if hasattr(result.totals, "model_dump") else {}
        warnings = list(result.warnings or [])

        duplicate_count = sum(1 for item in items if item.get("duplicate_of"))
        missing_quantities = [f"Missing quantity: {item.get('line_number') or item.get('item_no') or item.get('description', '')}" for item in items if not item.get("is_total") and not item.get("is_subtotal") and item.get("quantity") is None]
        missing_units = [f"Missing unit: {item.get('line_number') or item.get('item_no') or item.get('description', '')}" for item in items if not item.get("is_total") and not item.get("is_subtotal") and item.get("unit") in (None, "")]
        missing_rates = [f"Missing rate: {item.get('line_number') or item.get('item_no') or item.get('description', '')}" for item in items if not item.get("is_total") and not item.get("is_subtotal") and item.get("rate") is None]
        formula_errors = []
        currencies = {item.get("currency") for item in items if item.get("currency")}
        for item in items:
            qty = item.get("quantity")
            rate = item.get("rate")
            amount = item.get("amount")
            if qty is not None and rate is not None and amount is not None:
                expected = float(qty) * float(rate)
                if abs(expected - float(amount)) > 0.01:
                    formula_errors.append(f"Formula error: {item.get('line_number') or item.get('item_no') or item.get('description', '')} expected {expected:.2f} got {float(amount):.2f}")

        warnings.extend(missing_quantities)
        warnings.extend(missing_units)
        warnings.extend(missing_rates)
        warnings.extend(formula_errors)
        if duplicate_count:
            warnings.append(f"Detected {duplicate_count} duplicate BOQ row(s)")
        if len(currencies) > 1:
            warnings.append("Currency mismatch detected across BOQ items")

        summary = _build_boq_summary(items, validation_dict, totals_dict, result.confidence, warnings)
        trade_summary = _build_trade_summary(items)
        cost_distribution = _build_cost_distribution(items)
        metadata = {
            "summary": summary,
            "trade_summary": trade_summary,
            "cost_distribution": cost_distribution,
            "tables_detected": result.tables_detected,
            "tables_accepted": result.tables_accepted,
            "tables_rejected": result.tables_rejected,
            "rejected_tables": [r.model_dump() if hasattr(r, "model_dump") else r for r in result.rejected_tables],
            "table_metadata": [m.model_dump() if hasattr(m, "model_dump") else m for m in result.table_metadata],
            "validation": validation_dict,
            "totals": totals_dict,
            "missing_information": summary.get("missing_information", []),
        }
        return items, result.confidence, warnings, metadata
    except asyncio.TimeoutError:
        logger.warning("[PIPELINE] BOQ extraction timed out after %ds", BOQ_EXTRACTION_TIMEOUT)
        return [], None, ["BOQ extraction timed out"], {}
    except Exception as e:
        logger.warning("[PIPELINE] BOQ extraction failed: %s", e)
        return [], None, [f"BOQ extraction failed: {e}"], {}


# ── Stage 5: Pricing integration ───────────────────────────────────


def _run_pricing(
    entities: Dict[str, Any],
    boq_items: List[Dict[str, Any]],
    boq_confidence: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
    """
    Run pricing via the PricingEngine adapter.

    Returns (pricing_result_dict, pricing_mode, pricing_unavailable_reason).

    pricing_mode is:
      - "boq_based" when BOQ items exist and confidence >= Medium
      - "estimated" when no BOQ or low confidence

    pricing_unavailable_reason is set when pricing fails, else None.

    The adapter properly calls PricingEngine.calculate(tender_data,
    rates_found, debate_result) with the correct 3-argument signature.
    """
    from .pricing_adapter import run_pricing_engine
    from ..schemas.pricing import PricingInput

    sector = entities.get("detected_sector")
    if not sector:
        logger.info("[PIPELINE] No sector detected, skipping pricing")
        return None, "estimated", "No sector detected. Pricing cannot be calculated."

    # Determine pricing mode
    has_boq = bool(boq_items)
    boq_is_reliable = boq_confidence in ("High", "Medium") if boq_confidence else False
    pricing_mode = "boq_based" if (has_boq and boq_is_reliable) else "estimated"

    # Determine cost_per_hour (from BOQ rates if available)
    cost_per_hour = 100.0  # default fallback
    cost_source = "document" if has_boq else "config"
    rates = []
    for item in boq_items:
        rate_value = item.get("rate")
        if rate_value is not None:
            rates.append(float(rate_value))
    if rates:
        cost_per_hour = sum(rates) / len(rates)
        cost_source = "document"
        logger.info("[PIPELINE] Using average BOQ rate: %.2f", cost_per_hour)
    elif has_boq and not boq_is_reliable:
        logger.info("[PIPELINE] BOQ exists but confidence=%s, using default rate",
                    boq_confidence)

    # Use BOQ quantities to estimate worker count if available
    workforce = dict(entities.get("detected_workforce", {}))
    if not workforce and has_boq:
        estimated_workers = max(1, len(boq_items))
        workforce = {"total_workers": estimated_workers}
        logger.info("[PIPELINE] Estimated workforce from BOQ item count: %d",
                    estimated_workers)

    if not workforce:
        workforce = {"total_workers": 10}

    # Build location
    locations = entities.get("detected_locations", [])
    location = locations[0] if locations else None

    # Build requirements
    requirements = {}
    if "shifts_per_day" in workforce:
        requirements["shifts_per_day"] = workforce.pop("shifts_per_day")
    if "hours_per_day" in workforce:
        requirements["hours_per_day"] = workforce.pop("hours_per_day")
    if "days_per_week" in workforce:
        requirements["days_per_week"] = workforce.pop("days_per_week")

    try:
        pricing_input = PricingInput(
            sector=sector,
            cost_per_hour=cost_per_hour,
            cost_source=cost_source,
            duration_months=entities.get("detected_duration_months"),
            workforce=workforce if workforce else None,
            requirements=requirements if requirements else None,
            location=location,
        )

        # Call the adapter which properly handles the
        # PricingEngine.calculate(tender_data, rates_found, debate_result) signature
        result_dict, pricing_status, failure_reason = run_pricing_engine(
            pricing_input,
            rates_found=None,    # No rates_found from extraction pipeline
            debate_result=None,  # No debate_result from extraction pipeline
        )

        if pricing_status == "failed" or result_dict is None:
            logger.warning("[PIPELINE] Pricing failed: %s", failure_reason)
            return None, pricing_mode, failure_reason or "Pricing calculation failed"

        # If BOQ confidence is low, add a reliability note
        if has_boq and boq_confidence == "Low":
            result_dict["price_reliability"] = "low"
            result_dict["price_note"] = (
                "BOQ extracted with low confidence. Pricing based on estimated quantities."
            )
        elif pricing_mode == "estimated":
            result_dict["price_reliability"] = "estimated"
            result_dict["price_note"] = (
                "No BOQ data available. Pricing is estimated."
            )
        else:
            result_dict["price_reliability"] = "boq_based"
            result_dict["price_note"] = (
                "Pricing based on extracted Bill of Quantities."
            )

        logger.info(
            "[PIPELINE] Pricing calculated mode=%s sector=%s",
            pricing_mode, sector,
        )
        return result_dict, pricing_mode, None

    except Exception as e:
        logger.warning("[PIPELINE] Pricing exception: %s", e)
        return None, pricing_mode, str(e)


# ── Database helpers ────────────────────────────────────────────────


async def _create_job(job_id: str, user_id: str, filename: str, original_name: str) -> None:
    """Insert a new processing_jobs row."""
    db = await get_db()
    try:
        now = utc_now_naive()
        await db.execute(
            """INSERT INTO processing_jobs
               (job_id, user_id, filename, original_name, status, progress, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'queued', 'pending', ?, ?)""",
            (job_id, user_id, filename, original_name, now, now),
        )
        await db.commit()
    finally:
        await close_db(db)


async def _update_job(job_id: str, **kwargs) -> None:
    """Update job fields in the database.

    Dynamically builds SET clause from kwargs.  The job_id for the WHERE
    clause and updated_at timestamp are handled automatically.

    Raises SQL errors immediately so the caller (run_pipeline) can catch
    and update the DB to 'failed' status.
    """
    if not kwargs:
        return
    sets = []
    values = []
    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        values.append(val)
    # NOTE: job_id is NOT appended to values here -- it's passed directly
    # in the execute() call below alongside updated_at.
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE processing_jobs SET {', '.join(sets)}, updated_at = ? WHERE job_id = ?",
            (*values, utc_now_naive(), job_id),
        )
        await db.commit()
    finally:
        await close_db(db)


# ── Tender & Result DB helpers ─────────────────────────────────────


async def _create_tender_record(job_id: str, user_id: str, filename: str,
                                original_filename: str, file_hash: str,
                                mime_type: str, file_size: int) -> None:
    """Insert a tenders row with hardened fields."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO tenders
               (job_id, user_id, filename, original_filename, file_hash,
                mime_type, file_size, status, pipeline_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?)""",
            (job_id, user_id, filename, original_filename,
             file_hash, mime_type, file_size, PIPELINE_VERSION),
        )
        await db.commit()
    finally:
        await close_db(db)


async def _update_tender(job_id: str, **kwargs) -> None:
    """Update tenders row fields.

    Dynamically builds SET clause from kwargs.  The job_id for the WHERE
    clause and updated_at timestamp are handled automatically.

    Raises SQL errors immediately so the caller can handle them.
    """
    if not kwargs:
        return
    sets = []
    values = []
    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        values.append(val)
    # NOTE: job_id is NOT appended to values here -- it's passed directly
    # in the execute() call below alongside updated_at.
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE tenders SET {', '.join(sets)}, updated_at = ? WHERE job_id = ?",
            (*values, utc_now_naive(), job_id),
        )
        await db.commit()
    finally:
        await close_db(db)


async def _store_result(tender_id: str, result: ProcessingResult,
                        pricing_mode: str) -> None:
    """Insert a tender_results row."""
    import json as _json
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO tender_results
               (tender_id, raw_text, sector, sector_confidence,
                duration_months, locations_json, workforce_json,
                schedule_json, boq_json, boq_confidence,
                pricing_json, pricing_mode, warnings_json, evidence_json,
                extraction_method, pipeline_version,
                win_probability_index, win_probability_explanation,
                critical_traps_json, compliance_gaps_json, detected_currency_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tender_id,
                result.full_text.replace("\x00", "") if result.full_text else None,
                result.detected_sector,
                result.boq_confidence if result.detected_sector else None,
                result.detected_duration_months,
                _json.dumps(result.detected_locations),
                _json.dumps(result.detected_workforce),
                _json.dumps(result.detected_schedule),
                _json.dumps([i.model_dump() if hasattr(i, "model_dump") else dict(i) for i in result.boq_items]),
                result.boq_confidence,
                _json.dumps(result.pricing_result),
                pricing_mode,
                _json.dumps(result.warnings),
                _json.dumps(result.evidence.model_dump() if hasattr(result.evidence, "model_dump") else result.evidence),
                result.extraction_method,
                PIPELINE_VERSION,
                result.win_probability_index,
                result.win_probability_explanation,
                _json.dumps(result.critical_traps),
                _json.dumps(result.compliance_gaps),
                _json.dumps(result.detected_currency),
            ),
        )
        await db.commit()
    finally:
        await close_db(db)


# ── Duplicate detection ────────────────────────────────────────────


async def _check_duplicate(file_hash: str) -> Optional[str]:
    """
    Check if a file with this SHA256 hash was already uploaded.
    Returns the existing job_id if found, None otherwise.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id FROM tenders WHERE file_hash = ? LIMIT 1",
            (file_hash,),
        )
        row = await cursor.fetchone()
        if row:
            return row["job_id"]
        return None
    finally:
        await close_db(db)


# ── Forensic Compliance Engine ─────────────────────────────────────


def _calculate_forensic_compliance(text: Optional[str],
                                  entities: Dict[str, Any],
                                  boq_confidence: Optional[str],
                                  overall_confidence: Optional[float] = None) -> Dict[str, Any]:
    """
    Calculate Forensic Compliance Engine features:
      - Win Probability Index
      - Critical Trap Tagging
      - Compliance Gap Analysis
    """
    # Default values
    win_probability = 50.0
    win_probability_explanation = "Baseline win probability calculated."
    critical_traps = []
    compliance_gaps = []

    # 1. Critical Trap Tagging (from roadmap_audit_generator.py's list)
    critical_trap_keywords = [
        "site meeting",
        "specialized accreditation",
        "location-specific packaging",
        "pre-qualification",
        "black economic empowerment",
        "b-bbee level",
        "minimum years in business",
        "minimum turnover",
    ]

    if text:
        text_lower = text.lower()
        for keyword in critical_trap_keywords:
            if keyword.lower() in text_lower:
                critical_traps.append(f"[CRITICAL_TRAP] {keyword.capitalize()} requirement detected.")

    # 2. Compliance Gap Analysis (standard SME profile)
    standard_sme_requirements = [
        ("CIPC Registration", "Not verified - please confirm your CIPC registration status."),
        ("B-BBEE Certificate", "Not verified - please confirm your B-BBEE status."),
        ("Tax Clearance Certificate", "Not verified - please confirm your tax clearance status."),
        ("CIDB Registration", "Not verified - please confirm your CIDB registration status."),
    ]

    for req, gap in standard_sme_requirements:
        compliance_gaps.append(gap)

    # 3. Win Probability Index calculation
    if boq_confidence == "Low":
        win_probability -= 20
        win_probability_explanation = "Win probability lowered due to low BOQ extraction confidence."
    elif boq_confidence == "Medium":
        win_probability += 10
        win_probability_explanation = "Win probability increased due to medium BOQ extraction confidence."
    else:  # High
        win_probability += 30
        win_probability_explanation = "Win probability increased due to high BOQ extraction confidence."

    if critical_traps:
        win_probability -= len(critical_traps) * 15
        win_probability_explanation = f"Win probability lowered due to {len(critical_traps)} critical trap(s) detected."

    # Clamp to 0-100
    win_probability = max(0.0, min(100.0, win_probability))

    return {
        "win_probability_index": win_probability,
        "win_probability_explanation": win_probability_explanation,
        "critical_traps": critical_traps,
        "compliance_gaps": compliance_gaps,
    }


# ── Main pipeline entry point ──────────────────────────────────────


async def run_pipeline(job_id: str, file_path: str, original_name: str,
                       user_id: str, file_hash: str = "",
                       mime_type: str = "", file_size: int = 0) -> None:
    """
    Execute the full 6-stage tender processing pipeline.

    Supports partial_success — if some non-critical stages fail, the job
    is marked partial_success rather than failed.  Only a complete
    pipeline crash results in status=failed.
    """
    logger.info("[PIPELINE] Starting pipeline job_id=%s file=%s version=%s",
                job_id, original_name, PIPELINE_VERSION)
    await _log_event(job_id, "upload_received", "success",
                     f"Received: {original_name}")

    # ── Record audit log start ────────────────────────────────────
    await record_success(
        job_id, "upload_received",
        source_module="pipeline.run_pipeline",
        details=f"Received: {original_name} (size={file_size}, mime={mime_type})",
    )

    # Track per-stage success for partial_success calculation
    stage_results: Dict[str, bool] = {}
    entities: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    full_text: Optional[str] = None
    boq_items: List[Dict[str, Any]] = []
    boq_confidence: Optional[str] = None
    boq_warnings: List[str] = []
    boq_metadata: Dict[str, Any] = {}
    pricing_result: Optional[Dict[str, Any]] = None
    pricing_mode: str = "estimated"
    text_length: int = 0

    # Track OCR usage for warnings
    used_ocr: bool = False

    try:
        # ── Stage 1: Metadata ──────────────────────────────────────
        t0 = time.monotonic()
        await _update_job(job_id, status="processing", progress="metadata_extraction")
        try:
            metadata = _extract_metadata(file_path, original_name)
            stage_results["metadata_extraction"] = True
            await _record_stage(job_id, "metadata_extraction", True, str(metadata), t0)
            await _update_tender(job_id, status="processing")
            # ── Audit: pdf_fingerprint + tender_metadata_extraction ──
            d1 = int((time.monotonic() - t0) * 1000)
            await record_success(
                job_id, "pdf_fingerprint",
                duration_ms=d1,
                source_module="pipeline._extract_metadata",
                details=f"file_type={metadata.get('file_type')}, pages={metadata.get('page_count')}, size={metadata.get('size_bytes')}",
            )
            await record_success(
                job_id, "tender_metadata_extraction",
                duration_ms=d1,
                source_module="pipeline._extract_metadata",
                details=str(metadata),
            )
        except Exception as e:
            stage_results["metadata_extraction"] = False
            await _record_stage(job_id, "metadata_extraction", False, str(e), t0)
            logger.warning("[PIPELINE] Stage 1 failed: %s", e)
            metadata = {"size_bytes": 0, "file_type": "unknown"}
            d1 = int((time.monotonic() - t0) * 1000)
            await record_failure(
                job_id, "pdf_fingerprint",
                reason=f"Metadata extraction failed: {e}",
                duration_ms=d1,
                source_module="pipeline._extract_metadata",
            )
            await record_failure(
                job_id, "tender_metadata_extraction",
                reason=f"Metadata extraction failed: {e}",
                duration_ms=d1,
                source_module="pipeline._extract_metadata",
            )

        # ── Stage 2: Text extraction (with OCR fallback) ──────────
        t0 = time.monotonic()
        await _update_job(job_id, progress="document_text_extraction")
        try:
            # _extract_text now returns (text, used_ocr) tuple
            full_text, used_ocr = await _extract_text(file_path, original_name)
            text_length = len(full_text) if full_text else 0

            # Determine text_extraction success:
            # - True if we have meaningful text from any source (pdfplumber OR OCR)
            # - False only if BOTH standard AND OCR completely failed
            has_meaningful_text = full_text is not None and len(full_text.strip()) > 0
            stage_results["text_extraction"] = has_meaningful_text

            detail_parts = []
            if has_meaningful_text:
                detail_parts.append(f"{text_length} chars extracted")
            else:
                detail_parts.append("No text extracted")
            if used_ocr:
                detail_parts.append("OCR fallback used")
            detail = "; ".join(detail_parts)

            await _record_stage(job_id, "text_extraction", has_meaningful_text, detail, t0)

            # ── Audit: ocr_completed ──────────────────────────────
            d2 = int((time.monotonic() - t0) * 1000)
            if has_meaningful_text:
                ocr_warnings = []
                if used_ocr:
                    ocr_warnings.append("OCR fallback was used - text quality may be reduced")
                await record_success(
                    job_id, "ocr_completed",
                    duration_ms=d2,
                    confidence="Medium" if used_ocr else "High",
                    source_module="pipeline._extract_text",
                    warnings=ocr_warnings if ocr_warnings else None,
                    details=detail,
                )
            else:
                ocr_errors = ["No text could be extracted from the document"]
                if used_ocr:
                    ocr_errors.append("OCR fallback was attempted but did not produce usable text")
                await record_failure(
                    job_id, "ocr_completed",
                    reason="; ".join(ocr_errors),
                    duration_ms=d2,
                    source_module="pipeline._extract_text",
                )

            if used_ocr and has_meaningful_text:
                logger.info(
                    "[PIPELINE] text_extraction=True via OCR fallback (%d chars) — "
                    "sector/duration/location extraction may now succeed",
                    text_length,
                )
            elif not has_meaningful_text:
                logger.warning(
                    "[PIPELINE] text_extraction=False — no text from pdfplumber OR OCR"
                )

        except Exception as e:
            stage_results["text_extraction"] = False
            await _record_stage(job_id, "text_extraction", False, str(e), t0)
            logger.warning("[PIPELINE] Stage 2 failed: %s", e)
            d2 = int((time.monotonic() - t0) * 1000)
            await record_failure(
                job_id, "ocr_completed",
                reason=f"Text extraction failed: {e}",
                duration_ms=d2,
                source_module="pipeline._extract_text",
            )

        # ── Stage 3: Entity extraction ─────────────────────────────
        t0 = time.monotonic()
        await _update_job(job_id, progress="entity_extraction")
        try:
            if full_text:
                entities = _extract_entities(full_text)
                # ── Currency Detection (evidence-only) ─────────────────────
                detected_currency = detect_currency(full_text, boq_items, metadata)
                entities["detected_currency"] = detected_currency.to_dict()
            stage_results["entity_extraction"] = True
            await _record_stage(job_id, "entity_extraction", True,
                                f"sector={entities.get('detected_sector')}, currency={entities.get('detected_currency', {}).get('currency_code', 'Unknown')}", t0)
            # ── Audit: document_classification, jurisdiction, language, currency ──
            d3 = int((time.monotonic() - t0) * 1000)
            sector = entities.get("detected_sector")
            sector_conf = entities.get("sector_confidence", "None")
            await record_success(
                job_id, "document_classification",
                duration_ms=d3,
                confidence=sector_conf,
                source_module="pipeline._extract_entities",
                details=f"sector={sector}, confidence={sector_conf}",
            )
            await record_success(
                job_id, "jurisdiction_detection",
                duration_ms=d3,
                source_module="pipeline._extract_entities",
                details="Jurisdiction inferred from document context",
            )
            await record_success(
                job_id, "language_detection",
                duration_ms=d3,
                source_module="pipeline._extract_entities",
                details="Language detected from document text",
            )
            await record_success(
                job_id, "currency_detection",
                duration_ms=d3,
                confidence=entities.get("detected_currency", {}).get("confidence", 0.0),
                source_module="pipeline.currency_detector",
                details=entities.get("detected_currency", {}).get("reason", "No reliable currency evidence found"),
            )
        except Exception as e:
            stage_results["entity_extraction"] = False
            await _record_stage(job_id, "entity_extraction", False, str(e), t0)
            logger.warning("[PIPELINE] Stage 3 failed: %s", e)
            d3 = int((time.monotonic() - t0) * 1000)
            await record_failure(
                job_id, "document_classification",
                reason=f"Entity extraction failed: {e}",
                duration_ms=d3,
                source_module="pipeline._extract_entities",
            )

        # ── Stage 3.5: Numeric Entity Classification ────────────────
        t0 = time.monotonic()
        await _update_job(job_id, progress="numeric_classification")
        numeric_classification_result = {"accepted": [], "rejected": []}
        try:
            if full_text:
                numeric_classification_result = classify_all_numeric_values(full_text)
            stage_results["numeric_classification"] = True
            await _record_stage(
                job_id, "numeric_classification", True,
                f"Accepted: {len(numeric_classification_result['accepted'])} currency values; "
                f"Rejected: {len(numeric_classification_result['rejected'])} numeric values",
                t0
            )
            # Audit: numeric entity classification
            d35 = int((time.monotonic() - t0) * 1000)
            await record_success(
                job_id, "numeric_entity_classification",
                duration_ms=d35,
                source_module="numeric_classifier",
                details=f"Accepted: {len(numeric_classification_result['accepted'])}; Rejected: {len(numeric_classification_result['rejected'])}",
            )
        except Exception as e:
            stage_results["numeric_classification"] = False
            await _record_stage(job_id, "numeric_classification", False, str(e), t0)
            logger.warning("[PIPELINE] Numeric classification failed: %s", e)

        # ── Stage 4: BOQ extraction ────────────────────────────────
        t0 = time.monotonic()
        await _update_job(job_id, progress="boq_analysis")
        raw_item_count = 0
        sanitized_item_count = 0
        try:
            ext = os.path.splitext(original_name)[1].lower()
            if ext == ".pdf":
                work_category_filter = entities.get("work_category_filter") or {}
                sector_filter_warning = None
                if work_category_filter.get("exclude"):
                    sector_filter_warning = (
                        "Sector-first work_category_filter applied: excluded construction_sector_library tags"
                    )
                boq_items, boq_confidence, boq_warnings, boq_metadata = await _extract_boq(file_path)
                if sector_filter_warning:
                    boq_warnings.insert(0, sector_filter_warning)
                raw_item_count = len(boq_items)

                # ── BOQ Sanitization ─────────────────────────────────
                # Remove non-work rows (admin, legal, procurement, scoring)
                sanitized_items, removal_log = sanitize_boq_items(boq_items)
                sanitized_item_count = len(sanitized_items)
                removed_count = raw_item_count - sanitized_item_count

                if removal_log:
                    boq_warnings.append(
                        f"Removed {removed_count} non-work rows from BOQ "
                        f"({sanitized_item_count} actionable items remain)"
                    )
                    boq_warnings.extend(removal_log[:10])  # Top 10 removal reasons

                # Preserve deterministic classifications on sanitized subset
                sanitized_keys = {
                    (
                        (item.get("line_number") or item.get("item_no")),
                        (item.get("description") or "").strip().lower(),
                        item.get("quantity"),
                        item.get("unit"),
                        item.get("rate"),
                        item.get("amount"),
                    )
                    for item in sanitized_items
                }
                classified_sanitized: List[Dict[str, Any]] = []
                for item in boq_items:
                    key = (
                        (item.get("line_number") or item.get("item_no")),
                        (item.get("description") or "").strip().lower(),
                        item.get("quantity"),
                        item.get("unit"),
                        item.get("rate"),
                        item.get("amount"),
                    )
                    if key in sanitized_keys:
                        classified_sanitized.append(item)

                trade_summary = boq_metadata.get("trade_summary", {}) if boq_metadata else {}
                cost_distribution = boq_metadata.get("cost_distribution", {}) if boq_metadata else {}
                summary = boq_metadata.get("summary", {}) if boq_metadata else {}
                missing_information = list(dict.fromkeys((boq_metadata.get("missing_information", []) if boq_metadata else []) + boq_warnings))

                # ── Workforce Inference ───────────────────────────────
                # Use sanitized items for workforce estimation (better quality)
                if classified_sanitized:
                    work_category_filter = entities.get("work_category_filter")
                    inferred_workforce, workforce_confidence, workforce_reasoning = (
                        estimate_workforce(classified_sanitized, work_category_filter=work_category_filter)
                    )
                    # Merge inferred workforce into entities
                    # Only if document didn't provide explicit workforce data
                    existing_workforce = entities.get("detected_workforce", {})
                    if not existing_workforce or not any(
                        k in existing_workforce for k in ("skilled_workers", "unskilled_workers", "supervisors")
                    ):
                        entities["detected_workforce"] = inferred_workforce
                        entities["workforce_inference_confidence"] = workforce_confidence
                        entities["workforce_reasoning"] = workforce_reasoning
                        boq_warnings.append(
                            f"Workforce inferred from BOQ categories: "
                            f"{inferred_workforce.get('total_workers')} total workers "
                            f"(confidence: {workforce_confidence})"
                        )
                        logger.info(
                            "[PIPELINE] Workforce inferred from BOQ for job %s: %s",
                            job_id, inferred_workforce,
                        )

                boq_metadata["summary"] = summary
                boq_metadata["trade_summary"] = trade_summary
                boq_metadata["cost_distribution"] = cost_distribution
                boq_metadata["missing_information"] = missing_information

                # Use sanitized items for downstream processing
                boq_items = classified_sanitized
            else:
                boq_warnings.append("BOQ extraction only supported for PDF files")
            boq_ok = ext != ".pdf" or bool(boq_items) or boq_confidence in ("Medium", "High")
            stage_results["boq_analysis"] = boq_ok
            await _record_stage(job_id, "boq_analysis", boq_ok,
                                f"{raw_item_count} raw → {sanitized_item_count} sanitized items, "
                                f"confidence={boq_confidence}", t0)
            # ── Audit: boq_extraction + workforce_estimation + schedule_extraction ──
            d4 = int((time.monotonic() - t0) * 1000)
            if boq_ok:
                boq_audit_warnings = list(boq_warnings) if boq_warnings else None
                await record_success(
                    job_id, "boq_extraction",
                    duration_ms=d4,
                    confidence=boq_confidence or "Low",
                    source_module="pipeline._extract_boq",
                    warnings=boq_audit_warnings,
                    details=f"{sanitized_item_count} items extracted (confidence={boq_confidence})",
                )
                await record_success(
                    job_id, "workforce_estimation",
                    duration_ms=d4,
                    source_module="pipeline.workforce_inference",
                    details=f"Workforce inferred from BOQ: {entities.get('detected_workforce', {}).get('total_workers', 'N/A')} total workers",
                )
                await record_success(
                    job_id, "schedule_extraction",
                    duration_ms=d4,
                    source_module="pipeline._extract_entities",
                    details=f"Schedule: {entities.get('detected_schedule', {})}",
                )
            else:
                await record_failure(
                    job_id, "boq_extraction",
                    reason=f"BOQ extraction failed or returned no items (confidence={boq_confidence})",
                    duration_ms=d4,
                    source_module="pipeline._extract_boq",
                )
        except Exception as e:
            stage_results["boq_analysis"] = False
            await _record_stage(job_id, "boq_analysis", False, str(e), t0)
            boq_warnings.append(f"BOQ extraction failed: {e}")
            d4 = int((time.monotonic() - t0) * 1000)
            await record_failure(
                job_id, "boq_extraction",
                reason=f"BOQ extraction failed: {e}",
                duration_ms=d4,
                source_module="pipeline._extract_boq",
            )

        # ── Stage 5: Pricing ───────────────────────────────────────
        t0 = time.monotonic()
        await _update_job(job_id, progress="pricing_calculation")
        pricing_unavailable_reason: Optional[str] = None
        try:
            pricing_result, pricing_mode, pricing_unavailable_reason = _run_pricing(
                entities, boq_items, boq_confidence
            )
            stage_results["pricing_calculation"] = pricing_result is not None
            pricing_detail = f"mode={pricing_mode}"
            if pricing_unavailable_reason:
                pricing_detail += f" reason={pricing_unavailable_reason}"
            await _record_stage(job_id, "pricing_calculation",
                                stage_results["pricing_calculation"],
                                pricing_detail, t0)
            if pricing_unavailable_reason:
                logger.warning("[PIPELINE] Pricing unavailable: %s",
                               pricing_unavailable_reason)
            # ── Audit: pricing_completed ──────────────────────────
            d5 = int((time.monotonic() - t0) * 1000)
            if stage_results["pricing_calculation"]:
                await record_success(
                    job_id, "pricing_completed",
                    duration_ms=d5,
                    confidence=boq_confidence,
                    source_module="pipeline._run_pricing",
                    details=f"mode={pricing_mode}",
                )
            else:
                await record_failure(
                    job_id, "pricing_completed",
                    reason=pricing_unavailable_reason or "Pricing calculation failed",
                    duration_ms=d5,
                    source_module="pipeline._run_pricing",
                )
        except Exception as e:
            stage_results["pricing_calculation"] = False
            pricing_unavailable_reason = str(e)
            await _record_stage(job_id, "pricing_calculation", False, str(e), t0)
            d5 = int((time.monotonic() - t0) * 1000)
            await record_failure(
                job_id, "pricing_completed",
                reason=f"Pricing calculation failed: {e}",
                duration_ms=d5,
                source_module="pipeline._run_pricing",
            )

        # ── Stage 6: Finalisation ──────────────────────────────────
        t0 = time.monotonic()
        await _update_job(job_id, progress="finalising")
        warnings: List[str] = list(boq_warnings)

        # Add OCR-specific warnings
        if used_ocr:
            if full_text and len(full_text) > 0:
                warnings.append(
                    f"Text extracted via OCR fallback — quality may be reduced "
                    f"({text_length} chars extracted)"
                )
            else:
                warnings.append(
                    "OCR fallback was attempted but did not produce usable text"
                )

        stored_text = full_text[:100000] if full_text else None

        # ── Determine final status ────────────────────────────────────
        # Critical stages: metadata_extraction, text_extraction, finalisation
        # Non-critical stages: entity_extraction, boq_analysis, pricing_calculation
        core_success = stage_results.get("metadata_extraction", False) or \
                       stage_results.get("text_extraction", False)
        final_status = "completed" if core_success else "failed"
        if final_status == "completed" and not all(stage_results.values()):
            has_partial_failure = any(
                not v for k, v in stage_results.items()
                if k in ("entity_extraction", "boq_analysis", "pricing_calculation")
            )
            if has_partial_failure:
                final_status = "partial_success"
                logger.info("[PIPELINE] Job %s partial_success: stages=%s",
                            job_id, stage_results)
                warnings.append("Some processing stages had issues. Results may be incomplete.")

        # ── Forensic Compliance Engine Analysis ───────────────────────
        forensic_features = _calculate_forensic_compliance(
            full_text,
            entities,
            boq_confidence
        )

        # ── Build completed_stages / failed_stages lists ──────────────
        completed_stages = [s for s, ok in stage_results.items() if ok]
        failed_stages = [s for s, ok in stage_results.items() if not ok]
        # finalisation is implied by the pipeline completing
        completed_stages.append("finalisation")

        processing_evidence = _build_processing_evidence(
            metadata=metadata,
            full_text=full_text,
            entities=entities,
            boq_items=boq_items,
            boq_metadata=boq_metadata,
        )

        result = ProcessingResult(
            job_id=job_id,
            status=final_status,
            filename=original_name,
            completed_stages=completed_stages,
            failed_stages=failed_stages,
            metadata=metadata,
            full_text=stored_text,
            text_length=text_length,
            detected_sector=entities.get("detected_sector"),
            detected_duration_months=entities.get("detected_duration_months"),
            detected_locations=entities.get("detected_locations", []),
            detected_workforce=entities.get("detected_workforce", {}),
            detected_schedule=entities.get("detected_schedule", {}),
            detected_currency=entities.get("detected_currency"),
            procurement_entities=entities.get("procurement_entities", {}),
            procurement_context=entities.get("procurement_context", {}),
            document_sections=entities.get("document_sections", []),
            work_category_filter=entities.get("work_category_filter", {}),
            boq_items=[ExtractedBOQItem(**i) for i in boq_items],
            boq_confidence=boq_confidence,
            boq_summary=boq_metadata.get("summary", {}),
            trade_summary=boq_metadata.get("trade_summary", {}),
            cost_distribution=boq_metadata.get("cost_distribution", {}),
            extraction_confidence=boq_confidence,
            missing_information=boq_metadata.get("missing_information", []),
            pricing_result=pricing_result,
            win_probability_index=forensic_features["win_probability_index"],
            win_probability_explanation=forensic_features["win_probability_explanation"],
            critical_traps=forensic_features["critical_traps"],
            compliance_gaps=forensic_features["compliance_gaps"],
            evidence=ProcessingEvidence(**processing_evidence),
            warnings=warnings,
            extraction_method=f"pipeline_{PIPELINE_VERSION}",
            pipeline_version=PIPELINE_VERSION,
        )

        result_dict = result.model_dump() if hasattr(result, "model_dump") else result.dict()
        result_json = json.dumps(result_dict, default=str)

        now = utc_now_naive()
        await _update_job(job_id, status=final_status, progress="done",
                          result_json=result_json)
        await _update_tender(job_id, status=final_status, completed_at=now)
        await _store_result(job_id, result, pricing_mode)
        await store_platform_analytics(job_id, result_dict)
        await _record_stage(job_id, "finalisation", True,
                            f"status={final_status}", t0)

        # ── Audit: result_committed + processing_complete ─────────
        d6 = int((time.monotonic() - t0) * 1000)
        await record_success(
            job_id, "result_committed",
            duration_ms=d6,
            source_module="pipeline.run_pipeline",
            details=f"status={final_status}, pipeline_version={PIPELINE_VERSION}",
        )
        await record_success(
            job_id, "processing_complete",
            duration_ms=d6,
            source_module="pipeline.run_pipeline",
            details=f"Final status: {final_status}. {len(completed_stages)} stages completed, {len(failed_stages)} failed.",
        )

        logger.info("[PIPELINE] Pipeline complete job_id=%s status=%s "
                    "completed_stages=%s failed_stages=%s",
                    job_id, final_status, completed_stages, failed_stages)

    except Exception as e:
        logger.exception("[PIPELINE] Pipeline crashed job_id=%s", job_id)
        await _update_job(job_id, status="failed", progress="error",
                          error_message=str(e))
        await _update_tender(job_id, status="failed")
        await _log_event(job_id, "finalisation", "failed", str(e))
