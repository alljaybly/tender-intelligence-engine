"""
Tender Readiness Report Service
================================
Computes a comprehensive readiness assessment from processing results.

This platform is deterministic document-processing software.
It must never fabricate information or estimate missing data.
Every status, recommendation and assessment is derived only from verified
extraction results and deterministic business rules.

Sections:
   1. Tender Readiness Score (0–100) with category breakdown
   2. Missing Information Detection
   3. Missing Documents Detection
   4. Confidence Summary
   5. Risk Summary
   6. Recommendations
   7. Dashboard Integration Payload
   8. PDF Export Support (structured data for report generation)
   9. Tender Readiness Assessment PDF (enterprise-grade)

HONESTY RULES:
  - NO fabricated data
  - All confidence levels preserved
  - Missing data honestly marked
  - Reports are automatically generated, not manually curated
"""
import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)

from .confidence_service import compute_composite_confidence
from .schema_manager import SchemaManager
from .currency_util import CurrencyUtil
from .report_framework import build_action_plan, MISSING_FIELD_GUIDANCE

logger = logging.getLogger(__name__)

# ── Version ───────────────────────────────────────────────────────────
READINESS_PDF_VERSION = "1.0.0"

# ── Color palette (enterprise, consistent with submission letter) ────
PRIMARY_BLUE = colors.HexColor("#1F4E79")
ACCENT_BLUE = colors.HexColor("#2B78AE")
LIGHT_BLUE_BG = colors.HexColor("#E8F0FE")
VERY_LIGHT_BG = colors.HexColor("#F5F8FC")
TEXT_DARK = colors.HexColor("#222222")
TEXT_MEDIUM = colors.HexColor("#555555")
TEXT_LIGHT = colors.HexColor("#888888")
WHITE = colors.white
BORDER_LIGHT = colors.HexColor("#DDDDDD")
GREEN_VERIFIED = colors.HexColor("#155724")
GREEN_BG = colors.HexColor("#D4EDDA")
AMBER_WARN = colors.HexColor("#856404")
AMBER_BG = colors.HexColor("#FFF3CD")
RED_ERROR = colors.HexColor("#721C24")
RED_BG = colors.HexColor("#F8D7DA")
GRAY_BG = colors.HexColor("#F0F0F0")

# ── Page dimensions ───────────────────────────────────────────────────
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2.5 * cm
TOP_MARGIN = 2.5 * cm
BOTTOM_MARGIN = 2.0 * cm

# ── Styles (enterprise, consistent with submission letter) ───────────
styles = getSampleStyleSheet()

BRAND_TITLE_STYLE = ParagraphStyle(
    "BrandTitle", parent=styles["Title"],
    fontSize=20, leading=24, textColor=PRIMARY_BLUE,
    spaceAfter=0, alignment=TA_CENTER,
    fontName="Helvetica-Bold",
)

BRAND_SUBTITLE_STYLE = ParagraphStyle(
    "BrandSubtitle", parent=styles["Normal"],
    fontSize=10, leading=13, textColor=TEXT_MEDIUM,
    spaceAfter=4, alignment=TA_CENTER,
    fontName="Helvetica",
)

SECTION_STYLE = ParagraphStyle(
    "SectionHeader", parent=styles["Heading1"],
    fontSize=14, leading=18, textColor=PRIMARY_BLUE,
    spaceBefore=16, spaceAfter=8,
    fontName="Helvetica-Bold",
)

SUBSECTION_STYLE = ParagraphStyle(
    "SubSectionHeader", parent=styles["Heading2"],
    fontSize=11, leading=14, textColor=PRIMARY_BLUE,
    spaceBefore=10, spaceAfter=4,
    fontName="Helvetica-Bold",
)

BODY_STYLE = ParagraphStyle(
    "ReadinessBody", parent=styles["Normal"],
    fontSize=9.5, leading=14, textColor=TEXT_DARK,
    spaceAfter=4, alignment=TA_JUSTIFY,
    fontName="Helvetica",
)

BODY_BOLD_STYLE = ParagraphStyle(
    "ReadinessBodyBold", parent=BODY_STYLE,
    fontName="Helvetica-Bold",
)

LABEL_STYLE = ParagraphStyle(
    "FieldLabel", parent=styles["Normal"],
    fontSize=7.5, leading=9, textColor=TEXT_LIGHT,
    spaceAfter=1, fontName="Helvetica-Oblique",
)

VALUE_STYLE = ParagraphStyle(
    "FieldValue", parent=styles["Normal"],
    fontSize=10, leading=13, textColor=TEXT_DARK,
    spaceAfter=2, fontName="Helvetica",
)

STATUS_READY_STYLE = ParagraphStyle(
    "StatusReady", parent=styles["Normal"],
    fontSize=13, leading=17, textColor=GREEN_VERIFIED,
    spaceAfter=4, fontName="Helvetica-Bold",
    alignment=TA_CENTER,
)

STATUS_MINOR_STYLE = ParagraphStyle(
    "StatusMinor", parent=styles["Normal"],
    fontSize=13, leading=17, textColor=AMBER_WARN,
    spaceAfter=4, fontName="Helvetica-Bold",
    alignment=TA_CENTER,
)

STATUS_REVIEW_STYLE = ParagraphStyle(
    "StatusReview", parent=styles["Normal"],
    fontSize=13, leading=17, textColor=AMBER_WARN,
    spaceAfter=4, fontName="Helvetica-Bold",
    alignment=TA_CENTER,
)

STATUS_NOTREADY_STYLE = ParagraphStyle(
    "StatusNotReady", parent=styles["Normal"],
    fontSize=13, leading=17, textColor=RED_ERROR,
    spaceAfter=4, fontName="Helvetica-Bold",
    alignment=TA_CENTER,
)

VERIFIED_ITEM_STYLE = ParagraphStyle(
    "VerifiedItem", parent=styles["Normal"],
    fontSize=9, leading=12, textColor=TEXT_DARK,
    spaceAfter=3, fontName="Helvetica",
)

BLANK_ITEM_STYLE = ParagraphStyle(
    "BlankItem", parent=styles["Normal"],
    fontSize=9, leading=12, textColor=TEXT_LIGHT,
    spaceAfter=3, fontName="Helvetica-Oblique",
)

RISK_LEVEL_STYLE = ParagraphStyle(
    "RiskLevel", parent=styles["Normal"],
    fontSize=11, leading=14, textColor=TEXT_DARK,
    spaceAfter=2, fontName="Helvetica-Bold",
)

RECOMMENDATION_STYLE = ParagraphStyle(
    "Recommendation", parent=styles["Normal"],
    fontSize=9, leading=13, textColor=TEXT_DARK,
    spaceAfter=3, fontName="Helvetica",
)

FOOTER_STYLE = ParagraphStyle(
    "Footer", parent=styles["Normal"],
    fontSize=7, leading=10, textColor=TEXT_LIGHT,
    alignment=TA_CENTER,
)

FOOTER_BOLD_STYLE = ParagraphStyle(
    "FooterBold", parent=FOOTER_STYLE,
    fontName="Helvetica-Bold",
)

# ── Weights for readiness score categories ────────────────────────────
WEIGHTS = {
    "extraction_quality": 0.15,
    "entity_completeness": 0.20,
    "boq_completeness": 0.20,
    "pricing_availability": 0.20,
    "workforce_availability": 0.10,
    "document_integrity": 0.15,
}

# ── Missing documents checklist (standard tender requirements) ────────
REQUIRED_DOCUMENTS = [
    {"id": "sbd1", "name": "SBD 1 — Invitation to Bid", "detect_keywords": ["sbd1", "sbd 1", "invitation to bid"]},
    {"id": "sbd2", "name": "SBD 2 — Tax Clearance Certificate", "detect_keywords": ["sbd2", "sbd 2", "tax clearance"]},
    {"id": "sbd3", "name": "SBD 3 — Declaration of Interest", "detect_keywords": ["sbd3", "sbd 3", "declaration of interest"]},
    {"id": "sbd4", "name": "SBD 4 — Bidders Past SCM Practice", "detect_keywords": ["sbd4", "sbd 4", "past scm practice"]},
    {"id": "sbd5", "name": "SBD 5 — Preference Points Claim", "detect_keywords": ["sbd5", "sbd 5", "preference points"]},
    {"id": "sbd6", "name": "SBD 6 — Local Content Declaration", "detect_keywords": ["sbd6", "sbd 6", "local content"]},
    {"id": "sbd7", "name": "SBD 7 — Contract Form", "detect_keywords": ["sbd7", "sbd 7", "contract form"]},
    {"id": "sbd8", "name": "SBD 8 — Bidders Declaration", "detect_keywords": ["sbd8", "sbd 8", "bidders declaration"]},
    {"id": "sbd9", "name": "SBD 9 — Joint Venture", "detect_keywords": ["sbd9", "sbd 9", "joint venture"]},
    {"id": "bid_document", "name": "Bid Document / Tender Notice", "detect_keywords": ["bid document", "tender notice", "tender document"]},
    {"id": "bill_of_quantities", "name": "Bill of Quantities (BOQ)", "detect_keywords": ["bill of quantities", "boq", "schedule of quantities"]},
    {"id": "specifications", "name": "Technical Specifications", "detect_keywords": ["specification", "technical spec", "scope of work"]},
    {"id": "drawings", "name": "Drawings / Plans", "detect_keywords": ["drawing", "plan", "sketch", "layout"]},
    {"id": "company_profile", "name": "Company Profile / Registration", "detect_keywords": ["company profile", "registration", "company registration"]},
    {"id": "financial_statements", "name": "Financial Statements", "detect_keywords": ["financial statement", "audited", "balance sheet"]},
    {"id": "letter_of_goodstanding", "name": "Letter of Goodstanding", "detect_keywords": ["goodstanding", "good standing", "clearance"]},
    {"id": "insurance_certificate", "name": "Insurance Certificate", "detect_keywords": ["insurance", "public liability", "professional indemnity"]},
]

# ── Tender readiness required fields for completeness scoring ──────────
REQUIRED_FIELDS = [
    {"field": "detected_sector", "label": "Sector", "weight": 0.20},
    {"field": "detected_duration_months", "label": "Duration", "weight": 0.15},
    {"field": "detected_locations", "label": "Location(s)", "weight": 0.15},
    {"field": "boq_items", "label": "Bill of Quantities", "weight": 0.25},
    {"field": "pricing_result", "label": "Pricing Calculation", "weight": 0.15},
    {"field": "detected_workforce", "label": "Workforce Data", "weight": 0.10},
]

# ── Document detection patterns (for keyword scanning in full_text) ───
DOCUMENT_PATTERNS: List[Dict[str, Any]] = [
    {"id": "submission_letter", "keywords": ["submission letter", "covering letter", "letter of submission"]},
    {"id": "sbd_form", "keywords": ["sbd", "standard bidding document"]},
    {"id": "tax_clearance", "keywords": ["tax clearance", "tax certificate", "tax pin"]},
    {"id": "company_registration", "keywords": ["company registration", "registration certificate", "ck document"]},
    {"id": "bbbeee_certificate", "keywords": ["bbbee", "b-bbee", "broad-based black", "empowerment", "level 1", "level 2"]},
    {"id": "bid_guarantee", "keywords": ["bid guarantee", "bid bond", "tender guarantee"]},
    {"id": "proof_of_address", "keywords": ["proof of address", "utility bill", "municipal account"]},
    {"id": "id_document", "keywords": ["id document", "identity document", "passport", "copy of id"]},
    {"id": "declaration_of_interest", "keywords": ["declaration of interest", "conflict of interest"]},
]


# ═══════════════════════════════════════════════════════════════════════
# EXISTING JSON REPORT FUNCTIONS (unchanged)
# ═══════════════════════════════════════════════════════════════════════


def build_readiness_report(result_data: Dict[str, Any], jurisdiction_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Build a complete Tender Readiness Report from a processing result dict.

    Args:
        result_data: The full ProcessingResult as a dict
        jurisdiction_code: Optional jurisdiction code (ISO 4217). If not provided,
                          it will be auto-detected.

    Returns:
        Dict with all readiness report sections
    """
    # Detect jurisdiction and get schema
    detected_jurisdiction = jurisdiction_code or SchemaManager.detect_jurisdiction(result_data)
    schema = SchemaManager.get_schema_for_jurisdiction(detected_jurisdiction)
    jurisdiction_used = schema.get("jurisdiction", "South Africa")
    jurisdiction_assumed = detected_jurisdiction is None

    # ── 1. Compute readiness score ──────────────────────────────────
    score_data = compute_readiness_score(result_data, schema)

    # ── 2. Detect missing information ────────────────────────────────
    missing_info = detect_missing_information(result_data, schema)

    # ── 3. Detect missing documents ──────────────────────────────────
    missing_docs = detect_missing_documents(result_data, schema)

    # ── 4. Build confidence summary ──────────────────────────────────
    confidence_summary = build_confidence_summary(result_data)

    # ── 5. Build risk summary ────────────────────────────────────────
    risk_summary = build_risk_summary(result_data)

    # ── 6. Generate recommendations ──────────────────────────────────
    recommendations = generate_recommendations(result_data, score_data, missing_info, missing_docs)
    decision_support = build_action_plan(result_data)

    # ── 7. Build dashboard integration payload ───────────────────────
    dashboard = build_dashboard_payload(result_data, score_data, risk_summary)

    report = {
        "job_id": result_data.get("job_id", ""),
        "filename": result_data.get("filename", "Unknown"),
        "status": result_data.get("status", "unknown"),
        "generated_at": datetime.now().isoformat(),
        "jurisdiction": jurisdiction_used,
        "jurisdiction_assumed": jurisdiction_assumed,

        # Readiness score
        "readiness_score": score_data,

        # Missing information
        "missing_information": missing_info,

        # Missing documents
        "missing_documents": missing_docs,

        # Confidence summary
        "confidence_summary": confidence_summary,

        # Risk summary
        "risk_summary": risk_summary,

        # Recommendations
        "recommendations": recommendations,
        "decision_support": decision_support,

        # Dashboard integration payload
        "dashboard": dashboard,

        # Raw data reference
        "raw": {
            "extraction_method": result_data.get("extraction_method"),
            "pipeline_version": result_data.get("pipeline_version"),
            "text_length": result_data.get("text_length", 0),
        },
    }

    logger.info(
        "[READINESS] Report generated for job %s — jurisdiction=%s score=%.1f risks=%d recs=%d",
        result_data.get("job_id", ""),
        jurisdiction_used,
        score_data.get("overall_score", 0),
        len(risk_summary.get("risks", [])),
        len(recommendations),
    )

    return report


def _evidence_deduction_from_label(label: str) -> int:
    normalized = (label or "").strip().title()
    if normalized == "High":
        return 0
    if normalized == "Medium":
        return 1
    if normalized == "Low":
        return 3
    return 6


def _build_evidence_score_breakdown(result_data: Dict[str, Any]) -> Dict[str, Any]:
    evidence = (result_data.get("evidence") or {}).get("fields", {}) or {}
    tracked_fields = [
        "project_title", "tender_number", "employer", "closing_date", "closing_time",
        "estimated_contract_value", "currency", "boq_summary", "trade_summary",
        "work_categories", "location", "submission_method", "mandatory_documents",
        "cidb_grade", "compulsory_briefing",
    ]
    deductions = []
    total_deduction = 0
    counts = {"High": 0, "Medium": 0, "Low": 0, "Missing": 0}

    for field_key in tracked_fields:
        field = evidence.get(field_key, {}) or {}
        label = str(field.get("field_name") or field_key.replace("_", " ").title())
        value = field.get("value")
        confidence = str(field.get("confidence") or ("Missing" if value in (None, "", [], {}) else "Low")).title()
        if confidence not in counts:
            confidence = "Missing"
        counts[confidence] += 1
        deduction = _evidence_deduction_from_label(confidence)
        total_deduction += deduction
        if deduction > 0:
            deductions.append({
                "field": field_key,
                "label": label,
                "confidence": confidence,
                "deduction": deduction,
                "reason": f"{confidence} confidence {label}" if confidence != "Missing" else f"Missing {label}",
            })

    return {
        "deductions": deductions,
        "total_deduction": total_deduction,
        "confidence_counts": counts,
        "tracked_field_count": len(tracked_fields),
    }


def compute_readiness_score(result_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a composite readiness score (0–100) with category breakdown.

    Factors:
      - extraction_quality:  Quality of text extraction
      - entity_completeness: Completeness of extracted entities
      - boq_completeness:    BOQ item completeness
      - pricing_availability: Pricing data availability & quality
      - workforce_availability: Workforce data availability
      - document_integrity:   Pipeline success, warnings, failures

    Args:
        result_data: The full ProcessingResult as a dict
        schema: The compliance schema to use

    Returns:
        Dict with overall_score, category scores, and label
    """
    weights = schema.get("readiness_weights", {
        "extraction_quality": 0.15,
        "entity_completeness": 0.20,
        "boq_completeness": 0.20,
        "pricing_availability": 0.20,
        "workforce_availability": 0.10,
        "document_integrity": 0.15,
    })

    # ── Category scores (each 0–100) ─────────────────────────────────
    extraction_score = _score_extraction_quality(result_data)
    entity_score = _score_entity_completeness(result_data)
    boq_score = _score_boq_completeness(result_data)
    pricing_score = _score_pricing_availability(result_data)
    workforce_score = _score_workforce_availability(result_data)
    integrity_score = _score_document_integrity(result_data)

    # ── Weighted composite ───────────────────────────────────────────
    overall = (
        extraction_score * weights["extraction_quality"] +
        entity_score * weights["entity_completeness"] +
        boq_score * weights["boq_completeness"] +
        pricing_score * weights["pricing_availability"] +
        workforce_score * weights["workforce_availability"] +
        integrity_score * weights["document_integrity"]
    )

    overall = round(min(100.0, max(0.0, overall)), 1)

    evidence_breakdown = _build_evidence_score_breakdown(result_data)
    overall_after_evidence = round(min(100.0, max(0.0, overall - evidence_breakdown["total_deduction"])), 1)

    # ── Label ────────────────────────────────────────────────────────
    if overall_after_evidence >= 80:
        label = "high"
        label_description = "Tender is well-prepared and ready for submission."
    elif overall_after_evidence >= 50:
        label = "medium"
        label_description = "Tender has gaps that should be addressed before submission."
    elif overall_after_evidence >= 25:
        label = "low"
        label_description = "Significant gaps detected. Review and rework strongly recommended."
    else:
        label = "critical"
        label_description = "Tender data is insufficient for submission. Major rework required."

    categories = {
        "extraction_quality": {
            "score": round(extraction_score, 1),
            "weight": weights["extraction_quality"],
            "label": _score_to_label(extraction_score),
        },
        "entity_completeness": {
            "score": round(entity_score, 1),
            "weight": weights["entity_completeness"],
            "label": _score_to_label(entity_score),
        },
        "boq_completeness": {
            "score": round(boq_score, 1),
            "weight": weights["boq_completeness"],
            "label": _score_to_label(boq_score),
        },
        "pricing_availability": {
            "score": round(pricing_score, 1),
            "weight": weights["pricing_availability"],
            "label": _score_to_label(pricing_score),
        },
        "workforce_availability": {
            "score": round(workforce_score, 1),
            "weight": weights["workforce_availability"],
            "label": _score_to_label(workforce_score),
        },
        "document_integrity": {
            "score": round(integrity_score, 1),
            "weight": weights["document_integrity"],
            "label": _score_to_label(integrity_score),
        },
    }

    return {
        "overall_score": overall_after_evidence,
        "base_score": overall,
        "label": label,
        "label_description": label_description,
        "categories": categories,
        "breakdown": {
            "extraction_quality": round(extraction_score, 1),
            "entity_completeness": round(entity_score, 1),
            "boq_completeness": round(boq_score, 1),
            "pricing_availability": round(pricing_score, 1),
            "workforce_availability": round(workforce_score, 1),
            "document_integrity": round(integrity_score, 1),
        },
        "evidence_quality": evidence_breakdown,
        "calculation": {
            "base_score": overall,
            "deductions": evidence_breakdown["deductions"],
            "total_deduction": evidence_breakdown["total_deduction"],
            "final_score": overall_after_evidence,
        },
    }


def detect_missing_information(result_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect and list missing or incomplete information fields.

    Args:
        result_data: The full ProcessingResult as a dict
        schema: The compliance schema to use

    Returns:
        Dict with count, list of missing fields with severity,
        and completeness percentage
    """
    required_fields = schema.get("required_fields", [
        {"field": "detected_sector", "label": "Sector", "weight": 0.20},
        {"field": "detected_duration_months", "label": "Duration", "weight": 0.15},
        {"field": "detected_locations", "label": "Location(s)", "weight": 0.15},
        {"field": "boq_items", "label": "Bill of Quantities", "weight": 0.25},
        {"field": "pricing_result", "label": "Pricing Calculation", "weight": 0.15},
        {"field": "detected_workforce", "label": "Workforce Data", "weight": 0.10},
    ])

    missing_fields: List[Dict[str, Any]] = []
    total_weight = sum(f["weight"] for f in required_fields)
    completeness_sum = 0.0

    for field_def in required_fields:
        field_name = field_def["field"]
        label = field_def["label"]
        weight = field_def["weight"]
        value = result_data.get(field_name)

        is_missing = False
        severity = "low"
        missing_reason = ""

        if value is None or value == "" or value == "N/A":
            is_missing = True
            severity = "critical"
            missing_reason = f"{label} was not detected in the document."
        elif isinstance(value, list) and len(value) == 0:
            is_missing = True
            severity = "high"
            missing_reason = f"No {label.lower()} were found in the document."
        elif isinstance(value, dict) and not value:
            is_missing = True
            severity = "medium"
            missing_reason = f"{label} data is empty or incomplete."
        else:
            # Field is present
            pass

        if is_missing:
            guidance_defaults = {
                "why_it_matters": missing_reason,
                "where_found": "Refer to the original tender document.",
                "action": f"Locate and verify {label.lower()} before submission.",
            }
            evidence_fields = ((result_data.get("evidence") or {}).get("fields", {}) or {})
            evidence_guidance = evidence_fields.get(field_name, {}) or evidence_fields.get(label.lower().replace(" ", "_"), {}) or {}
            guidance = MISSING_FIELD_GUIDANCE.get(field_name, {})
            missing_fields.append({
                "field": field_name,
                "label": label,
                "severity": severity,
                "reason": missing_reason,
                "status": "Missing",
                "why_it_matters": evidence_guidance.get("why_it_matters") or guidance.get("why_it_matters") or guidance_defaults["why_it_matters"],
                "where_found": evidence_guidance.get("where_found") or guidance.get("where_found") or guidance_defaults["where_found"],
                "who_usually_supplies_it": guidance.get("label") or label,
                "recommended_action": evidence_guidance.get("recommended_action_if_missing") or guidance.get("action") or guidance_defaults["action"],
                "what_happens_if_ignored": f"Tender readiness remains reduced because {label.lower()} is unresolved.",
            })
        else:
            completeness_sum += weight

    completeness_pct = round((completeness_sum / total_weight) * 100, 1) if total_weight > 0 else 0.0

    return {
        "count": len(missing_fields),
        "total_required": len(required_fields),
        "completeness_percentage": completeness_pct,
        "missing_fields": missing_fields,
        "summary": (
            f"{len(missing_fields)} of {len(required_fields)} required fields "
            f"are missing ({100 - completeness_pct:.1f}% incomplete)."
        ),
    }


def detect_missing_documents(result_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect potentially missing tender documents based on full_text scanning
    and document type analysis.

    Args:
        result_data: The full ProcessingResult as a dict
        schema: The compliance schema to use

    Returns:
        Dict with count, list of missing documents, and detected documents
    """
    full_text = result_data.get("full_text", "") or ""
    full_text_lower = full_text.lower()

    required_documents = schema.get("required_documents", [])
    document_patterns = schema.get("document_patterns", [])

    missing_docs: List[Dict[str, Any]] = []
    detected_docs: List[Dict[str, Any]] = []

    for doc in required_documents:
        doc_id = doc["id"]
        doc_name = doc["name"]
        keywords = doc.get("detect_keywords", [])
        severity = doc.get("severity", "medium")

        # Check if any keyword is present in the text
        found = any(kw in full_text_lower for kw in keywords)

        if found:
            detected_docs.append({
                "id": doc_id,
                "name": doc_name,
                "status": "detected",
            })
        else:
            missing_docs.append({
                "id": doc_id,
                "name": doc_name,
                "status": "missing",
                "severity": severity,
            })

    # Also scan for additional document patterns
    additional_detected: List[Dict[str, Any]] = []
    for pattern in document_patterns:
        pattern_id = pattern["id"]
        keywords = pattern["keywords"]

        # Check if already in detected_docs or missing_docs
        already_checked = any(
            d["id"] == pattern_id
            for d in detected_docs + missing_docs
        )
        if not already_checked:
            found = any(kw in full_text_lower for kw in keywords)
            if found:
                additional_detected.append({
                    "id": pattern_id,
                    "name": _get_pattern_name(pattern_id),
                    "status": "detected",
                })

    detected_docs.extend(additional_detected)

    return {
        "total_required": len(required_documents),
        "detected_count": len(detected_docs),
        "missing_count": len(missing_docs),
        "detected": detected_docs,
        "missing": missing_docs,
        "summary": (
            f"{len(detected_docs)} of {len(required_documents)} required documents "
            f"detected. {len(missing_docs)} document(s) potentially missing."
        ),
    }


def build_confidence_summary(result_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a plain-English confidence summary from the processed data.

    Returns:
        Dict with overall confidence, per-category confidence, and summary text
    """
    confidence = compute_composite_confidence(result_data)
    score = confidence.get("confidence_score", 0)
    label = confidence.get("confidence_label", "low")
    breakdown = confidence.get("breakdown", {})

    # Build summary text
    if label == "high":
        if result_data.get("status") == "completed":
            summary_text = (
                "High confidence overall. All processing stages completed "
                "successfully with strong extraction quality."
            )
        else:
            summary_text = (
                "High confidence in the extracted data, though some processing "
                "stages were not fully completed."
            )
    elif label == "medium":
        summary_text = (
            "Moderate confidence. Some data gaps exist that may affect the "
            "reliability of certain sections. Review noted gaps before use."
        )
    elif label == "low":
        summary_text = (
            "Low confidence. Significant data quality or completeness issues "
            "were detected. Use this report as a starting point for manual review."
        )
    else:
        summary_text = (
            "Confidence could not be reliably determined due to insufficient data."
        )

    return {
        "overall_score": round(score, 3),
        "label": label,
        "summary_text": summary_text,
        "breakdown": {
            "extraction": round(breakdown.get("extraction", 0), 3),
            "boq": round(breakdown.get("boq", 0), 3),
            "pricing": round(breakdown.get("pricing", 0), 3),
            "ocr_penalty": round(breakdown.get("ocr_penalty", 0), 3),
            "missing_penalty": round(breakdown.get("missing_penalty", 0), 3),
        },
        "levels": {
            "extraction": _score_to_label(breakdown.get("extraction", 0) * 100),
            "boq": _score_to_label(breakdown.get("boq", 0) * 100),
            "pricing": _score_to_label(breakdown.get("pricing", 0) * 100),
        },
    }


def build_risk_summary(result_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a summary of identified risks from processing data.

    Returns:
        Dict with risk level, list of risks, and overall assessment
    """
    risks: List[Dict[str, Any]] = []
    warnings = result_data.get("warnings", []) or []
    failed_stages = result_data.get("failed_stages", []) or []
    status = result_data.get("status", "unknown")

    # ── Risk: Processing failure ─────────────────────────────────────
    if status == "failed":
        risks.append({
            "category": "processing",
            "severity": "critical",
            "title": "Processing Failed",
            "description": "The pipeline was unable to complete processing. No reliable data is available.",
            "actionable": True,
        })
    elif status == "partial_success":
        risks.append({
            "category": "processing",
            "severity": "high",
            "title": "Partial Processing Only",
            "description": "Some processing stages failed. Data may be incomplete.",
            "actionable": True,
        })

    # ── Risk: Failed stages ──────────────────────────────────────────
    if failed_stages:
        for stage in failed_stages:
            stage_label = stage.replace("_", " ").title()
            risks.append({
                "category": "pipeline",
                "severity": "high",
                "title": f"Stage Failed: {stage_label}",
                "description": f"The '{stage_label}' processing stage did not complete successfully.",
                "actionable": True,
            })

    # ── Risk: No sector detected ─────────────────────────────────────
    if not result_data.get("detected_sector"):
        risks.append({
            "category": "data_quality",
            "severity": "high",
            "title": "Sector Not Detected",
            "description": "The tender sector was not identified, which affects pricing and workforce estimates.",
            "actionable": True,
        })

    # ── Risk: No pricing data ────────────────────────────────────────
    if not result_data.get("pricing_result"):
        risks.append({
            "category": "data_quality",
            "severity": "critical",
            "title": "Pricing Unavailable",
            "description": "Pricing calculation could not be performed. Critical for bid submission.",
            "actionable": True,
        })

    # ── Risk: No BOQ items ───────────────────────────────────────────
    boq_items = result_data.get("boq_items", []) or []
    if not boq_items:
        risks.append({
            "category": "data_quality",
            "severity": "critical",
            "title": "No Bill of Quantities",
            "description": "No BOQ items were extracted. This is essential for pricing and scope understanding.",
            "actionable": True,
        })
    else:
        # Check for items with missing rates
        missing_rates = sum(1 for i in boq_items if i.get("rate") is None)
        if missing_rates > 0:
            risks.append({
                "category": "data_quality",
                "severity": "medium",
                "title": f"{missing_rates} BOQ Items Missing Rates",
                "description": f"{missing_rates} of {len(boq_items)} items have no rate data.",
                "actionable": True,
            })

    # ── Risk: No duration ────────────────────────────────────────────
    if result_data.get("detected_duration_months") is None:
        risks.append({
            "category": "data_quality",
            "severity": "medium",
            "title": "Duration Not Detected",
            "description": "Project duration was not found, which may affect workforce planning.",
            "actionable": True,
        })

    # ── Risk: OCR usage ──────────────────────────────────────────────
    extraction_method = result_data.get("extraction_method", "")
    if "ocr" in extraction_method.lower():
        risks.append({
            "category": "quality",
            "severity": "medium",
            "title": "OCR Fallback Used",
            "description": "Text was extracted using OCR, which may reduce accuracy for numbers and tables.",
            "actionable": False,
        })

    # ── Risk: High warning count ─────────────────────────────────────
    if len(warnings) > 5:
        risks.append({
            "category": "pipeline",
            "severity": "medium",
            "title": f"{len(warnings)} Processing Warnings",
            "description": f"There are {len(warnings)} warnings from the processing pipeline. Review for details.",
            "actionable": True,
        })

    # ── Determine overall risk level ─────────────────────────────────
    if any(r["severity"] == "critical" for r in risks):
        overall_risk = "high"
        overall_assessment = "Significant risks detected. Submission is not recommended without addressing critical issues."
    elif any(r["severity"] == "high" for r in risks):
        overall_risk = "medium"
        overall_assessment = "Moderate risks detected. Review and address high-severity items before submission."
    else:
        overall_risk = "low"
        overall_assessment = "Low risk profile. The tender appears well-prepared with minimal issues."

    return {
        "overall_risk_level": overall_risk,
        "overall_assessment": overall_assessment,
        "risk_count": len(risks),
        "critical_count": sum(1 for r in risks if r["severity"] == "critical"),
        "high_count": sum(1 for r in risks if r["severity"] == "high"),
        "medium_count": sum(1 for r in risks if r["severity"] == "medium"),
        "low_count": sum(1 for r in risks if r["severity"] == "low"),
        "risks": risks,
    }


def generate_recommendations(
    result_data: Dict[str, Any],
    score_data: Dict[str, Any],
    missing_info: Dict[str, Any],
    missing_docs: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Generate actionable recommendations based on readiness assessment.

    Returns:
        List of recommendation dicts with priority, category, message, and action
    """
    recommendations: List[Dict[str, Any]] = []
    status = result_data.get("status", "unknown")

    # ── Recommendation: Processing failure ───────────────────────────
    if status == "failed":
        recommendations.append(_make_rec(
            priority="critical",
            category="processing",
            title="Re-process the tender document",
            message="The processing pipeline failed. Try uploading a clearer copy of the document, "
                    "preferably a text-based PDF rather than a scanned image.",
            action="re_upload",
        ))
        return recommendations  # No point in further recommendations if processing failed

    # ── Recommendation: Missing critical fields ───────────────────────
    for mf in missing_info.get("missing_fields", []):
        severity = mf.get("severity", "low")
        if severity in ("critical", "high"):
            recommendations.append(_make_rec(
                priority=_severity_to_priority(severity),
                category="data_gap",
                title=f"Add missing: {mf['label']}",
                message=mf["reason"],
                action=f"provide_{mf['field']}",
            ))

    # ── Recommendation: Missing documents ────────────────────────────
    for md in missing_docs.get("missing", []):
        recommendations.append(_make_rec(
            priority="high",
            category="document",
            title=f"Obtain: {md['name']}",
            message=f"The document '{md['name']}' was not detected in the submission. "
                    f"This may be required for a complete bid response.",
            action="obtain_document",
        ))

    # ── Recommendation: Low extraction quality ───────────────────────
    extraction_score = score_data.get("categories", {}).get("extraction_quality", {}).get("score", 100)
    if extraction_score < 50:
        recommendations.append(_make_rec(
            priority="high",
            category="quality",
            title="Improve document quality",
            message="Text extraction quality is low. Consider using a text-based PDF (not scanned) "
                    "to improve data extraction accuracy.",
            action="improve_document",
        ))

    # ── Recommendation: Low BOQ completeness ──────────────────────────
    boq_category = score_data.get("categories", {}).get("boq_completeness", {})
    if boq_category.get("score", 100) < 50:
        recommendations.append(_make_rec(
            priority="high",
            category="boq",
            title="Complete Bill of Quantities",
            message="The Bill of Quantities is incomplete. Ensure all line items have descriptions, "
                    "rates, and amounts filled in.",
            action="complete_boq",
        ))

    # ── Recommendation: No pricing data ──────────────────────────────
    if not result_data.get("pricing_result"):
        recommendations.append(_make_rec(
            priority="critical",
            category="pricing",
            title="Perform pricing calculation",
            message="No pricing data is available. A complete pricing calculation is essential "
                    "for bid submission. Provide rates for the BOQ items.",
            action="calculate_pricing",
        ))

    # ── Recommendation: OCR fallback ─────────────────────────────────
    extraction_method = result_data.get("extraction_method", "")
    if "ocr" in extraction_method.lower():
        recommendations.append(_make_rec(
            priority="medium",
            category="quality",
            title="Verify OCR-extracted data",
            message="OCR was used for text extraction. Double-check all numbers, rates, and amounts "
                    "for accuracy, as OCR can introduce errors.",
            action="verify_ocr_data",
        ))

    # ── Recommendation: Partial success ──────────────────────────────
    if status == "partial_success":
        recommendations.append(_make_rec(
            priority="high",
            category="processing",
            title="Retry failed processing stages",
            message="Some processing stages failed. Use the retry endpoint to re-attempt "
                    "failed stages without re-uploading the document.",
            action="retry_pipeline",
        ))

    # ── Recommendation: General readiness ────────────────────────────
    overall_score = score_data.get("overall_score", 0)
    if overall_score >= 80:
        recommendations.append(_make_rec(
            priority="low",
            category="readiness",
            title="Tender ready for submission",
            message="The tender data is well-prepared. Proceed with final review and submission.",
            action="finalize",
        ))

    # Sort by priority order: critical > high > medium > low
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(key=lambda r: priority_order.get(r.get("priority", "low"), 99))

    return recommendations


def build_dashboard_payload(
    result_data: Dict[str, Any],
    score_data: Dict[str, Any],
    risk_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a lightweight payload for dashboard integration.

    Returns:
        Dict with summary fields safe for dashboard display
    """
    return {
        "readiness_score": score_data.get("overall_score", 0),
        "readiness_label": score_data.get("label", "unknown"),
        "risk_level": risk_summary.get("overall_risk_level", "unknown"),
        "risk_count": risk_summary.get("risk_count", 0),
        "missing_fields_count": 0,  # Filled in caller
        "missing_documents_count": 0,  # Filled in caller
        "confidence_label": _get_confidence_label(result_data),
        "status": result_data.get("status", "unknown"),
        "has_pricing": result_data.get("pricing_result") is not None,
        "has_boq": len(result_data.get("boq_items", []) or []) > 0,
        "has_workforce": bool(result_data.get("detected_workforce")),
    }


# ── Private scoring functions ─────────────────────────────────────


def _score_extraction_quality(result_data: Dict[str, Any]) -> float:
    """Score text extraction quality (0–100)."""
    text_length = result_data.get("text_length", 0) or 0
    extraction_method = result_data.get("extraction_method", "")

    if text_length == 0:
        return 0.0

    # Score based on text length
    if text_length >= 10000:
        length_score = 100.0
    elif text_length >= 5000:
        length_score = 85.0
    elif text_length >= 1000:
        length_score = 60.0
    elif text_length >= 200:
        length_score = 30.0
    else:
        length_score = 10.0

    # OCR penalty
    if "ocr" in extraction_method.lower():
        length_score *= 0.75  # 25% penalty for OCR

    return length_score


def _score_entity_completeness(result_data: Dict[str, Any]) -> float:
    """Score entity extraction completeness (0–100)."""
    present = 0
    total = 4  # sector, duration, locations, schedule

    if result_data.get("detected_sector"):
        present += 1
    if result_data.get("detected_duration_months") is not None:
        present += 1
    locations = result_data.get("detected_locations", [])
    if locations and len(locations) > 0:
        present += 1
    schedule = result_data.get("detected_schedule", {})
    if schedule:
        present += 1

    return (present / total) * 100.0


def _score_boq_completeness(result_data: Dict[str, Any]) -> float:
    """Score BOQ completeness (0–100)."""
    boq_items = result_data.get("boq_items", []) or []
    if not boq_items:
        return 0.0

    item_count = len(boq_items)

    # Score based on item count
    if item_count >= 30:
        count_score = 100.0
    elif item_count >= 15:
        count_score = 80.0
    elif item_count >= 5:
        count_score = 50.0
    else:
        count_score = 30.0

    # Rate/amount coverage
    items_with_rates = sum(1 for i in boq_items if i.get("rate") is not None)
    items_with_amounts = sum(1 for i in boq_items if i.get("amount") is not None)

    rate_coverage = (items_with_rates / item_count) * 100 if item_count > 0 else 0
    amount_coverage = (items_with_amounts / item_count) * 100 if item_count > 0 else 0
    coverage_score = (rate_coverage * 0.5 + amount_coverage * 0.5)

    # BOQ confidence multiplier
    boq_confidence = result_data.get("boq_confidence", "")
    confidence_multiplier = 1.0
    if boq_confidence == "High":
        confidence_multiplier = 1.0
    elif boq_confidence == "Medium":
        confidence_multiplier = 0.75
    elif boq_confidence == "Low":
        confidence_multiplier = 0.5
    else:
        confidence_multiplier = 0.4

    return (count_score * 0.4 + coverage_score * 0.6) * confidence_multiplier


def _score_pricing_availability(result_data: Dict[str, Any]) -> float:
    """Score pricing availability (0–100)."""
    pricing_result = result_data.get("pricing_result")
    if not pricing_result:
        return 0.0

    # Check pricing method
    method = pricing_result.get("price_reliability", "")
    if method == "boq_based":
        method_score = 100.0
    elif method == "estimated":
        method_score = 60.0
    elif method == "low":
        method_score = 30.0
    else:
        method_score = 50.0

    # Check if key fields are present
    has_total = pricing_result.get("total_monthly") is not None or \
                pricing_result.get("final_contract_value") is not None
    has_vat = pricing_result.get("vat") is not None
    has_breakdown = (
        pricing_result.get("labour_cost") is not None or
        pricing_result.get("materials_cost") is not None
    )

    completeness = 0.0
    if has_total:
        completeness += 0.4
    if has_vat:
        completeness += 0.3
    if has_breakdown:
        completeness += 0.3

    return method_score * (0.5 + completeness * 0.5)


def _score_workforce_availability(result_data: Dict[str, Any]) -> float:
    """Score workforce data availability (0–100)."""
    workforce = result_data.get("detected_workforce", {})
    if not workforce:
        return 0.0

    total_workers = workforce.get("total_workers")
    if total_workers is None:
        return 20.0  # Some data but no total

    try:
        total = int(total_workers)
        if total > 0:
            return 100.0
        return 30.0
    except (ValueError, TypeError):
        return 20.0


def _score_document_integrity(result_data: Dict[str, Any]) -> float:
    """Score document/pipeline integrity (0–100)."""
    status = result_data.get("status", "unknown")
    warnings = result_data.get("warnings", []) or []
    failed_stages = result_data.get("failed_stages", []) or []

    # Base score on status
    if status == "completed":
        base = 90.0
    elif status == "partial_success":
        base = 50.0
    elif status == "failed":
        base = 10.0
    else:
        base = 30.0

    # Deduct for warnings
    warning_penalty = min(len(warnings) * 5, 30)  # Max 30% penalty
    # Deduct for failed stages
    failure_penalty = min(len(failed_stages) * 15, 45)  # Max 45% penalty

    return max(0.0, base - warning_penalty - failure_penalty)


# ── Private helpers ──────────────────────────────────────────────


def _score_to_label(score: float) -> str:
    """Convert a numeric score (0–100) to a label."""
    if score >= 80:
        return "high"
    elif score >= 50:
        return "medium"
    elif score >= 25:
        return "low"
    return "critical"


def _severity_to_priority(severity: str) -> str:
    """Map field severity to recommendation priority."""
    mapping = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
    }
    return mapping.get(severity, "medium")


def _make_rec(
    priority: str,
    category: str,
    title: str,
    message: str,
    action: str,
) -> Dict[str, Any]:
    """Create a structured recommendation."""
    return {
        "priority": priority,
        "category": category,
        "title": title,
        "message": message,
        "action": action,
    }


def _get_confidence_label(result_data: Dict[str, Any]) -> str:
    """Get the confidence label from result data."""
    confidence = compute_composite_confidence(result_data)
    return confidence.get("confidence_label", "low")


def _get_pattern_name(pattern_id: str) -> str:
    """Get human-readable name for a document pattern ID."""
    names = {
        "submission_letter": "Submission / Covering Letter",
        "sbd_form": "Standard Bidding Document (SBD) Form",
        "tax_clearance": "Tax Clearance Certificate",
        "company_registration": "Company Registration Document",
        "bbbeee_certificate": "B-BBEE Certificate / Affidavit",
        "bid_guarantee": "Bid Guarantee / Tender Bond",
        "proof_of_address": "Proof of Address",
        "id_document": "ID Document / Passport",
        "declaration_of_interest": "Declaration of Interest",
    }
    return names.get(pattern_id, pattern_id.replace("_", " ").title())


def _get_document_severity(doc_id: str) -> str:
    """Determine severity level for a missing document."""
    critical_docs = {"sbd1", "sbd2", "sbd3", "sbd4", "sbd5", "sbd7", "bid_document", "bill_of_quantities"}
    high_docs = {"sbd6", "sbd8", "sbd9", "specifications", "company_profile", "letter_of_goodstanding"}
    if doc_id in critical_docs:
        return "critical"
    elif doc_id in high_docs:
        return "high"
    return "medium"


# ═══════════════════════════════════════════════════════════════════════
# PDF READINESS ASSESSMENT GENERATION (NEW)
# ═══════════════════════════════════════════════════════════════════════


def _determine_overall_status(result_data: Dict[str, Any], score_data: Dict[str, Any],
                               risk_summary: Dict[str, Any]) -> Tuple[str, str, Any]:
    """Determine the overall readiness status using deterministic business rules.

    Returns:
        (status_text, status_description, status_style)
    """
    status = result_data.get("status", "unknown")
    score = score_data.get("overall_score", 0)
    risk_level = risk_summary.get("overall_risk_level", "low")
    has_pricing = result_data.get("pricing_result") is not None
    has_boq = len(result_data.get("boq_items", []) or []) > 0
    has_sector = result_data.get("detected_sector") is not None
    has_duration = result_data.get("detected_duration_months") is not None
    failed_stages = result_data.get("failed_stages", []) or []

    # Deterministic rules (priority order)
    if status == "failed":
        return (
            "Submission Not Ready",
            "The document could not be processed. No reliable data is available for submission.",
            STATUS_NOTREADY_STYLE,
        )

    if not has_pricing or not has_boq:
        return (
            "Manual Review Required",
            "Critical data gaps detected. Pricing or Bill of Quantities is missing.",
            STATUS_REVIEW_STYLE,
        )

    if risk_level == "high":
        return (
            "Manual Review Required",
            "Significant risks detected. Address critical issues before submission.",
            STATUS_REVIEW_STYLE,
        )

    if status == "partial_success" or len(failed_stages) > 0:
        return (
            "Ready with Minor Actions",
            "Processing completed with some issues. Review flagged items before submission.",
            STATUS_MINOR_STYLE,
        )

    if not has_sector or not has_duration:
        return (
            "Ready with Minor Actions",
            "Basic tender information is partially complete. Verify sector and duration details.",
            STATUS_MINOR_STYLE,
        )

    if score >= 80 and risk_level == "low":
        return (
            "Ready for Submission",
            "All critical fields verified. The tender is well-prepared for submission.",
            STATUS_READY_STYLE,
        )

    if score >= 50:
        return (
            "Ready with Minor Actions",
            "Most requirements are met. Review minor gaps before submission.",
            STATUS_MINOR_STYLE,
        )

    return (
        "Manual Review Required",
        "Significant gaps detected. Manual review and completion required.",
        STATUS_REVIEW_STYLE,
    )


def _build_verification_summary(result_data: Dict[str, Any]) -> List[Tuple[str, bool, str]]:
    """Build a list of verification items with their status.

    Returns:
        List of (label, is_verified, detail) tuples
    """
    metadata = result_data.get("metadata", {}) or {}
    full_text = result_data.get("full_text")
    boq_items = result_data.get("boq_items", []) or []
    pricing_result = result_data.get("pricing_result")
    has_sector = result_data.get("detected_sector") is not None
    has_duration = result_data.get("detected_duration_months") is not None
    has_locations = len(result_data.get("detected_locations", []) or []) > 0

    items: List[Tuple[str, bool, str]] = []

    # Project
    project_verified = bool(
        metadata.get("project_name") or metadata.get("project_title") or
        metadata.get("tender_name") or
        (full_text and "project" in full_text.lower())
    )
    items.append(("Project", project_verified,
                  "Project title extracted" if project_verified else "Not confidently identified"))

    # Tender Reference
    tender_verified = bool(
        metadata.get("tender_number") or metadata.get("tender_reference") or
        metadata.get("reference_number")
    )
    items.append(("Tender Reference", tender_verified,
                  "Tender reference extracted" if tender_verified else "Not confidently identified"))

    # BOQ
    boq_verified = len(boq_items) > 0
    items.append(("Bill of Quantities (BOQ)", boq_verified,
                  f"{len(boq_items)} items extracted" if boq_verified else "Not extracted"))

    # Pricing
    pricing_verified = pricing_result is not None
    items.append(("Pricing", pricing_verified,
                  "Pricing calculated" if pricing_verified else "Not calculated"))

    # Executive Summary (sector + duration + locations)
    exec_verified = has_sector or has_duration or has_locations
    exec_details = []
    if has_sector:
        exec_details.append("sector")
    if has_duration:
        exec_details.append("duration")
    if has_locations:
        exec_details.append("locations")
    items.append(("Executive Summary", exec_verified,
                  f"Data available: {', '.join(exec_details)}" if exec_details else "Insufficient data"))

    # Submission Letter (always available — generated by system)
    items.append(("Submission Letter", True,
                  "Available for download"))

    # Submission Package (always available — generated by system)
    items.append(("Submission Package", True,
                  "Available for download"))

    return items


def _build_manual_review_fields(result_data: Dict[str, Any]) -> List[str]:
    """Build a list of fields that require manual attention.

    Returns:
        List of field descriptions requiring manual completion
    """
    fields = []
    metadata = result_data.get("metadata", {}) or {}

    # Employer
    if not metadata.get("employer") and not metadata.get("procuring_entity") and not metadata.get("client_name"):
        fields.append("Employer / Procuring Entity")

    # Applicant / Company
    if not metadata.get("company_name") and not metadata.get("organisation") and not metadata.get("bidder_name"):
        fields.append("Applicant / Company Name")

    # Banking Details (always requires manual input — not extractable from tender docs)
    fields.append("Banking Details")

    # Company Registration
    if not metadata.get("company_registration"):
        fields.append("Company Registration")

    # Contact Information
    if not metadata.get("contact_person") and not metadata.get("email") and not metadata.get("telephone"):
        fields.append("Contact Information")

    return fields


def _build_missing_docs_checklist(result_data: Dict[str, Any], schema: Dict[str, Any]) -> List[Tuple[str, bool]]:
    """Build a checklist of commonly required tender documents.

    Args:
        result_data: The full Processing Result dict
        schema: The compliance schema to use

    Returns:
        List of (document_name, is_detected) tuples
    """
    full_text = result_data.get("full_text", "") or ""
    full_text_lower = full_text.lower()

    # Get document checks from schema, fallback to defaults if missing
    doc_checks = schema.get("document_checklist", [
        ("Tax Clearance Certificate", ["tax clearance", "tax certificate", "tax pin", "sars"]),
        ("CSD Registration (Central Supplier Database)", ["csd", "central supplier database", "supplier database"]),
        ("CIDB Registration", ["cidb", "construction industry development board"]),
        ("B-BBEE Certificate / Affidavit", ["bbbee", "b-bbee", "broad-based black", "empowerment", "level 1", "level 2"]),
        ("Proof of Banking Details", ["banking details", "bank confirmation", "bank letter", "proof of bank"]),
        ("Signed Declaration of Interest", ["declaration of interest", "conflict of interest", "sbd 3"]),
    ])

    results = []
    for doc_name, keywords in doc_checks:
        found = any(kw in full_text_lower for kw in keywords)
        results.append((doc_name, found))

    return results


def _build_risk_assessment(result_data: Dict[str, Any], risk_summary: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Build risk assessment with deterministic explanations.

    Returns:
        (risk_level, list_of_explanations)
    """
    risk_level = risk_summary.get("overall_risk_level", "low")
    explanations = []

    status = result_data.get("status", "unknown")
    failed_stages = result_data.get("failed_stages", []) or []
    warnings = result_data.get("warnings", []) or []
    has_pricing = result_data.get("pricing_result") is not None
    has_boq = len(result_data.get("boq_items", []) or []) > 0
    has_sector = result_data.get("detected_sector") is not None
    extraction_method = result_data.get("extraction_method", "")

    # Build explanations from verified findings only
    if status == "failed":
        explanations.append("Document processing failed — no reliable data available.")
    if status == "partial_success":
        explanations.append("Some processing stages did not complete successfully.")
    if not has_pricing:
        explanations.append("Pricing data is missing — critical for bid submission.")
    if not has_boq:
        explanations.append("Bill of Quantities was not extracted.")
    if not has_sector:
        explanations.append("Tender sector was not identified.")
    if len(failed_stages) > 0:
        stages = ", ".join(s.replace("_", " ") for s in failed_stages)
        explanations.append(f"Failed processing stages: {stages}.")
    if "ocr" in extraction_method.lower():
        explanations.append("OCR was used — numeric data may require verification.")
    if len(warnings) > 5:
        explanations.append(f"{len(warnings)} processing warnings recorded.")

    if not explanations:
        explanations.append("No significant risks detected based on verified extraction data.")

    return risk_level, explanations


def _build_recommendations_list(result_data: Dict[str, Any], score_data: Dict[str, Any],
                                 missing_info: Dict[str, Any], missing_docs: Dict[str, Any]) -> List[str]:
    """Generate practical recommendations based solely on missing verified information.

    Returns:
        List of recommendation strings
    """
    recs = []
    status = result_data.get("status", "unknown")

    if status == "failed":
        recs.append("Re-upload the document in a supported format (PDF, DOCX, or TXT).")
        return recs

    # Missing critical fields
    for mf in missing_info.get("missing_fields", []):
        if mf.get("severity") in ("critical", "high"):
            recs.append(f"Complete {mf['label'].lower()} information before submission.")

    # Employer
    metadata = result_data.get("metadata", {}) or {}
    if not metadata.get("employer") and not metadata.get("procuring_entity"):
        recs.append("Verify employer / procuring entity details.")

    # Applicant
    if not metadata.get("company_name") and not metadata.get("organisation"):
        recs.append("Complete applicant information before submission.")

    # Missing documents
    for md in missing_docs.get("missing", [])[:5]:  # Top 5 most important
        recs.append(f"Attach outstanding document: {md['name']}.")

    # OCR
    extraction_method = result_data.get("extraction_method", "")
    if "ocr" in extraction_method.lower():
        recs.append("Verify all OCR-extracted numbers and amounts for accuracy.")

    # Partial success
    if status == "partial_success":
        recs.append("Retry failed processing stages to improve data completeness.")

    # General readiness
    score = score_data.get("overall_score", 0)
    if score >= 80:
        recs.append("Proceed with final review and submission.")

    if not recs:
        recs.append("Review all extracted data before submission.")

    return recs


def _build_brand_header(story) -> None:
    """Build the Tender Engine brand header (consistent with submission letter)."""
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Tender Engine", BRAND_TITLE_STYLE))
    story.append(Paragraph(
        "Tender Readiness Assessment",
        BRAND_SUBTITLE_STYLE,
    ))
    story.append(Spacer(1, 0.2 * cm))
    story.append(HRFlowable(
        width="100%", thickness=1.5, color=PRIMARY_BLUE,
        spaceAfter=2, spaceBefore=2,
    ))
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=ACCENT_BLUE,
        spaceAfter=14, spaceBefore=2,
    ))


def _build_status_section(story, status_text: str, status_description: str, status_style: Any) -> None:
    """Build the Overall Status section."""
    story.append(Paragraph("Overall Status", SECTION_STYLE))
    story.append(Spacer(1, 0.2 * cm))

    # Status box
    status_box_data = [[
        Paragraph(f"<b>{status_text}</b>", status_style),
    ]]
    status_table = Table(status_box_data, colWidths=[16 * cm])
    status_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, status_style.textColor if hasattr(status_style, 'textColor') else PRIMARY_BLUE),
        ("BACKGROUND", (0, 0), (-1, -1), VERY_LIGHT_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(KeepTogether(status_table))

    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(status_description, BODY_STYLE))
    story.append(Spacer(1, 0.3 * cm))


def _build_verification_section(story, verification_items: List[Tuple[str, bool, str]]) -> None:
    """Build the Verification Summary section."""
    story.append(Paragraph("Verification Summary", SECTION_STYLE))
    story.append(Spacer(1, 0.2 * cm))

    for label, verified, detail in verification_items:
        if verified:
            story.append(Paragraph(
                f'✓&nbsp;&nbsp;<font color="{GREEN_VERIFIED}"><b>{label} verified</b></font>'
                f'&nbsp;&nbsp;<font color="{TEXT_MEDIUM}" size="8">({detail})</font>',
                VERIFIED_ITEM_STYLE,
            ))
        else:
            story.append(Paragraph(
                f'✗&nbsp;&nbsp;<font color="{RED_ERROR}"><b>{label} not verified</b></font>'
                f'&nbsp;&nbsp;<font color="{TEXT_LIGHT}" size="8">({detail})</font>',
                BLANK_ITEM_STYLE,
            ))

    story.append(Spacer(1, 0.3 * cm))


def _build_manual_review_section(story, manual_fields: List[str]) -> None:
    """Build the Manual Review Required section."""
    story.append(Paragraph("Manual Review Required", SECTION_STYLE))
    story.append(Spacer(1, 0.2 * cm))

    if not manual_fields:
        story.append(Paragraph(
            "No fields require manual attention based on verified extraction data.",
            ParagraphStyle("NoManualItems", parent=BODY_STYLE, textColor=GREEN_VERIFIED),
        ))
    else:
        story.append(Paragraph(
            "The following fields require user attention before submission:",
            BODY_STYLE,
        ))
        story.append(Spacer(1, 0.1 * cm))
        for field in manual_fields:
            story.append(Paragraph(
                f'•&nbsp;&nbsp;<font color="{AMBER_WARN}"><b>{field}</b></font>'
                f'&nbsp;&nbsp;(requires manual completion)',
                BLANK_ITEM_STYLE,
            ))

    story.append(Spacer(1, 0.3 * cm))


def _build_missing_docs_section(story, doc_checks: List[Tuple[str, bool]]) -> None:
    """Build the Missing Supporting Documents section."""
    story.append(Paragraph("Missing Supporting Documents", SECTION_STYLE))
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph(
        "Commonly required tender documents. Checked against extracted document content.",
        BODY_STYLE,
    ))
    story.append(Spacer(1, 0.1 * cm))

    # Build checklist table
    doc_data = [["Document", "Status"]]
    for doc_name, detected in doc_checks:
        status_icon = "✓ Detected" if detected else "☐ Not detected"
        status_color = GREEN_VERIFIED if detected else TEXT_LIGHT
        doc_data.append([
            doc_name,
            f'<font color="{status_color}">{status_icon}</font>',
        ])

    doc_table = Table(doc_data, colWidths=[10 * cm, 6 * cm])
    doc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    # Alternate row colors
    for i in range(1, len(doc_data)):
        if i % 2 == 0:
            doc_table.setStyle(TableStyle([
                ("BACKGROUND", (0, i), (-1, i), VERY_LIGHT_BG)
            ]))

    story.append(doc_table)
    story.append(Spacer(1, 0.3 * cm))


def _build_readiness_score_section(story, score_data: Dict[str, Any]) -> None:
    """Build the readiness score section with evidence quality deductions."""
    story.append(Paragraph("Readiness Score", SECTION_STYLE))
    story.append(Spacer(1, 0.2 * cm))

    calculation = score_data.get("calculation", {}) or {}
    base_score = calculation.get("base_score", score_data.get("overall_score", 0))
    final_score = calculation.get("final_score", score_data.get("overall_score", 0))
    deductions = calculation.get("deductions", []) or []

    story.append(Paragraph(f"<b>Final Score:</b> {final_score:.1f}%", BODY_BOLD_STYLE))
    story.append(Paragraph(f"Base score before evidence deductions: {base_score:.1f}%", BODY_STYLE))
    story.append(Spacer(1, 0.1 * cm))

    rows = [["Calculation", "Deduction"]]
    if deductions:
        for item in deductions:
            rows.append([item.get("reason", "Evidence deduction"), f"-{item.get('deduction', 0)}"])
    else:
        rows.append(["No evidence-quality deductions applied", "0"])
    rows.append(["Final Score", f"{final_score:.1f}%"])

    table = Table(rows, colWidths=[12 * cm, 4 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.3 * cm))



def _build_evidence_section(story, result_data: Dict[str, Any]) -> None:
    """Build field-level evidence display section."""
    story.append(Paragraph("Verified Extraction Evidence", SECTION_STYLE))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Important extracted values below show where they were found, how they were selected, and how confident the extraction is.",
        BODY_STYLE,
    ))
    story.append(Spacer(1, 0.1 * cm))

    evidence_fields = ((result_data.get("evidence") or {}).get("fields", {}) or {})
    rows = [["Field", "Value", "Verified From"]]
    for field_key, item in evidence_fields.items():
        value = item.get("value")
        if value in (None, "", [], {}):
            continue
        confidence = str(item.get("confidence") or "Missing").title()
        verified_lines = [
            f"Page {item.get('page_number') or 'Unknown'}",
            str(item.get("section") or item.get("source_category") or "Unknown"),
            f"Confidence: {confidence}",
        ]
        if confidence == "Low":
            verified_lines.append("⚠ Verify before submission")
        rows.append([
            str(item.get("field_name") or field_key.replace("_", " ").title()),
            str(value),
            "\n".join(verified_lines),
        ])

    if len(rows) == 1:
        story.append(Paragraph("No evidence-backed extracted values are currently available.", BODY_STYLE))
    else:
        table = Table(rows, colWidths=[4.5 * cm, 5.5 * cm, 6.0 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
    story.append(Spacer(1, 0.3 * cm))



def _build_risk_section(story, risk_level: str, risk_explanations: List[str]) -> None:
    """Build the Risk Assessment section."""
    story.append(Paragraph("Risk Assessment", SECTION_STYLE))
    story.append(Spacer(1, 0.2 * cm))

    # Risk level display
    risk_display = risk_level.upper()
    risk_color = {
        "low": GREEN_VERIFIED,
        "medium": AMBER_WARN,
        "high": RED_ERROR,
    }.get(risk_level, TEXT_DARK)

    risk_bg = {
        "low": GREEN_BG,
        "medium": AMBER_BG,
        "high": RED_BG,
    }.get(risk_level, VERY_LIGHT_BG)

    risk_box = [[
        Paragraph(
            f'<font color="{risk_color}"><b>Overall Risk Level: {risk_display}</b></font>',
            ParagraphStyle("RiskBoxText", parent=BODY_STYLE, alignment=TA_CENTER),
        ),
    ]]
    risk_table = Table(risk_box, colWidths=[16 * cm])
    risk_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, risk_color),
        ("BACKGROUND", (0, 0), (-1, -1), risk_bg),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(KeepTogether(risk_table))
    story.append(Spacer(1, 0.2 * cm))

    # Explanations
    story.append(Paragraph("<b>Deterministic Assessment:</b>", BODY_BOLD_STYLE))
    for explanation in risk_explanations:
        story.append(Paragraph(f"• {explanation}", RECOMMENDATION_STYLE))

    story.append(Spacer(1, 0.3 * cm))


def _build_recommendations_section(story, recommendations_list: List[str]) -> None:
    """Build the Recommendations section."""
    story.append(Paragraph("Recommendations", SECTION_STYLE))
    story.append(Spacer(1, 0.2 * cm))

    if not recommendations_list:
        story.append(Paragraph(
            "No specific recommendations at this time.",
            BODY_STYLE,
        ))
    else:
        for i, rec in enumerate(recommendations_list, 1):
            story.append(Paragraph(
                f"{i}. {rec}",
                RECOMMENDATION_STYLE,
            ))

    story.append(Spacer(1, 0.3 * cm))


def _build_footer(story, job_id: str) -> None:
    """Build the enterprise footer (consistent with submission letter)."""
    story.append(Spacer(1, 20))
    story.append(HRFlowable(
        width="100%", thickness=0.3, color=BORDER_LIGHT,
        spaceAfter=6, spaceBefore=4,
    ))
    story.append(Paragraph(
        "Generated by Tender Engine",
        FOOTER_BOLD_STYLE,
    ))
    story.append(Paragraph(
        "Generated from verified document extraction. "
        "Manual verification required before submission.",
        FOOTER_STYLE,
    ))
    story.append(Spacer(1, 2))
    gen_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(
        f"Version {READINESS_PDF_VERSION} &nbsp;|&nbsp; "
        f"Job ID: {job_id[:16]}... &nbsp;|&nbsp; "
        f"Generated: {gen_timestamp}",
        FOOTER_STYLE,
    ))


def generate_readiness_pdf(
    job_id: str,
    result_dict: Dict[str, Any],
) -> BytesIO:
    """Generate a professional Tender Readiness Assessment PDF.

    This function is deterministic. No generative AI, no guessing, no hallucination.

    Every status, recommendation and assessment is derived only from verified
    extraction results and deterministic business rules.

    Sections:
      1. Overall Status (Ready for Submission / Ready with Minor Actions /
         Manual Review Required / Submission Not Ready)
      2. Verification Summary
      3. Manual Review Required
      4. Missing Supporting Documents
      5. Risk Assessment (Low / Medium / High)
      6. Recommendations

    Args:
        job_id: The processing job ID
        result_dict: The full processing result dictionary

    Returns:
        BytesIO stream containing the generated PDF
    """
    # ── Get compliance schema ───────────────────────────────────────
    detected_jurisdiction = SchemaManager.detect_jurisdiction(result_dict)
    schema = SchemaManager.get_schema_for_jurisdiction(detected_jurisdiction)
    
    # ── Compute all assessment data ──────────────────────────────────
    score_data = compute_readiness_score(result_dict, schema)
    missing_info = detect_missing_information(result_dict, schema)
    missing_docs = detect_missing_documents(result_dict, schema)
    risk_summary = build_risk_summary(result_dict)

    # ── Build assessment sections ────────────────────────────────────
    status_text, status_description, status_style = _determine_overall_status(
        result_dict, score_data, risk_summary,
    )
    verification_items = _build_verification_summary(result_dict)
    manual_fields = _build_manual_review_fields(result_dict)
    doc_checks = _build_missing_docs_checklist(result_dict, schema)
    risk_level, risk_explanations = _build_risk_assessment(result_dict, risk_summary)
    recommendations_list = _build_recommendations_list(result_dict, score_data, missing_info, missing_docs)

    # ── Build PDF ────────────────────────────────────────────────────
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=2.5 * cm,
        bottomMargin=2.0 * cm,
    )

    story = []

    # ── Build document sections ──────────────────────────────────────
    _build_brand_header(story)
    _build_status_section(story, status_text, status_description, status_style)
    _build_readiness_score_section(story, score_data)
    _build_verification_section(story, verification_items)
    _build_evidence_section(story, result_dict)
    _build_manual_review_section(story, manual_fields)
    _build_missing_docs_section(story, doc_checks)
    _build_risk_section(story, risk_level, risk_explanations)
    _build_recommendations_section(story, recommendations_list)
    _build_footer(story, job_id)

    # ── Build PDF ─────────────────────────────────────────────────────
    try:
        doc.build(story)
        buf.seek(0)
        logger.info(
            "[READINESS] PDF assessment generated for job %s — status=%s risk=%s v%s",
            job_id, status_text, risk_level, READINESS_PDF_VERSION,
        )
        return buf
    except Exception as e:
        logger.exception("[READINESS] Failed to build PDF assessment for job %s", job_id)
        raise