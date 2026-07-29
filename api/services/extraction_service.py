"""
Extraction Service — Deterministic field extraction from tenders.

This platform is deterministic. It does NOT generate fictional information.
It does NOT guess. It does NOT hallucinate.

Every value originates from verified extracted document data or falls back
to deterministic business rules.

States:
  - "verified"   = Confidently extracted from structured metadata or strong regex match
  - "review"     = Low-confidence match found (candidate displayed for manual review)
  - "blank"      = No evidence found, field left empty
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple


_FIELD_LABEL_EXCLUSIONS = {
    "supplier information",
    "name of bidder",
    "bidder name",
    "name of supplier",
    "supplier name",
    "company name",
    "contact person",
    "postal address",
    "physical address",
    "banking details",
    "bank name",
    "account number",
    "branch code",
    "signature",
    "date",
    "telephone",
    "fax",
    "email",
}

_GENERIC_UPPERCASE_EXCLUSIONS = {
    "supplier information",
    "standard bidding document",
    "returnable documents",
    "submission requirements",
    "evaluation criteria",
    "award criteria",
    "pricing schedule",
    "bill of quantities",
    "schedule of quantities",
}

logger = logging.getLogger(__name__)

# ── Tender Reference patterns (priority-ordered) ────────────────────
TENDER_REF_PATTERNS = [
    # Explicit "Tender No/Ref/Number:" patterns (most specific)
    r"(?:Tender\s+(?:No|Number|Ref|Reference)\s*[:\-–]?\s*)([A-Z0-9][A-Z0-9/\-–\s]{4,30})",
    r"(?:Reference\s+(?:No|Number)\s*[:\-–]?\s*)([A-Z0-9][A-Z0-9/\-–\s]{4,30})",
    r"(?:Bid\s+(?:No|Number|Ref)\s*[:\-–]?\s*)([A-Z0-9][A-Z0-9/\-–\s]{4,30})",
    r"(?:RFQ\s*(?:No|Number|Ref)?\s*[:\-–]?\s*)([A-Z0-9][A-Z0-9/\-–\s]{4,20})",
    # SA tender authority codes (secondary, requires review)
    r"\b((?:ZNT|SCM|RFQ|TEN|BID|CONTRACT)\s*[/\-–]\s*\d[\d/\-–]{3,20})\b",
    r"\b((?:REQ|REQUISITION)\s*[/\-–]?\s*\d[\d/\-–]{3,15})\b",
    # Generic reference-number pattern (lowest confidence)
    r"\b([A-Z]{2,6}\s*[/\-–]?\s*\d{4,10}[/\-–]?\d{0,5})\b",
]

# ── Secondary fallback: common tender prefixes followed by alphanumeric ──
SECONDARY_REF_PATTERNS = [
    # "RFQ-12345", "RFQ12345", "Tender-2024-001", etc.
    r"\b((?:RFQ|Tender|Bid|REQ|RFP|RFT|EOI|ITT|ITB)\s*[-–]?\s*\d[\dA-Za-z/\-–]{3,20})\b",
    # "TEN/2024/001", "SCM/2024/01" style
    r"\b((?:TEN|SCM|ZNT|BID|CONTRACT)\s*[/\-–]\s*\d{2,4}\s*[/\-–]\s*\d[\dA-Za-z/\-–]{2,15})\b",
    # "REF-2024-00123" style
    r"\b(REF\s*[-–]?\s*\d{2,4}\s*[-–]?\s*\d[\dA-Za-z/\-–]{2,15})\b",
    # Any alphanumeric code that looks like a reference (e.g., "PRJ-2024-001")
    r"\b([A-Z]{2,6}\s*[-–]\s*\d{2,4}\s*[-–]\s*\d[\dA-Za-z/\-–]{2,15})\b",
]

# ── Document header patterns (for candidate extraction) ─────────────
DOCUMENT_HEADER_PATTERNS = [
    # First few lines often contain reference numbers
    r"^(?:RE|RE:|Reference|Ref)[:\s]*([A-Z0-9][A-Z0-9/\-–\s]{4,30})",
    # Look for alphanumeric codes at top of document
    r"^([A-Z]{2,8}\s*/\s*\d{3,10})",
    # Common header patterns: RFQ/Tender/Bid number at line start
    r"^(?:RFQ|Tender|Bid|REQ|RFP)\s*(?:No|Number|Ref)?[:\s]*([A-Z0-9][A-Z0-9/\-–\s]{4,30})",
]

# ── Employer / Procuring Entity patterns ───────────────────────────
EMPLOYER_PATTERNS = [
    r"(?:Procuring\s+Entity|Employer|Client|Department)\s*[:\-–]\s*([A-Za-z0-9\s&'.,\-()/]+?)(?:\n|\.\s|\r)",
    r"(?:Issued\s+by|Prepared\s+by|On\s+behalf\s+of)\s*[:\-–]\s*([A-Za-z0-9\s&'.,\-()/]+?)(?:\n|\.\s|\r)",
    r"(?:Tender\s+issued\s+by|Tender\s+invited\s+by)\s*[:\-–]\s*([A-Za-z0-9\s&'.,\-()/]+?)(?:\n|\.\s|\r)",
    # Document header / letterhead
    r"(?:^|\n)([A-Z][A-Za-z\s&.]{5,60})\n(?:Private Bag|P\.?\s*O\.?\s*Box|Postal)",
]

# ── Project Name patterns ──────────────────────────────────────────
PROJECT_NAME_PATTERNS = [
    r"(?:Project\s+(?:Name|Title|Description)\s*[:\-–]?\s*)([A-Za-z0-9\s&'.,\-()/]{10,120})(?:\n|\.\s|\r)",
    r"(?:Tender\s+(?:Name|Title|Description)\s*[:\-–]?\s*)([A-Za-z0-9\s&'.,\-()/]{10,120})(?:\n|\.\s|\r)",
    r"(?:Description\s+of\s+(?:Tender|Works|Services|Goods)\s*[:\-–]?\s*)([A-Za-z0-9\s&'.,\-()/]{10,120})(?:\n|\.\s|\r)",
]

PROCUREMENT_ENTITY_PATTERNS: Dict[str, List[str]] = {
    "engineer": [
        r"(?:Engineer|Project Engineer|Consulting Engineer)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,100})",
    ],
    "consultant": [
        r"(?:Consultant|Professional Consultant|Lead Consultant)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,100})",
    ],
    "funding_agency": [
        r"(?:Funding Agency|Funded by|Financed by|Donor)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,120})",
    ],
    "winning_bidder": [
        r"(?:Winning Bidder|Successful Bidder|Awarded to)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,120})",
    ],
    "buyer": [
        r"(?:Buyer|Purchaser|Purchasing Officer)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,100})",
    ],
    "procurement_authority": [
        r"(?:Procurement Authority|Tender Board|Supply Chain Management|SCM Unit)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,120})",
    ],
    "evaluation_committee": [
        r"(?:Evaluation Committee|Bid Evaluation Committee|BEC)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,120})",
    ],
    "legal_authority": [
        r"(?:Legal Authority|In terms of|Governed by)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,120})",
    ],
    "bank": [
        r"(?:Bank|Banking Details|Bank Name)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,100})",
    ],
    "insurance_provider": [
        r"(?:Insurance Provider|Insurer|Underwriter)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,100})",
    ],
}

PROCUREMENT_CONTEXT_PATTERNS: Dict[str, List[str]] = {
    "country": [
        r"\b(South Africa|Namibia|Botswana|Zimbabwe|Mozambique|Zambia|Kenya|Uganda|Tanzania|Rwanda|Nigeria|Ghana|United Kingdom|UK|United States|USA)\b",
    ],
    "jurisdiction": [
        r"(?:Jurisdiction|Province|Region)\s*[:\-–]?\s*([A-Za-z][A-Za-z\s\-]{2,80})",
        r"\b(Western Cape|Eastern Cape|Northern Cape|KwaZulu-Natal|Gauteng|Mpumalanga|Limpopo|Free State|North West)\b",
    ],
    "tender_type": [
        r"(?:Tender Type|Type of Tender|Request Type)\s*[:\-–]?\s*([A-Za-z][A-Za-z\s\-/]{2,80})",
        r"\b(Request for Quotation|RFQ|Request for Proposal|RFP|Invitation to Bid|ITB|Tender Notice|Bid Invitation)\b",
    ],
    "procedure": [
        r"(?:Procedure|Evaluation Procedure|Selection Procedure)\s*[:\-–]?\s*([A-Za-z][A-Za-z\s\-/]{2,80})",
        r"\b(Open Tender|Restricted Tender|Two-Stage|Single-Stage|80/20|90/10)\b",
    ],
    "procurement_method": [
        r"(?:Procurement Method|Acquisition Method|Sourcing Method)\s*[:\-–]?\s*([A-Za-z][A-Za-z\s\-/]{2,80})",
        r"\b(quotation|request for quotation|open bid|competitive bidding|limited bidding|framework agreement)\b",
    ],
    "funding_source": [
        r"(?:Funding Source|Source of Funds|Budget Source)\s*[:\-–]?\s*([A-Za-z][A-Za-z0-9\s&'.,\-()/]{3,120})",
    ],
    "language": [
        r"(?:Language|Document Language)\s*[:\-–]?\s*([A-Za-z][A-Za-z\s]{2,40})",
    ],
}

DOCUMENT_SECTION_PATTERNS: Dict[str, List[str]] = {
    "instructions": [r"^\s*(Instructions to Bidders|Instructions|Bid Instructions)\s*$"],
    "eligibility": [r"^\s*(Eligibility|Eligibility Criteria|Minimum Eligibility Requirements)\s*$"],
    "pricing": [r"^\s*(Pricing|Pricing Schedule|Price Schedule|Financial Proposal)\s*$"],
    "boq": [r"^\s*(Bill of Quantities|BOQ|Schedule of Quantities)\s*$"],
    "specifications": [r"^\s*(Specifications|Technical Specifications|Scope of Work|Terms of Reference)\s*$"],
    "forms": [r"^\s*(Forms|Returnable Documents|Standard Bidding Documents|SBD\s*\d.*)\s*$"],
    "drawings": [r"^\s*(Drawings|Plans|Construction Drawings)\s*$"],
    "schedules": [r"^\s*(Schedules|Programme|Timeline|Project Schedule)\s*$"],
    "appendices": [r"^\s*(Appendices|Annexures|Annexes)\s*$"],
    "evaluation_criteria": [r"^\s*(Evaluation Criteria|Technical Evaluation Criteria|Functionality Criteria)\s*$"],
    "award_criteria": [r"^\s*(Award Criteria|Selection Criteria|Preference Point System)\s*$"],
    "submission_requirements": [r"^\s*(Submission Requirements|Proposal Requirements|Submission Instructions|Returnable Documents)\s*$"],
}


def _find_in_text(pattern: str, text: Optional[str], flags: int = re.IGNORECASE | re.MULTILINE) -> Optional[str]:
    """Search for a regex pattern in text, return first match or None."""
    if not text:
        return None
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def _find_all_in_text(pattern: str, text: Optional[str], flags: int = re.IGNORECASE | re.MULTILINE) -> List[str]:
    """Search for ALL matches of a regex pattern in text, return deduplicated list."""
    if not text:
        return []
    matches = re.findall(pattern, text, flags)
    seen = set()
    unique: List[str] = []
    for m in matches:
        cleaned = m.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return unique


def _clean_ref(value: str) -> str:
    """Clean up whitespace in a reference string."""
    return re.sub(r'\s+', ' ', value).strip()


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _clean_extracted_value(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    cleaned = re.sub(r"^[\-:–]+\s*", "", cleaned)
    cleaned = re.sub(r"\s*[\-:–]+$", "", cleaned)
    return cleaned.strip(" ,.;")


def _looks_like_field_label(value: str) -> bool:
    normalized = _clean_extracted_value(value).lower()
    if not normalized:
        return True
    if normalized in _FIELD_LABEL_EXCLUSIONS:
        return True
    if len(normalized) <= 2:
        return True
    if re.fullmatch(r"[A-Z\s]{3,}", value or "") and normalized in _GENERIC_UPPERCASE_EXCLUSIONS:
        return True
    return False


def _is_reasonable_entity_value(value: str) -> bool:
    cleaned = _clean_extracted_value(value)
    if not cleaned or _looks_like_field_label(cleaned):
        return False
    if len(cleaned) > 140:
        return False
    if re.search(r"\b(signature|telephone|tel|fax|email|cell|account number|branch code)\b", cleaned, re.IGNORECASE):
        return False
    return True


def _find_line_candidates(full_text: Optional[str], labels: List[str]) -> List[Dict[str, Any]]:
    if not full_text:
        return []
    candidates: List[Dict[str, Any]] = []
    lines = full_text.splitlines()
    current_page = 1
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        page_match = re.search(r"Page\s+(\d+)\s+of\s+\d+", line, re.IGNORECASE)
        if page_match:
            try:
                current_page = int(page_match.group(1))
            except ValueError:
                pass
        for label in labels:
            pattern = rf"^\s*{label}\s*[:\-–]?\s*(.+)$"
            match = re.match(pattern, line, re.IGNORECASE)
            if not match:
                continue
            value = _clean_extracted_value(match.group(1))
            if not value and idx + 1 < len(lines):
                value = _clean_extracted_value(lines[idx + 1].strip())
            if not _is_reasonable_entity_value(value):
                continue
            candidates.append({
                "value": value,
                "page": current_page,
                "line": line,
                "line_index": idx,
            })
    return candidates


def _extract_header_organization(full_text: Optional[str]) -> Optional[str]:
    if not full_text:
        return None
    current_page = 1
    for raw_line in full_text.splitlines()[:60]:
        line = raw_line.strip()
        if not line:
            continue
        page_match = re.search(r"Page\s+(\d+)\s+of\s+\d+", line, re.IGNORECASE)
        if page_match:
            try:
                current_page = int(page_match.group(1))
            except ValueError:
                pass
            continue
        normalized = line.lower()
        if normalized in _GENERIC_UPPERCASE_EXCLUSIONS or normalized in _FIELD_LABEL_EXCLUSIONS:
            continue
        if re.search(r"\b(private bag|p\.?\s*o\.?\s*box|postal|department of|municipality|municipal|ministry|authority|board|university|college|hospital)\b", line, re.IGNORECASE):
            return _clean_extracted_value(line)
    return None


def extract_tender_reference(
    metadata: Dict[str, Any],
    full_text: Optional[str],
    document_heading: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract tender reference with confidence states.

    Returns:
        Dict with:
          - value: The extracted reference or empty string
          - state: "verified" | "review" | "blank"
          - candidates: List of candidate strings (for "review" state)
          - source: Where the value came from
    """
    # ── Priority 1: Structured metadata (highest confidence) ───────────
    for field in ["tender_number", "tender_reference", "reference_number", "tender_reference_number"]:
        val = metadata.get(field)
        if val:
            return {
                "value": _clean_ref(str(val)),
                "state": "verified",
                "candidates": [],
                "source": f"metadata.{field}",
            }

    # ── Priority 2: Explicit patterns in full text (high confidence) ───
    if full_text:
        # Try the most specific patterns first
        for pattern in TENDER_REF_PATTERNS[:3]:  # First 3 are explicit
            result = _find_in_text(pattern, full_text)
            if result:
                cleaned = _clean_ref(result)
                if len(cleaned) >= 4:
                    return {
                        "value": cleaned,
                        "state": "verified",
                        "candidates": [],
                        "source": "regex_explicit",
                    }

    # ── Priority 3: Document heading (medium confidence) ───────────────
    if document_heading:
        for pattern in DOCUMENT_HEADER_PATTERNS:
            result = _find_in_text(pattern, document_heading)
            if result:
                cleaned = _clean_ref(result)
                return {
                    "value": cleaned,
                    "state": "verified",
                    "source": "document_heading",
                    "candidates": [],
                }

    # ── Priority 4: Secondary patterns in full text (lower confidence) ──
    if full_text:
        candidates: List[str] = []
        for pattern in TENDER_REF_PATTERNS[3:]:  # Authority codes + generic
            matches = _find_all_in_text(pattern, full_text)
            for m in matches:
                cleaned = _clean_ref(m)
                if cleaned and len(cleaned) >= 4:
                    candidates.append(cleaned)

        # Also check first 500 chars (document header area) for ref-style patterns
        header_text = full_text[:500]
        header_candidates = _find_all_in_text(r"([A-Z0-9]{4,15}\s*[/\-–]\s*\d{3,10})", header_text)
        for c in header_candidates:
            cleaned = _clean_ref(c)
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)

        if candidates:
            # Deduplicate
            unique_candidates = list(dict.fromkeys(candidates))
            return {
                "value": unique_candidates[0],
                "state": "review",
                "candidates": unique_candidates[:5],  # Top 5 candidates
                "source": "regex_secondary",
            }

    # ── Priority 5: Secondary fallback — common tender prefixes ────────
    if full_text:
        fallback_candidates: List[str] = []
        for pattern in SECONDARY_REF_PATTERNS:
            matches = _find_all_in_text(pattern, full_text)
            for m in matches:
                cleaned = _clean_ref(m)
                if cleaned and len(cleaned) >= 4 and cleaned not in fallback_candidates:
                    fallback_candidates.append(cleaned)

        if fallback_candidates:
            return {
                "value": fallback_candidates[0],
                "state": "review",
                "candidates": fallback_candidates[:5],
                "source": "regex_fallback",
            }

    # ── Priority 6: Document header candidate extraction (lowest confidence) ──
    if document_heading:
        header_candidates = _find_all_in_text(
            r"([A-Z0-9]{3,15}\s*[/\-–]\s*\d[\dA-Za-z/\-–]{2,15})",
            document_heading,
        )
        if header_candidates:
            return {
                "value": header_candidates[0],
                "state": "review",
                "candidates": header_candidates[:5],
                "source": "header_candidate",
            }

    # ── No evidence found ──────────────────────────────────────────────
    return {
        "value": "",
        "state": "blank",
        "candidates": [],
        "source": "insufficient_evidence",
    }


def extract_project_name(
    metadata: Dict[str, Any],
    full_text: Optional[str],
) -> Dict[str, Any]:
    """Extract project name with confidence states."""
    # ── Priority 1: Structured metadata ────────────────────────────────
    for field in ["project_name", "project_title", "tender_name"]:
        val = metadata.get(field)
        if val:
            return {"value": str(val), "state": "verified", "candidates": [], "source": f"metadata.{field}"}

    # ── Priority 2: Full text patterns ─────────────────────────────────
    if full_text:
        for pattern in PROJECT_NAME_PATTERNS:
            result = _find_in_text(pattern, full_text)
            if result and len(result) > 10:
                return {"value": result, "state": "verified", "candidates": [], "source": "regex_explicit"}

    return {"value": "", "state": "blank", "candidates": [], "source": "insufficient_evidence"}


def extract_employer(
    metadata: Dict[str, Any],
    full_text: Optional[str],
) -> Dict[str, Any]:
    """Extract employer / procuring entity with confidence states."""
    for field in ["employer", "procuring_entity", "client_name", "department"]:
        val = metadata.get(field)
        if val:
            return {"value": str(val), "state": "verified", "candidates": [], "source": f"metadata.{field}"}

    line_candidates = _find_line_candidates(full_text, [
        r"Employer",
        r"Procuring\s+Entity",
        r"Client",
        r"Department",
        r"Issued\s+by",
        r"Tender\s+issued\s+by",
        r"Tender\s+invited\s+by",
    ])
    if line_candidates:
        return {
            "value": line_candidates[0]["value"],
            "state": "verified",
            "candidates": [],
            "source": "line_label_match",
        }

    if full_text:
        for pattern in EMPLOYER_PATTERNS:
            result = _find_in_text(pattern, full_text)
            if result and _is_reasonable_entity_value(result):
                return {"value": _clean_extracted_value(result), "state": "verified", "candidates": [], "source": "regex_explicit"}

    header_org = _extract_header_organization(full_text)
    if header_org:
        return {"value": header_org, "state": "review", "candidates": [], "source": "header_letterhead"}

    return {"value": "", "state": "blank", "candidates": [], "source": "insufficient_evidence"}


def extract_company_name(
    metadata: Dict[str, Any],
    full_text: Optional[str],
) -> Dict[str, Any]:
    """Extract company/bidder name with confidence states."""
    # ── Priority 1: Structured metadata ────────────────────────────────
    for field in ["company_name", "organisation", "organization", "bidder_name"]:
        val = metadata.get(field)
        if val:
            return {"value": str(val), "state": "verified", "candidates": [], "source": f"metadata.{field}"}

    # ── Priority 2: Full text patterns ─────────────────────────────────
    if full_text:
        pattern = r"(?:Bidder|Contractor|Service\s+Provider|Supplier)\s*(?:Name)?\s*[:\-–]?\s*([A-Za-z0-9\s&'.,\-()/]{3,80})(?:\n|\.\s|\r)"
        result = _find_in_text(pattern, full_text)
        if result and len(result) > 3:
            return {"value": result, "state": "verified", "candidates": [], "source": "regex_explicit"}

    return {"value": "", "state": "blank", "candidates": [], "source": "insufficient_evidence"}


def _extract_generic_field(full_text: Optional[str], patterns: List[str], labels: Optional[List[str]] = None) -> Dict[str, Any]:
    if labels:
        line_candidates = _find_line_candidates(full_text, labels)
        if line_candidates:
            return {"value": line_candidates[0]["value"], "state": "verified", "candidates": [], "source": "line_label_match"}
    if full_text:
        for pattern in patterns:
            result = _find_in_text(pattern, full_text)
            if result:
                cleaned = _clean_extracted_value(result)
                if _is_reasonable_entity_value(cleaned):
                    return {"value": cleaned, "state": "verified", "candidates": [], "source": "regex_explicit"}
    return {"value": "", "state": "blank", "candidates": [], "source": "insufficient_evidence"}


def extract_procurement_entities(metadata: Dict[str, Any], full_text: Optional[str]) -> Dict[str, Dict[str, Any]]:
    entities: Dict[str, Dict[str, Any]] = {
        "employer": extract_employer(metadata, full_text),
    }
    metadata_field_map = {
        "engineer": ["engineer", "project_engineer"],
        "consultant": ["consultant", "lead_consultant"],
        "funding_agency": ["funding_agency", "funded_by"],
        "winning_bidder": ["winning_bidder", "awarded_to"],
        "buyer": ["buyer", "purchaser"],
        "procurement_authority": ["procurement_authority", "tender_board"],
        "evaluation_committee": ["evaluation_committee", "bid_evaluation_committee"],
        "legal_authority": ["legal_authority"],
        "bank": ["bank", "bank_name"],
        "insurance_provider": ["insurance_provider", "insurer"],
    }
    label_map = {
        "engineer": [r"Engineer", r"Project\s+Engineer", r"Consulting\s+Engineer"],
        "consultant": [r"Consultant", r"Professional\s+Consultant", r"Lead\s+Consultant"],
        "funding_agency": [r"Funding\s+Agency", r"Funded\s+by", r"Financed\s+by", r"Donor"],
        "winning_bidder": [r"Winning\s+Bidder", r"Successful\s+Bidder", r"Awarded\s+to"],
        "buyer": [r"Buyer", r"Purchaser", r"Purchasing\s+Officer"],
        "procurement_authority": [r"Procurement\s+Authority", r"Tender\s+Board", r"SCM\s+Unit"],
        "evaluation_committee": [r"Evaluation\s+Committee", r"Bid\s+Evaluation\s+Committee", r"BEC"],
        "legal_authority": [r"Legal\s+Authority", r"Governed\s+by"],
        "bank": [r"Bank", r"Bank\s+Name"],
        "insurance_provider": [r"Insurance\s+Provider", r"Insurer", r"Underwriter"],
    }
    for field_name, patterns in PROCUREMENT_ENTITY_PATTERNS.items():
        value = None
        source_field = None
        for metadata_field in metadata_field_map.get(field_name, []):
            if metadata.get(metadata_field):
                value = str(metadata[metadata_field])
                source_field = metadata_field
                break
        if value:
            entities[field_name] = {"value": value, "state": "verified", "candidates": [], "source": f"metadata.{source_field}"}
        else:
            entities[field_name] = _extract_generic_field(full_text, patterns, labels=label_map.get(field_name))
    return entities


def extract_procurement_context(metadata: Dict[str, Any], full_text: Optional[str], detected_sector: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    context: Dict[str, Dict[str, Any]] = {}
    metadata_field_map = {
        "country": ["country"],
        "jurisdiction": ["jurisdiction", "province"],
        "tender_type": ["tender_type"],
        "procedure": ["procedure"],
        "procurement_method": ["procurement_method"],
        "funding_source": ["funding_source"],
        "language": ["language"],
    }
    context_label_map = {
        "country": [r"Country"],
        "jurisdiction": [r"Jurisdiction", r"Province", r"Region"],
        "tender_type": [r"Tender\s+Type", r"Type\s+of\s+Tender", r"Request\s+Type"],
        "procedure": [r"Procedure", r"Evaluation\s+Procedure", r"Selection\s+Procedure"],
        "procurement_method": [r"Procurement\s+Method", r"Acquisition\s+Method", r"Sourcing\s+Method"],
        "funding_source": [r"Funding\s+Source", r"Source\s+of\s+Funds", r"Budget\s+Source"],
        "language": [r"Language", r"Document\s+Language"],
    }
    for field_name, patterns in PROCUREMENT_CONTEXT_PATTERNS.items():
        value = None
        source_field = None
        for metadata_field in metadata_field_map.get(field_name, []):
            if metadata.get(metadata_field):
                value = str(metadata[metadata_field])
                source_field = metadata_field
                break
        if value:
            context[field_name] = {"value": value, "state": "verified", "candidates": [], "source": f"metadata.{source_field}"}
        else:
            context[field_name] = _extract_generic_field(full_text, patterns, labels=context_label_map.get(field_name))
    context["sector"] = {"value": detected_sector or "", "state": "verified" if detected_sector else "blank", "candidates": [], "source": "detected_sector" if detected_sector else "insufficient_evidence"}
    return context


def detect_document_sections(full_text: Optional[str]) -> List[Dict[str, Any]]:
    if not full_text:
        return []
    sections: List[Dict[str, Any]] = []
    lines = full_text.splitlines()
    current_page = 1
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        page_match = re.search(r"Page\s+(\d+)\s+of\s+\d+", line, re.IGNORECASE)
        if page_match:
            try:
                current_page = int(page_match.group(1))
            except ValueError:
                pass
        for section_type, patterns in DOCUMENT_SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    if not any(existing["section_type"] == section_type and existing["heading"] == line for existing in sections):
                        sections.append({
                            "section_type": section_type,
                            "heading": line,
                            "page": current_page,
                            "confidence": "High",
                            "evidence": line,
                        })
                    break
    return sections


def build_extraction_summary(metadata: Dict[str, Any], full_text: Optional[str],
                             document_heading: Optional[str] = None,
                             detected_sector: Optional[str] = None) -> Dict[str, Any]:
    """Build a complete extraction summary for all fields."""
    return {
        "tender_reference": extract_tender_reference(metadata, full_text, document_heading),
        "project_name": extract_project_name(metadata, full_text),
        "employer": extract_employer(metadata, full_text),
        "company_name": extract_company_name(metadata, full_text),
        "procurement_entities": extract_procurement_entities(metadata, full_text),
        "procurement_context": extract_procurement_context(metadata, full_text, detected_sector),
        "document_sections": detect_document_sections(full_text),
    }


def format_candidates_for_display(candidates: List[str]) -> str:
    """Format candidate strings for UI display."""
    if not candidates:
        return ""
    formatted = []
    for i, c in enumerate(candidates, 1):
        formatted.append(f"  Candidate {i}: \"{c}\"")
    return "\n".join(formatted)