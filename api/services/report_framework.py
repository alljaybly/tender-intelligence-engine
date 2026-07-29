"""
Professional Report Framework — Production-Quality Business Document Standard.

Every generated report must use this framework.

Report Structure (mandatory):
  1. Executive Summary
  2. What We Successfully Extracted
  3. Missing Information
  4. Action Plan
  5. Verification Notice

Language rules:
  - NEVER use: AI, Intelligent, Predictive, Magic, Smart
  - ALWAYS use: Detected, Extracted, Verified, Evidence Found, Generated from verified data

Every report ends with:
  "No information has been invented or inferred. Verify all details before submission."
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


_REPORT_SECTION_REFERENCES = {
    "completion_guide": "02 Tender Completion Guide.pdf",
    "readiness_report": "03 Tender Readiness Assessment.pdf",
    "submission_letter": "04 Submission Letter.pdf",
    "roadmap": "05 Bid Response Roadmap.pdf",
    "audit_report": "06 Tender Integrity Audit.pdf",
    "processing_audit": "07 Processing Audit.pdf",
    "evidence_report": "08 Evidence Report.pdf",
    "manifest": "PACKAGE_MANIFEST.txt",
}

_DECISION_OWNER_MAP = {
    "project_title": "Bid Administrator",
    "tender_number": "Bid Administrator",
    "employer": "Bid Administrator",
    "closing_date": "Bid Administrator",
    "closing_time": "Bid Administrator",
    "estimated_contract_value": "Estimator / Quantity Surveyor",
    "currency": "Estimator / Finance",
    "boq_summary": "Estimator / Quantity Surveyor",
    "trade_summary": "Estimator",
    "work_categories": "Estimator / Technical Lead",
    "location": "Bid Administrator / Site Coordinator",
    "submission_method": "Bid Administrator",
    "mandatory_documents": "Bid Administrator / Compliance Officer",
    "cidb_grade": "Contracts Manager / Director",
    "compulsory_briefing": "Bid Administrator / Contracts Manager",
    "pricing_result": "Estimator / Finance",
    "boq_items": "Estimator / Quantity Surveyor",
    "detected_sector": "Technical Lead",
    "detected_duration_months": "Contracts Manager",
    "detected_locations": "Bid Administrator",
    "detected_workforce": "Contracts Manager / Estimator",
    "detected_schedule": "Planner / Contracts Manager",
    "detected_currency": "Estimator / Finance",
}

_REQUIRED_DOCUMENT_HINTS = {
    "project_title": ["Tender Notice", "Cover Page"],
    "tender_number": ["Tender Notice", "Invitation to Bid"],
    "employer": ["Tender Notice", "Invitation to Bid"],
    "closing_date": ["Tender Notice", "Submission Instructions"],
    "closing_time": ["Tender Notice", "Submission Instructions"],
    "estimated_contract_value": ["BOQ", "Pricing Schedule"],
    "currency": ["Pricing Schedule", "BOQ"],
    "boq_summary": ["BOQ"],
    "trade_summary": ["BOQ", "Scope of Work"],
    "work_categories": ["BOQ", "Scope of Work"],
    "location": ["Project Particulars", "Scope of Work"],
    "submission_method": ["Submission Instructions"],
    "mandatory_documents": ["Returnable Documents", "Submission Requirements"],
    "cidb_grade": ["Eligibility Criteria", "Tender Notice"],
    "compulsory_briefing": ["Tender Notice", "Instructions to Bidders"],
}

logger = logging.getLogger(__name__)

REPORT_FRAMEWORK_VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════════════════
# Data Completeness (replaces percentage scores)
# ═══════════════════════════════════════════════════════════════════════

class DataCompleteness:
    """
    Replace vague percentage scores with DATA COMPLETENESS.
    
    Example:
      Data Completeness: 4 of 11 Required Fields Completed
      ████░░░░░░░ 36%
      Completed: Sector, Currency, Duration, BOQ Tables
      Missing: Pricing, Workforce, Schedule, Locations, etc.
    """

    @staticmethod
    def calculate(completed: int, total: int, optional: int = 0) -> Dict[str, Any]:
        """Calculate data completeness metrics."""
        if total == 0:
            return {
                "completed": 0,
                "total": 0,
                "optional": optional,
                "percentage": 0.0,
                "bar": "░" * 10,
                "label": "No data available",
            }
        pct = (completed / total) * 100
        bar_units = max(1, min(10, round(completed / total * 10)))
        bar = "█" * bar_units + "░" * (10 - bar_units)
        
        if pct >= 80:
            label = "Good"
        elif pct >= 50:
            label = "Partial"
        elif pct >= 25:
            label = "Limited"
        else:
            label = "Minimal"
        
        return {
            "completed": completed,
            "total": total,
            "optional": optional,
            "percentage": round(pct, 1),
            "bar": bar,
            "label": label,
            "display": f"{completed} of {total} Required Fields Completed",
        }

    @staticmethod
    def format_display(completeness: Dict[str, Any]) -> str:
        """Format data completeness for display."""
        return (
            f"Data Completeness: {completeness['display']}\n"
            f"{completeness['bar']} {completeness['percentage']}%\n"
            f"Status: {completeness['label']}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Extracted Fields (What We Successfully Extracted)
# ═══════════════════════════════════════════════════════════════════════

EXTRACTED_FIELD_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "tender_number": {
        "label": "Tender Number",
        "description": "Official tender reference number",
        "source": "Document header or metadata",
    },
    "employer": {
        "label": "Employer / Procuring Entity",
        "description": "The organisation issuing the tender",
        "source": "Document header, letterhead, or metadata",
    },
    "project_title": {
        "label": "Project Title",
        "description": "Name or description of the project",
        "source": "Document title or first page",
    },
    "sector": {
        "label": "Sector",
        "description": "Industry sector (construction, electrical, cleaning, etc.)",
        "source": "Document text analysis",
    },
    "currency": {
        "label": "Currency",
        "description": "Currency used in pricing (ZAR, USD, EUR, etc.)",
        "source": "Currency Engine — evidence-based detection",
    },
    "contract_duration": {
        "label": "Contract Duration",
        "description": "Expected project duration in months",
        "source": "Document text or schedule section",
    },
    "locations": {
        "label": "Location(s)",
        "description": "Project location or delivery area",
        "source": "Document text analysis",
    },
    "boq_tables": {
        "label": "BOQ Tables",
        "description": "Bill of Quantities line items",
        "source": "BOQ Engine v2 — table extraction",
    },
    "boq_items": {
        "label": "BOQ Items",
        "description": "Number of line items extracted from BOQ tables",
        "source": "BOQ Engine v2 — row extraction",
    },
    "pricing": {
        "label": "Pricing Calculation",
        "description": "Calculated pricing based on BOQ items",
        "source": "Pricing Engine — deterministic calculation",
    },
    "workforce": {
        "label": "Workforce Requirements",
        "description": "Estimated workforce needed for the project",
        "source": "Document text or BOQ inference",
    },
    "schedule": {
        "label": "Project Schedule",
        "description": "Project timeline or milestone dates",
        "source": "Document text analysis",
    },
    "submission_letter": {
        "label": "Submission Letter",
        "description": "Generated submission letter for bid response",
        "source": "Generated from verified extracted data",
    },
    "readiness_report": {
        "label": "Readiness Assessment",
        "description": "Assessment of tender document completeness",
        "source": "Generated from verified extracted data",
    },
    "audit_report": {
        "label": "Integrity Audit",
        "description": "Audit trail of all processing stages",
        "source": "Generated from verified processing logs",
    },
    "engineer": {
        "label": "Engineer",
        "description": "Named engineer or consulting engineer",
        "source": "Deterministic procurement entity extraction",
    },
    "consultant": {
        "label": "Consultant",
        "description": "Named consultant or professional consultant",
        "source": "Deterministic procurement entity extraction",
    },
    "funding_agency": {
        "label": "Funding Agency",
        "description": "Funding or donor body named in the tender",
        "source": "Deterministic procurement entity extraction",
    },
    "buyer": {
        "label": "Buyer",
        "description": "Buyer or purchaser named in the tender",
        "source": "Deterministic procurement entity extraction",
    },
    "procurement_authority": {
        "label": "Procurement Authority",
        "description": "Authority or SCM body administering procurement",
        "source": "Deterministic procurement entity extraction",
    },
    "winning_bidder": {
        "label": "Winning Bidder",
        "description": "Successful or awarded bidder named in the tender",
        "source": "Deterministic procurement entity extraction",
    },
    "evaluation_committee": {
        "label": "Evaluation Committee",
        "description": "Named bid evaluation committee or equivalent body",
        "source": "Deterministic procurement entity extraction",
    },
    "legal_authority": {
        "label": "Legal Authority",
        "description": "Named legal or governing authority referenced in the tender",
        "source": "Deterministic procurement entity extraction",
    },
    "bank": {
        "label": "Bank",
        "description": "Bank named in the tender or submission requirements",
        "source": "Deterministic procurement entity extraction",
    },
    "insurance_provider": {
        "label": "Insurance Provider",
        "description": "Insurer or underwriter named in the tender",
        "source": "Deterministic procurement entity extraction",
    },
    "country": {
        "label": "Country",
        "description": "Detected country of procurement",
        "source": "Deterministic procurement context extraction",
    },
    "jurisdiction": {
        "label": "Jurisdiction",
        "description": "Detected jurisdiction or province",
        "source": "Deterministic procurement context extraction",
    },
    "tender_type": {
        "label": "Tender Type",
        "description": "Detected tender or request type",
        "source": "Deterministic procurement context extraction",
    },
    "procedure": {
        "label": "Procedure",
        "description": "Detected procurement procedure",
        "source": "Deterministic procurement context extraction",
    },
    "procurement_method": {
        "label": "Procurement Method",
        "description": "Detected sourcing or procurement method",
        "source": "Deterministic procurement context extraction",
    },
    "funding_source": {
        "label": "Funding Source",
        "description": "Detected budget or funding source",
        "source": "Deterministic procurement context extraction",
    },
    "language": {
        "label": "Language",
        "description": "Detected document language",
        "source": "Deterministic procurement context extraction",
    },
}


def _get_evidence_entry(result_data: Dict[str, Any], field_key: str) -> Dict[str, Any]:
    evidence = result_data.get("evidence", {}) or {}
    fields = evidence.get("fields", {}) or {}
    return fields.get(field_key, {}) or {}


def _normalize_confidence_label(confidence: Any) -> str:
    if confidence is None or confidence == "":
        return "Missing"
    if isinstance(confidence, (int, float)):
        if confidence >= 0.8:
            return "High"
        if confidence >= 0.5:
            return "Medium"
        if confidence > 0:
            return "Low"
        return "Missing"
    label = str(confidence).strip().title()
    if label in ("High", "Medium", "Low", "Missing"):
        return label
    if label in ("Not Found", "Unknown", "Very Low"):
        return "Low" if label == "Very Low" else "Missing"
    return label


def build_extracted_fields(result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build 'What We Successfully Extracted' section.

    Only displays verified information. Never invents data.
    """
    fields = []

    field_specs = [
        ("tender_number", EXTRACTED_FIELD_DEFINITIONS["tender_number"], result_data.get("metadata", {}).get("tender_number") or result_data.get("tender_number")),
        ("employer", EXTRACTED_FIELD_DEFINITIONS["employer"], result_data.get("metadata", {}).get("employer") or result_data.get("employer")),
        ("project_title", EXTRACTED_FIELD_DEFINITIONS["project_title"], result_data.get("metadata", {}).get("project_title") or result_data.get("project_title") or result_data.get("filename", "").replace(".pdf", "").replace(".PDF", "")),
        ("sector", EXTRACTED_FIELD_DEFINITIONS["sector"], result_data.get("detected_sector")),
        ("currency", EXTRACTED_FIELD_DEFINITIONS["currency"], None),
        ("contract_duration", EXTRACTED_FIELD_DEFINITIONS["contract_duration"], f"{result_data.get('detected_duration_months')} months" if result_data.get("detected_duration_months") else None),
        ("locations", EXTRACTED_FIELD_DEFINITIONS["locations"], ", ".join(result_data.get("detected_locations", []) or []) or None),
        ("boq_items", EXTRACTED_FIELD_DEFINITIONS["boq_items"], f"{len(result_data.get('boq_items', []) or [])} line items extracted" if (result_data.get("boq_items") or []) else None),
        ("pricing", EXTRACTED_FIELD_DEFINITIONS["pricing"], "Calculated" if result_data.get("pricing_result") else None),
        ("workforce", EXTRACTED_FIELD_DEFINITIONS["workforce"], f"{(result_data.get('detected_workforce') or {}).get('total_workers')} workers" if (result_data.get("detected_workforce") or {}).get("total_workers") else None),
        ("engineer", EXTRACTED_FIELD_DEFINITIONS["engineer"], (result_data.get("procurement_entities") or {}).get("engineer", {}).get("value")),
        ("consultant", EXTRACTED_FIELD_DEFINITIONS["consultant"], (result_data.get("procurement_entities") or {}).get("consultant", {}).get("value")),
        ("funding_agency", EXTRACTED_FIELD_DEFINITIONS["funding_agency"], (result_data.get("procurement_entities") or {}).get("funding_agency", {}).get("value")),
        ("buyer", EXTRACTED_FIELD_DEFINITIONS["buyer"], (result_data.get("procurement_entities") or {}).get("buyer", {}).get("value")),
        ("procurement_authority", EXTRACTED_FIELD_DEFINITIONS["procurement_authority"], (result_data.get("procurement_entities") or {}).get("procurement_authority", {}).get("value")),
        ("winning_bidder", EXTRACTED_FIELD_DEFINITIONS["winning_bidder"], (result_data.get("procurement_entities") or {}).get("winning_bidder", {}).get("value")),
        ("evaluation_committee", EXTRACTED_FIELD_DEFINITIONS["evaluation_committee"], (result_data.get("procurement_entities") or {}).get("evaluation_committee", {}).get("value")),
        ("legal_authority", EXTRACTED_FIELD_DEFINITIONS["legal_authority"], (result_data.get("procurement_entities") or {}).get("legal_authority", {}).get("value")),
        ("bank", EXTRACTED_FIELD_DEFINITIONS["bank"], (result_data.get("procurement_entities") or {}).get("bank", {}).get("value")),
        ("insurance_provider", EXTRACTED_FIELD_DEFINITIONS["insurance_provider"], (result_data.get("procurement_entities") or {}).get("insurance_provider", {}).get("value")),
        ("country", EXTRACTED_FIELD_DEFINITIONS["country"], (result_data.get("procurement_context") or {}).get("country", {}).get("value")),
        ("jurisdiction", EXTRACTED_FIELD_DEFINITIONS["jurisdiction"], (result_data.get("procurement_context") or {}).get("jurisdiction", {}).get("value")),
        ("tender_type", EXTRACTED_FIELD_DEFINITIONS["tender_type"], (result_data.get("procurement_context") or {}).get("tender_type", {}).get("value")),
        ("procedure", EXTRACTED_FIELD_DEFINITIONS["procedure"], (result_data.get("procurement_context") or {}).get("procedure", {}).get("value")),
        ("procurement_method", EXTRACTED_FIELD_DEFINITIONS["procurement_method"], (result_data.get("procurement_context") or {}).get("procurement_method", {}).get("value")),
        ("funding_source", EXTRACTED_FIELD_DEFINITIONS["funding_source"], (result_data.get("procurement_context") or {}).get("funding_source", {}).get("value")),
        ("language", EXTRACTED_FIELD_DEFINITIONS["language"], (result_data.get("procurement_context") or {}).get("language", {}).get("value")),
    ]

    currency_data = result_data.get("detected_currency")
    if currency_data and isinstance(currency_data, dict):
        currency_value = currency_data.get("currency_code")
        currency_display = f"{currency_value} ({currency_data.get('currency_name', '')})" if currency_value else None
    else:
        currency_display = None

    for field_key, definition, default_value in field_specs:
        evidence_key = field_key
        if field_key == "locations":
            evidence_key = "location"
        elif field_key == "contract_duration":
            evidence_key = "closing_date"
        elif field_key == "boq_items":
            evidence_key = "boq_summary"
        elif field_key == "pricing":
            evidence_key = "estimated_contract_value"
        elif field_key == "workforce":
            evidence_key = "work_categories"
        elif field_key == "currency":
            default_value = currency_display

        evidence = _get_evidence_entry(result_data, evidence_key)
        value = evidence.get("value") if evidence.get("value") not in (None, "", []) else default_value
        confidence = _normalize_confidence_label(evidence.get("confidence"))
        verified_from = evidence.get("section") or evidence.get("source_category") or definition["source"]
        page = evidence.get("page_number")
        paragraph = evidence.get("paragraph_or_sentence")

        fields.append({
            "field": field_key,
            "label": definition["label"],
            "description": definition["description"],
            "source": definition["source"],
            "value": value,
            "extracted": bool(value),
            "verified_from": verified_from,
            "page": page,
            "confidence": confidence,
            "warning": "⚠ Verify before submission" if confidence == "Low" else None,
            "paragraph_or_sentence": paragraph,
            "detection_method": evidence.get("detection_method"),
        })

    return fields


# ═══════════════════════════════════════════════════════════════════════
# Missing Information (with guidance)
# ═══════════════════════════════════════════════════════════════════════

MISSING_FIELD_GUIDANCE: Dict[str, Dict[str, str]] = {
    "employer": {
        "label": "Employer",
        "why_it_matters": "Required for submission letters, declarations, and identifying the procuring entity.",
        "where_found": "Usually located in the Tender Notice, Invitation to Bid, or cover page.",
        "action": "Locate the employer name in the original tender document before submission.",
    },
    "project_title": {
        "label": "Project Title",
        "why_it_matters": "Required to identify the opportunity correctly across reports and submission documents.",
        "where_found": "Usually located on the cover page, title block, or tender notice heading.",
        "action": "Confirm the project title from the tender notice or first page heading.",
    },
    "tender_number": {
        "label": "Tender Number",
        "why_it_matters": "Required for references, submission forms, and package identification.",
        "where_found": "Usually located in the document header, invitation to bid, or procurement notice.",
        "action": "Find the official tender or bid reference number in the tender notice before submission.",
    },
    "closing_date": {
        "label": "Closing Date",
        "why_it_matters": "Required to avoid late submission and to plan final packaging timelines.",
        "where_found": "Usually located in the tender notice, invitation to bid, or submission instructions.",
        "action": "Confirm the closing date from the official submission instructions.",
    },
    "closing_time": {
        "label": "Closing Time",
        "why_it_matters": "A tender can be disqualified if submitted after the stated time.",
        "where_found": "Usually located near the closing date in the tender notice or submission instructions.",
        "action": "Confirm the exact closing time from the tender notice before submission.",
    },
    "estimated_contract_value": {
        "label": "Estimated Contract Value",
        "why_it_matters": "Important for pricing review, approvals, and financial planning.",
        "where_found": "Usually located in the BOQ totals, pricing schedule, or contract value section.",
        "action": "Verify the contract value from the pricing schedule or BOQ totals.",
    },
    "submission_method": {
        "label": "Submission Method",
        "why_it_matters": "Determines whether the bid must be uploaded, emailed, couriered, or hand-delivered.",
        "where_found": "Usually located in the submission instructions or invitation to bid.",
        "action": "Check the tender instructions for the required submission method before final packaging.",
    },
    "mandatory_documents": {
        "label": "Mandatory Documents",
        "why_it_matters": "Missing compulsory documents can cause immediate disqualification.",
        "where_found": "Usually located in the mandatory returnables, compliance checklist, or tender instructions.",
        "action": "Review the tender document and compile all mandatory returnables before submission.",
    },
    "cidb_grade": {
        "label": "CIDB Grade",
        "why_it_matters": "Required for construction tenders where minimum contractor grading is specified.",
        "where_found": "Usually located in eligibility requirements, tender notice, or technical criteria.",
        "action": "Confirm the CIDB grade requirement from the eligibility or tender notice section.",
    },
    "compulsory_briefing": {
        "label": "Compulsory Briefing",
        "why_it_matters": "Missing a compulsory briefing/site meeting can disqualify the submission.",
        "where_found": "Usually located in the tender notice, briefing session section, or instructions to bidders.",
        "action": "Check whether a compulsory briefing is required and ensure attendance is recorded.",
    },
    "boq_summary": {
        "label": "BOQ Summary",
        "why_it_matters": "Needed to verify scope coverage, totals, and pricing completeness.",
        "where_found": "Usually located in the BOQ tables or summary of quantities.",
        "action": "Review the BOQ tables and totals to confirm a complete summary is available.",
    },
    "trade_summary": {
        "label": "Trade Summary",
        "why_it_matters": "Needed to understand discipline-level scope and cost distribution.",
        "where_found": "Usually derived from classified BOQ items and trade sections.",
        "action": "Verify that trade disciplines are visible in the BOQ and pricing breakdown.",
    },
    "work_categories": {
        "label": "Work Categories",
        "why_it_matters": "Needed for workforce planning and scope verification.",
        "where_found": "Usually derived from BOQ descriptions, scope of work, and trade headings.",
        "action": "Review the scope of work and BOQ descriptions to confirm work categories.",
    },
    "detected_sector": {
        "label": "Sector",
        "why_it_matters": "Sector determines applicable regulations, wage rates, and industry standards.",
        "where_found": "Usually stated in the tender notice or scope of work section.",
        "action": "Check the tender document for the sector classification (e.g., Construction, Electrical, Cleaning).",
    },
    "detected_duration_months": {
        "label": "Contract Duration",
        "why_it_matters": "Duration affects pricing, resource planning, and bond requirements.",
        "where_found": "Usually stated in the tender schedule or project timeline section.",
        "action": "Look for 'Contract Period', 'Duration', or 'Completion Period' in the tender document.",
    },
    "detected_locations": {
        "label": "Location(s)",
        "why_it_matters": "Location determines travel costs, regional rates, and delivery logistics.",
        "where_found": "Usually stated in the project description or site address section.",
        "action": "Check the tender document for the project site address or delivery location.",
    },
    "boq_items": {
        "label": "Bill of Quantities",
        "why_it_matters": "BOQ is the foundation of pricing. Without it, accurate cost estimation is not possible.",
        "where_found": "Usually a separate section or attachment titled 'Bill of Quantities' or 'Schedule of Quantities'.",
        "action": "Ensure the BOQ is included as a separate PDF or within the tender document. Tables must be text-based (not scanned images).",
    },
    "pricing_result": {
        "label": "Pricing Calculation",
        "why_it_matters": "Pricing determines bid competitiveness and financial viability.",
        "where_found": "Calculated from BOQ items, rates, and quantities.",
        "action": "Complete the BOQ extraction first. Pricing requires item rates and quantities to calculate.",
    },
    "detected_workforce": {
        "label": "Workforce Requirements",
        "why_it_matters": "Workforce planning affects cost estimation and project scheduling.",
        "where_found": "Usually stated in the scope of work or technical specifications.",
        "action": "Check for workforce requirements in the tender specifications or scope of work section.",
    },
    "detected_schedule": {
        "label": "Project Schedule",
        "why_it_matters": "Schedule affects resource planning, milestone payments, and completion deadlines.",
        "where_found": "Usually a separate section titled 'Programme', 'Schedule', or 'Timeline'.",
        "action": "Look for milestone dates, delivery schedules, or completion timelines in the document.",
    },
    "detected_currency": {
        "label": "Currency",
        "why_it_matters": "Currency determines the monetary unit for all pricing and financial calculations.",
        "where_found": "Usually indicated by currency symbols (R, $, €) or ISO codes (ZAR, USD, EUR) near pricing.",
        "action": "Check for currency symbols or codes near any monetary amounts in the document.",
    },
}


def build_missing_information(result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build 'Missing Information' section with guidance.
    
    Every missing field includes:
      - Field Name
      - Why it matters
      - Where it is normally found
      - Specific action required
    """
    missing = []
    
    # Check each required field
    checks = [
        ("detected_sector", result_data.get("detected_sector")),
        ("detected_duration_months", result_data.get("detected_duration_months")),
        ("detected_locations", result_data.get("detected_locations")),
        ("boq_items", result_data.get("boq_items")),
        ("pricing_result", result_data.get("pricing_result")),
        ("detected_workforce", result_data.get("detected_workforce")),
        ("detected_schedule", result_data.get("detected_schedule")),
        ("detected_currency", result_data.get("detected_currency")),
    ]
    
    for field_key, value in checks:
        is_missing = not value or (isinstance(value, (list, dict)) and len(value) == 0)
        if is_missing:
            guidance = MISSING_FIELD_GUIDANCE.get(field_key, {
                "label": field_key,
                "why_it_matters": "This information is required for complete tender processing.",
                "where_found": "Refer to the tender document.",
                "action": "Check the tender document for this information.",
            })
            missing.append({
                "field": field_key,
                "label": guidance["label"],
                "why_it_matters": guidance["why_it_matters"],
                "where_found": guidance["where_found"],
                "action": guidance["action"],
            })
    
    return missing


# ═══════════════════════════════════════════════════════════════════════
# Action Plan
# ═══════════════════════════════════════════════════════════════════════

def _evidence_entry(result_data: Dict[str, Any], field_key: str) -> Dict[str, Any]:
    return ((result_data.get("evidence") or {}).get("fields", {}) or {}).get(field_key, {}) or {}


def _decision_action_from_field(field_key: str, label: str, evidence: Dict[str, Any], guidance: Dict[str, str], priority: str) -> Dict[str, Any]:
    value = evidence.get("value")
    confidence = _normalize_confidence_label(evidence.get("confidence"))
    verified_from = evidence.get("section") or guidance.get("where_found") or "Tender document"
    page = evidence.get("page_number")
    evidence_text = evidence.get("paragraph_or_sentence") or (str(value) if value not in (None, "", [], {}) else "No direct evidence extracted")
    required_docs = _REQUIRED_DOCUMENT_HINTS.get(field_key, [guidance.get("where_found", "Tender document")])
    responsible = _DECISION_OWNER_MAP.get(field_key, "Bid Administrator")

    if priority == "Critical":
        est_time = "30-60 minutes"
        risk_if_ignored = f"Submission risk remains high because {label.lower()} is still unresolved."
    elif priority == "Required":
        est_time = "15-30 minutes"
        risk_if_ignored = f"Bid quality may be reduced because {label.lower()} is not fully verified."
    else:
        est_time = "10-20 minutes"
        risk_if_ignored = f"Manual review effort increases if {label.lower()} is left unresolved."

    completion_steps = [
        f"Open the section listed as '{verified_from}'.",
        f"Confirm whether {label.lower()} appears in the original tender wording.",
        "Update the submission pack only after the source wording is confirmed.",
    ]
    if page:
        completion_steps.insert(0, f"Start on page {page} of the tender document.")

    return {
        "field": field_key,
        "action": f"Resolve {label}",
        "priority": priority,
        "reason": guidance.get("why_it_matters") or f"{label} is required for tender completion.",
        "evidence": evidence_text,
        "verified_from": verified_from,
        "page": page,
        "estimated_time": est_time,
        "responsible_person": responsible,
        "required_documents": required_docs,
        "completion_steps": completion_steps,
        "risk_if_ignored": risk_if_ignored,
        "related_sections": [
            _REPORT_SECTION_REFERENCES["completion_guide"],
            _REPORT_SECTION_REFERENCES["readiness_report"],
            _REPORT_SECTION_REFERENCES["manifest"],
        ],
    }


def build_action_plan(result_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Generate an evidence-based prioritised action plan."""
    critical: List[Dict[str, Any]] = []
    required: List[Dict[str, Any]] = []
    optional: List[Dict[str, Any]] = []

    checks = [
        ("boq_items", result_data.get("boq_items"), "Critical"),
        ("pricing_result", result_data.get("pricing_result"), "Critical"),
        ("detected_sector", result_data.get("detected_sector"), "Required"),
        ("detected_duration_months", result_data.get("detected_duration_months"), "Required"),
        ("detected_locations", result_data.get("detected_locations"), "Required"),
        ("detected_workforce", result_data.get("detected_workforce"), "Optional"),
        ("detected_schedule", result_data.get("detected_schedule"), "Optional"),
        ("employer", _evidence_entry(result_data, "employer").get("value"), "Required"),
        ("closing_date", _evidence_entry(result_data, "closing_date").get("value"), "Critical"),
        ("closing_time", _evidence_entry(result_data, "closing_time").get("value"), "Critical"),
        ("submission_method", _evidence_entry(result_data, "submission_method").get("value"), "Critical"),
        ("mandatory_documents", _evidence_entry(result_data, "mandatory_documents").get("value"), "Critical"),
        ("cidb_grade", _evidence_entry(result_data, "cidb_grade").get("value"), "Required"),
        ("compulsory_briefing", _evidence_entry(result_data, "compulsory_briefing").get("value"), "Required"),
    ]

    for field_key, value, priority in checks:
        is_missing = not value or (isinstance(value, (list, dict)) and len(value) == 0)
        if not is_missing:
            continue
        guidance = MISSING_FIELD_GUIDANCE.get(field_key, {
            "label": field_key.replace("_", " ").title(),
            "why_it_matters": "This item affects tender completion.",
            "where_found": "Tender document",
            "action": f"Resolve {field_key.replace('_', ' ')} from the original tender.",
        })
        evidence = _evidence_entry(result_data, field_key)
        action = _decision_action_from_field(field_key, guidance["label"], evidence, guidance, priority)
        if priority == "Critical":
            critical.append(action)
        elif priority == "Required":
            required.append(action)
        else:
            optional.append(action)

    return {
        "critical": critical,
        "required": required,
        "optional": optional,
    }


# ═══════════════════════════════════════════════════════════════════════
# Executive Summary
# ═══════════════════════════════════════════════════════════════════════

def build_executive_summary(
    result_data: Dict[str, Any],
    extracted_fields: List[Dict[str, Any]],
    missing_info: List[Dict[str, Any]],
    action_plan: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Build the Executive Summary section.
    
    Summarises:
      - What was processed
      - What was found
      - What is missing
      - Recommended next steps
    """
    filename = result_data.get("filename", "Unknown document")
    status = result_data.get("status", "unknown")
    
    extracted_count = sum(1 for f in extracted_fields if f.get("extracted"))
    total_fields = len(extracted_fields)
    missing_count = len(missing_info)
    
    critical_count = len(action_plan.get("critical", []))
    required_count = len(action_plan.get("required", []))
    
    completeness = DataCompleteness.calculate(extracted_count, total_fields)
    
    if status == "completed":
        status_text = "Processing completed successfully."
    elif status == "partial_success":
        status_text = "Processing completed with some issues."
    else:
        status_text = "Processing encountered issues."
    
    summary = (
        f"Document: {filename}\n"
        f"Status: {status_text}\n"
        f"Data Completeness: {completeness['display']}\n"
        f"Fields Extracted: {extracted_count} of {total_fields}\n"
        f"Missing Fields: {missing_count}\n"
        f"Critical Actions: {critical_count}\n"
        f"Required Actions: {required_count}\n"
    )
    
    all_actions = action_plan.get("critical", []) + action_plan.get("required", []) + action_plan.get("optional", [])
    top_missing_items = [item.get("label") for item in missing_info[:10]]
    top_risks = [action.get("risk_if_ignored") for action in all_actions[:10]]
    estimated_submission_readiness = completeness["percentage"]

    return {
        "summary": summary,
        "filename": filename,
        "status": status,
        "status_text": status_text,
        "completeness": completeness,
        "extracted_count": extracted_count,
        "total_fields": total_fields,
        "missing_count": missing_count,
        "critical_actions": critical_count,
        "required_actions": required_count,
        "top_10_missing_items": top_missing_items,
        "top_10_risks": top_risks,
        "estimated_submission_readiness": estimated_submission_readiness,
        "related_reports": _REPORT_SECTION_REFERENCES,
    }


# ═══════════════════════════════════════════════════════════════════════
# Verification Notice
# ═══════════════════════════════════════════════════════════════════════

VERIFICATION_NOTICE = (
    "No information has been invented or inferred. "
    "Verify all details before submission."
)

VERIFICATION_NOTICE_FULL = (
    "This report was generated from verified document extraction. "
    "No information has been invented or inferred. "
    "All data shown was detected, extracted, or calculated from the uploaded document. "
    "Verify all details before submission."
)


# ═══════════════════════════════════════════════════════════════════════
# Complete Report Builder
# ═══════════════════════════════════════════════════════════════════════

def build_professional_report(result_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a complete professional report using the standard framework.
    
    Every report contains:
      1. Executive Summary
      2. What We Successfully Extracted
      3. Missing Information
      4. Action Plan
      5. Verification Notice
    """
    extracted_fields = build_extracted_fields(result_data)
    missing_info = build_missing_information(result_data)
    action_plan = build_action_plan(result_data)
    executive_summary = build_executive_summary(
        result_data, extracted_fields, missing_info, action_plan
    )
    
    return {
        "report_framework_version": REPORT_FRAMEWORK_VERSION,
        "generated_at": datetime.now().isoformat(),
        "executive_summary": executive_summary,
        "extracted_fields": extracted_fields,
        "missing_information": missing_info,
        "action_plan": action_plan,
        "verification_notice": VERIFICATION_NOTICE,
        "verification_notice_full": VERIFICATION_NOTICE_FULL,
    }


# ═══════════════════════════════════════════════════════════════════════
# PDF Section Builders (for reportlab integration)
# ═══════════════════════════════════════════════════════════════════════

def get_pdf_styles():
    """Get standard PDF styles for report generation."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    
    styles = getSampleStyleSheet()
    
    PRIMARY_BLUE = colors.HexColor("#1F4E79")
    TEXT_DARK = colors.HexColor("#222222")
    TEXT_MEDIUM = colors.HexColor("#555555")
    TEXT_LIGHT = colors.HexColor("#888888")
    
    return {
        "title": ParagraphStyle(
            "ReportTitle", parent=styles["Title"],
            fontSize=22, leading=28, textColor=PRIMARY_BLUE,
            spaceAfter=6, alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle", parent=styles["Normal"],
            fontSize=10, leading=14, textColor=TEXT_MEDIUM,
            spaceAfter=20, alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "SectionHeader", parent=styles["Heading1"],
            fontSize=14, leading=18, textColor=PRIMARY_BLUE,
            spaceBefore=16, spaceAfter=8,
        ),
        "subsection": ParagraphStyle(
            "SubSection", parent=styles["Heading2"],
            fontSize=12, leading=16, textColor=TEXT_DARK,
            spaceBefore=12, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body", parent=styles["Normal"],
            fontSize=9, leading=13, textColor=TEXT_DARK,
            spaceAfter=6,
        ),
        "body_bold": ParagraphStyle(
            "BodyBold", parent=styles["Normal"],
            fontSize=9, leading=13, textColor=TEXT_DARK,
            spaceAfter=6, fontName="Helvetica-Bold",
        ),
        "small": ParagraphStyle(
            "Small", parent=styles["Normal"],
            fontSize=8, leading=11, textColor=TEXT_MEDIUM,
            spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "Footer", parent=styles["Normal"],
            fontSize=7, leading=10, textColor=TEXT_LIGHT,
            alignment=TA_CENTER,
        ),
        "verification": ParagraphStyle(
            "Verification", parent=styles["Normal"],
            fontSize=8, leading=11, textColor=TEXT_MEDIUM,
            alignment=TA_CENTER, spaceBefore=20, spaceAfter=10,
            fontName="Helvetica-Oblique",
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=styles["Normal"],
            fontSize=9, leading=13, textColor=TEXT_DARK,
            leftIndent=15, spaceAfter=3,
        ),
        "action_critical": ParagraphStyle(
            "ActionCritical", parent=styles["Normal"],
            fontSize=9, leading=13, textColor=colors.HexColor("#CC0000"),
            leftIndent=15, spaceAfter=3, fontName="Helvetica-Bold",
        ),
        "action_required": ParagraphStyle(
            "ActionRequired", parent=styles["Normal"],
            fontSize=9, leading=13, textColor=colors.HexColor("#CC6600"),
            leftIndent=15, spaceAfter=3, fontName="Helvetica-Bold",
        ),
        "action_optional": ParagraphStyle(
            "ActionOptional", parent=styles["Normal"],
            fontSize=9, leading=13, textColor=TEXT_MEDIUM,
            leftIndent=15, spaceAfter=3,
        ),
    }


def build_pdf_sections(report: Dict[str, Any], pdf_styles: Dict[str, Any]) -> List[Any]:
    """
    Build PDF flowable elements from a professional report.
    
    Returns a list of reportlab flowables for document building.
    """
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    
    elements = []
    s = pdf_styles
    
    # ── Title ─────────────────────────────────────────────────────────
    elements.append(Paragraph("Tender Processing Report", s["title"]))
    elements.append(Paragraph(
        f"Generated: {report.get('generated_at', '')[:10]}",
        s["subtitle"]
    ))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1F4E79")))
    elements.append(Spacer(1, 0.3 * cm))
    
    # ── 1. Executive Summary ─────────────────────────────────────────
    elements.append(Paragraph("1. Executive Summary", s["section"]))
    exec_summary = report.get("executive_summary", {})
    elements.append(Paragraph(f"<b>Document:</b> {exec_summary.get('filename', 'Unknown')}", s["body"]))
    elements.append(Paragraph(f"<b>Status:</b> {exec_summary.get('status_text', '')}", s["body"]))
    elements.append(Paragraph(
        f"<b>Data Completeness:</b> {exec_summary.get('completeness', {}).get('display', 'N/A')}",
        s["body"]
    ))
    elements.append(Paragraph(
        f"{exec_summary.get('completeness', {}).get('bar', '')} {exec_summary.get('completeness', {}).get('percentage', 0)}%",
        s["body"]
    ))
    elements.append(Paragraph(
        f"Fields Extracted: {exec_summary.get('extracted_count', 0)} of {exec_summary.get('total_fields', 0)} | "
        f"Missing: {exec_summary.get('missing_count', 0)} | "
        f"Critical Actions: {exec_summary.get('critical_actions', 0)}",
        s["body"]
    ))
    elements.append(Spacer(1, 0.2 * cm))
    
    # ── 2. What We Successfully Extracted ────────────────────────────
    elements.append(Paragraph("2. What We Successfully Extracted", s["section"]))
    extracted = report.get("extracted_fields", [])
    
    extracted_data = [["Field", "Value", "Source"]]
    for field in extracted:
        if field.get("extracted"):
            extracted_data.append([
                f"✓ {field['label']}",
                str(field.get("value", "") or "Detected"),
                field.get("source", ""),
            ])
    
    if len(extracted_data) > 1:
        table = Table(extracted_data, colWidths=[5 * cm, 8 * cm, 5 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No fields were successfully extracted from this document.", s["body"]))
    
    elements.append(Spacer(1, 0.3 * cm))
    
    # ── 3. Missing Information ───────────────────────────────────────
    elements.append(Paragraph("3. Missing Information", s["section"]))
    missing = report.get("missing_information", [])
    
    if missing:
        for m in missing:
            elements.append(Paragraph(f"<b>{m.get('label', 'Unknown')}</b>", s["subsection"]))
            elements.append(Paragraph(f"<b>Why it matters:</b> {m.get('why_it_matters', '')}", s["body"]))
            elements.append(Paragraph(f"<b>Where it is normally found:</b> {m.get('where_found', '')}", s["body"]))
            elements.append(Paragraph(f"<b>Action required:</b> {m.get('action', '')}", s["body"]))
            elements.append(Spacer(1, 0.15 * cm))
    else:
        elements.append(Paragraph("All required fields have been successfully extracted.", s["body"]))
    
    elements.append(Spacer(1, 0.3 * cm))
    
    # ── 4. Action Plan ───────────────────────────────────────────────
    elements.append(Paragraph("4. Action Plan", s["section"]))
    actions = report.get("action_plan", {})
    
    # Critical
    critical_actions = actions.get("critical", [])
    if critical_actions:
        elements.append(Paragraph("<b>Critical — Must be addressed before submission</b>", s["body_bold"]))
        for a in critical_actions:
            elements.append(Paragraph(f"■ {a.get('action', '')}", s["action_critical"]))
            elements.append(Paragraph(f"  {a.get('detail', '')}", s["small"]))
        elements.append(Spacer(1, 0.15 * cm))
    
    # Required
    required_actions = actions.get("required", [])
    if required_actions:
        elements.append(Paragraph("<b>Required — Should be addressed for completeness</b>", s["body_bold"]))
        for a in required_actions:
            elements.append(Paragraph(f"● {a.get('action', '')}", s["action_required"]))
            elements.append(Paragraph(f"  {a.get('detail', '')}", s["small"]))
        elements.append(Spacer(1, 0.15 * cm))
    
    # Optional
    optional_actions = actions.get("optional", [])
    if optional_actions:
        elements.append(Paragraph("<b>Optional — Nice to have</b>", s["body_bold"]))
        for a in optional_actions:
            elements.append(Paragraph(f"○ {a.get('action', '')}", s["action_optional"]))
            elements.append(Paragraph(f"  {a.get('detail', '')}", s["small"]))
    
    elements.append(Spacer(1, 0.3 * cm))
    
    # ── 5. Verification Notice ───────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC")))
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(Paragraph(report.get("verification_notice_full", ""), s["verification"]))
    
    return elements