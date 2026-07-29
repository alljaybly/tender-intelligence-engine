"""
Deterministic Numeric Entity Classification Engine.

Every numeric value must be classified before it enters pricing.
No numeric value may enter pricing until it has been classified.

Classification uses:
  - Context (neighbouring words)
  - Formatting patterns
  - Regular expressions
  - Document section (where in the document the value appears)
  - Language
  - Jurisdiction

Only CurrencyAmount objects may enter pricing, BOQ, totals, cost estimation, reports.
All other types are rejected with explanation.

Never guess. Never convert rejected values into money.
"""
from __future__ import annotations
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from .currency_detector import detect_currency, CURRENCY_REGISTRY
from ..schemas.currency import CurrencyEvidence

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Entity Types
# ═══════════════════════════════════════════════════════════════════════

class EntityType:
    """Canonical entity types for numeric classification."""
    CURRENCY_AMOUNT = "CurrencyAmount"
    MONEY = "Money"
    TENDER_VALUE = "TenderValue"
    BUDGET = "Budget"
    AWARD_VALUE = "AwardValue"
    BOQ_QUANTITY = "BOQQuantity"
    BOQ_RATE = "BOQRate"
    BOQ_AMOUNT = "BOQAmount"
    VAT_PERCENT = "VATPercentage"
    RETENTION_PERCENT = "RetentionPercentage"
    PERFORMANCE_BOND_PERCENT = "PerformanceBondPercentage"
    INSURANCE_VALUE = "InsuranceValue"
    DURATION = "Duration"
    CLOSING_DATE = "ClosingDate"
    CONTRACT_NUMBER = "ContractNumber"
    COMPANY_REGISTRATION = "CompanyRegistration"
    TELEPHONE = "Telephone"
    POSTAL_CODE = "PostalCode"
    REFERENCE_NUMBER = "ReferenceNumber"
    WORKFORCE = "Workforce"
    PAGE_NUMBER = "PageNumber"
    WEIGHT = "Weight"
    LENGTH = "Length"
    AREA = "Area"
    VOLUME = "Volume"
    DATE = "Date"
    TIME = "Time"
    PERCENTAGE = "Percentage"
    PERCENT_COMPLETE = "PercentageComplete"
    PERFORMANCE_SCORE = "PerformanceScore"
    PHONE_NUMBER = "PhoneNumber"
    POSTAL_CODE = "PostalCode"
    REGISTRATION_NUMBER = "RegistrationNumber"
    VAT_NUMBER = "VATNumber"
    TENDER_REFERENCE = "TenderReference"
    CONTRACT_REFERENCE = "ContractReference"
    UUID = "UUID"
    DATE = "Date"
    CLAUSE_REFERENCE = "ClauseReference"
    QUANTITY = "Quantity"
    PERCENTAGE = "Percentage"
    DIMENSION = "Dimension"
    COORDINATE = "Coordinate"
    UNKNOWN = "Unknown"


# ═══════════════════════════════════════════════════════════════════════
# Rejection Patterns (priority ordered)
# ═══════════════════════════════════════════════════════════════════════

# 1. Phone Numbers — international, local, with extensions
_PHONE_INTERNATIONAL_RE = re.compile(
    r"""
    ^\s*
    (?:\+?\d{1,3}[-\s.])?      # Country code
    \(?\d{2,4}\)?               # Area code
    [-\s.]?\d{3,4}              # Prefix
    [-\s.]?\d{3,4}              # Line number
    (?:\s*(?:x|ext)\.?\s*\d{1,6})?  # Extension
    \s*$
    """,
    re.VERBOSE
)

_PHONE_LOCAL_RE = re.compile(
    r"""
    ^\s*
    (?:0\d{1,2})?               # Trunk prefix
    [-\s.]?\d{3,4}
    [-\s.]?\d{4,6}
    \s*$
    """,
    re.VERBOSE
)

# 2. Postal Codes — ZA (4 digits), US (5+4), UK (alphanumeric), Canada, generic
_POSTAL_CODE_ZA_RE = re.compile(r"^\s*\d{4}\s*$")
_POSTAL_CODE_US_RE = re.compile(r"^\s*\d{5}(?:-\d{4})?\s*$")
_POSTAL_CODE_UK_RE = re.compile(r"^\s*[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\s*$", re.IGNORECASE)
_POSTAL_CODE_CA_RE = re.compile(r"^\s*[A-Z]\d[A-Z]\s*\d[A-Z]\d\s*$", re.IGNORECASE)
_POSTAL_CODE_GENERIC_RE = re.compile(r"^\s*\d{4,6}\s*$")

# 3. Registration Numbers — VAT, CIDB, CIPC, Company, Tax
_VAT_NUMBER_ZA_RE = re.compile(r"^\s*4\d{9}\s*$")  # SA VAT starts with 4, 10 digits
_VAT_NUMBER_EU_RE = re.compile(r"^\s*[A-Z]{2}\s*\d{8,12}\s*$", re.IGNORECASE)  # EU format: FR12345678901
_VAT_PREFIX_RE = re.compile(r"^\s*(?:VAT|Vat|vat)\s*[:\-]?\s*\d+", re.IGNORECASE)
_CIDB_NUMBER_RE = re.compile(r"^\s*CIDB\s*/\s*\d+\s*/\s*\d+\s*/\s*\d+\s*$", re.IGNORECASE)
_CIPC_NUMBER_RE = re.compile(r"^\s*(?:CIPC|ck|CK)\s*[/:\-]?\s*\d{4}\s*/\s*\d+\s*/\s*\d+\s*$", re.IGNORECASE)
_REGISTRATION_KEYWORD_RE = re.compile(
    r"^\s*(?:Reg|Registration|Company|Tax|Reference|Ref)\s*[:\-]?\s*[\dA-Z/\-]{4,}",
    re.IGNORECASE
)

# 4. Tender References
_TENDER_REF_KEYWORD_RE = re.compile(
    r"^\s*(?:Tender|Bid|RFQ|RFP|RFI|EOI|ITT|ITB)\s*[:\-]?\s*[A-Z0-9/\-]{4,}",
    re.IGNORECASE
)
_TENDER_REF_PATTERN_RE = re.compile(
    r"^\s*(?:ZNT|SCM|TEN|BID|CONTRACT)\s*[/\-]\s*\d[\d/\-]{3,}\s*$",
    re.IGNORECASE
)

# 5. Contract References
_CONTRACT_REF_KEYWORD_RE = re.compile(
    r"^\s*(?:Contract|PO|Order|Purchase\s*Order)\s*[:\-]?\s*[A-Z0-9/\-]{4,}",
    re.IGNORECASE
)
_CONTRACT_REF_PATTERN_RE = re.compile(
    r"^\s*(?:CNT|CON|PO)\s*[/\-]\s*\d[\d/\-]{3,}\s*$",
    re.IGNORECASE
)

# 6. UUIDs
_UUID_RE = re.compile(
    r"^\s*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\s*$",
    re.IGNORECASE
)

# 7. Dates — ISO, SA, EU, US formats
_DATE_ISO_RE = re.compile(
    r"^\s*\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}\s*$"
)
_DATE_TEXT_RE = re.compile(
    r"^\s*\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\s*$",
    re.IGNORECASE
)
_DATE_NUMERIC_RE = re.compile(
    r"^\s*\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}\s*$"
)

# 8. Clause References
_CLAUSE_KEYWORD_RE = re.compile(
    r"^\s*(?:Clause|Section|Part|Rule|Article|Paragraph|Subclause|Annex|Appendix)\s*[:\-]?\s*[\d\.\-]+",
    re.IGNORECASE
)
_CLAUSE_NUMERIC_RE = re.compile(r"^\s*\d+\.\d+(?:\.\d+)*\s*$")

# 9. Coordinates — GPS, DMS, decimal
_COORDINATE_DMS_RE = re.compile(
    r"^\s*\d{1,3}°\s*\d{1,2}['′]\s*\d{1,2}[.\d]*[\"″]?\s*[NS]\s*",
    re.IGNORECASE
)
_COORDINATE_DECIMAL_RE = re.compile(
    r"^\s*-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+\s*$"
)
_COORDINATE_DMS_PAIR_RE = re.compile(
    r"^\s*\d{1,3}°\d{1,2}['′]\d{1,2}[.\d]*[\"″]?[NS]\s*\d{1,3}°\d{1,2}['′]\d{1,2}[.\d]*[\"″]?[EW]",
    re.IGNORECASE
)

# 10. Percentages
_PERCENTAGE_RE = re.compile(
    r"^\s*[\d\.,]+\s*(?:%|percent|percentage|pct)\s*$",
    re.IGNORECASE
)

# 11. Dimensions — length, area, volume
_DIMENSION_RE = re.compile(
    r"^\s*[\d\.,]+\s*(?:mm|cm|m|km|m²|m2|m³|m3|ft|feet|in|inch|yd|yard|ha|hectare)\s*$",
    re.IGNORECASE
)

# 12. Quantities (simple numbers with unit keywords)
_QUANTITY_WITH_UNIT_RE = re.compile(
    r"^\\s*[\\d\\.,]+\\s*(?:units|items|each|pcs|pieces|boxes|crates|kgs|kg|tons|tonnes|litres|l|hours|hrs|days|weeks|months|years)\\s*$",
    re.IGNORECASE
)

# 13. Financial terminology patterns (ESSENTIAL for tender documents)
_TENDER_VALUE_RE = re.compile(r"(?:tender|contract|procurement|project|budget)\s*(?:value|amount|cost|price|bid|proposal)?", re.IGNORECASE)

_AWARD_VALUE_RE = re.compile(r"(?:award|winner|selected|successful)\s*(?:value|amount|bid)?", re.IGNORECASE)

_BUDGET_INITIALIZATION_RE = re.compile(r"budget\s*(?:is|will\s*be|was\s*established|was\s*allocated|is\s*initially|amount)", re.IGNORECASE)

_BOQ_QUANTITY_RE = re.compile(r"(?:quantity|qty|unit\s*quantity|item\s*quantity|no\s*of\s*units)", re.IGNORECASE)

_BOQ_RATE_RE = re.compile(r"(?:rate|unit\s*price|price\s*per\s*(?:unit|hour|day|package|ton)|hourly\s*rate|daily\s*rate)", re.IGNORECASE)

_BOQ_AMOUNT_RE = re.compile(r"(?:total\s*(?:amount|value|cost)|amount)", re.IGNORECASE)

_VAT_PERCENT_RE = re.compile(r"(?:vat|value\s*added\s*tax).{0,30}?\d+(?:\.\d+)?%", re.IGNORECASE)

_RETENTION_PERCENT_RE = re.compile(r"retention.{0,30}?\d+(?:\.\d+)?%", re.IGNORECASE)

_PERFORMANCE_BOND_PERCENT_RE = re.compile(r"performance\s*(?:bond|security|guarantee).{0,30}?\d+(?:\.\d+)?%", re.IGNORECASE)

_INSURANCE_VALUE_RE = re.compile(r"(?:insurance|policy|certificate\s*of\s*insurance).{0,40}?(?:USD|EUR|GBP|ZAR|R|\$|£|€)?\s*\d", re.IGNORECASE)

_DURATION_RE = re.compile(r"(?:duration|period\s*of\s*performance|time\s*frame|execution\s*period|lifespan|operating\s*period).{0,20}?\d+\s*(?:months?|years?|days?|weeks?)", re.IGNORECASE)

_CLOSING_DATE_RE = re.compile(r"(?:submission\s*(?:date|deadline)|closing\s*(?:date|time|deadline)|deadline\s*(?:for\s*submission|opening)).{0,20}?(?:\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})", re.IGNORECASE)

_TELEPHONE_RE = re.compile(r"(?:tel|phone|fax|telephone|contact).{0,20}?\d{3,}", re.IGNORECASE)

_POSTAL_CODE_RE = re.compile(r"(?:postal|postcode|zip)(?:\s*code)?\s*[:\-]?\s*\d+", re.IGNORECASE)

_REGISTRATION_NUMBER_RE = re.compile(r"(?:registration|company\s*registration|reg)(?:\s*number)?\s*[:\-]?\s*[A-Z0-9/\-]+", re.IGNORECASE)

_REFERENCE_NUMBER_RE = re.compile(r"(?:reference|ref|bid\s*number)\s*[:\-]?\s*[A-Z0-9/\-]+", re.IGNORECASE)

_WORKFORCE_RE = re.compile(r"(?:number\s*of\s*(?:personnel|staff|workers|employees|workforce)|staffing\s*(?:requirements|levels)|manpower).{0,20}?\d+", re.IGNORECASE)

_PERCENTAGE_RE = re.compile(
    r"^\\s*[\\d\\.,]+\\s*(?:%|percent|percentage|pct)\\s*$",
    re.IGNORECASE
)

# Context keywords that help classify surrounding values
_CONTEXT_PHONE_KEYWORDS = re.compile(
    r"(?:tel|phone|fax|mobile|cell|contact|telephone|call|whatsapp)",
    re.IGNORECASE
)
_CONTEXT_POSTAL_KEYWORDS = re.compile(
    r"(?:postal\s*code|postcode|zip|p\.?\s*o\.?\s*box|code)",
    re.IGNORECASE
)
_CONTEXT_VAT_KEYWORDS = re.compile(
    r"(?:vat|vat\s*number|tax\s*number|tax\s*reference)",
    re.IGNORECASE
)
_CONTEXT_TENDER_KEYWORDS = re.compile(
    r"(?:tender\s*(?:no|number|ref|reference)|bid\s*(?:no|number|ref)|rfq|ref)",
    re.IGNORECASE
)
_CONTEXT_DATE_KEYWORDS = re.compile(
    r"(?:date|submission\s*date|closing\s*date|deadline|issued|published|signed)",
    re.IGNORECASE
)
_CONTEXT_CLAUSE_KEYWORDS = re.compile(
    r"(?:clause|section|article|paragraph|rule|term)",
    re.IGNORECASE
)


# ═══════════════════════════════════════════════════════════════════════
# Classification Result Schema
# ═══════════════════════════════════════════════════════════════════════

def _rejection(
    entity_type: str,
    reason: str,
    evidence: str,
    source_text: str,
    page_number: Optional[int] = None,
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a standardized rejection result."""
    return {
        "accepted": False,
        "type": entity_type,
        "reason": reason,
        "evidence": evidence,
        "source_text": source_text,
        "page_number": page_number,
        "context": context[:200] if context else None,
    }


def _acceptance(
    amount: float,
    currency_code: str,
    currency_name: str,
    currency_symbol: str,
    confidence: float,
    evidence: str,
    source_text: str,
    page_number: Optional[int] = None,
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a standardized CurrencyAmount acceptance result."""
    return {
        "accepted": True,
        "type": EntityType.CURRENCY_AMOUNT,
        "amount": amount,
        "currency_code": currency_code,
        "currency_name": currency_name,
        "currency_symbol": currency_symbol,
        "confidence": confidence,
        "reason": f"Accepted as {currency_code} amount ({confidence:.0%} confidence)",
        "evidence": evidence,
        "source_text": source_text,
        "page_number": page_number,
        "context": context[:200] if context else None,
    }


# ═══════════════════════════════════════════════════════════════════════
# Main Classification Function
# ═══════════════════════════════════════════════════════════════════════

def classify_numeric_value(
    value_str: str,
    context: Optional[str] = None,
    page_number: Optional[int] = None,
    document_section: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministically classify a numeric value with evidence-based rules.

    Classification uses:
      1. Context (neighbouring words)
      2. Formatting patterns
      3. Regular expressions
      4. Document section (where in the document the value appears)
      5. Language / Jurisdiction

    Only CurrencyAmount with confidence >= 0.7 may enter pricing/BOQ.

    Args:
        value_str: The raw numeric string found in the document
        context: Surrounding text (50-100 chars before and after)
        page_number: Page number where the value was found
        document_section: Section of the document (header, footer, body, boq, etc.)
        jurisdiction: Detected jurisdiction (e.g., "south_africa")

    Returns:
        Dict with classification result (accepted=False for rejected types)
    """
    value_clean = value_str.strip()
    if not value_clean:
        return _rejection(EntityType.UNKNOWN, "Empty value", "No text to classify", value_str, page_number)

    # ── Priority 1: Context-based rejection ──────────────────────────
    # Check context BEFORE pattern matching for higher accuracy
    if context:
        # Phone context
        if _CONTEXT_PHONE_KEYWORDS.search(context):
            # Verify the value looks like a number
            if _looks_like_digits(value_clean):
                return _rejection(
                    EntityType.PHONE_NUMBER,
                    "Context indicates phone number (tel/phone/fax keyword nearby)",
                    f"Context: '{_extract_window(context, 40)}'",
                    value_clean, page_number, context,
                )

        # Postal code context
        if _CONTEXT_POSTAL_KEYWORDS.search(context):
            if _looks_like_digits(value_clean) and len(value_clean.replace(" ", "")) in (4, 5, 6, 7):
                return _rejection(
                    EntityType.POSTAL_CODE,
                    "Context indicates postal code (postal code/zip keyword nearby)",
                    f"Context: '{_extract_window(context, 40)}'",
                    value_clean, page_number, context,
                )

        # VAT context
        if _CONTEXT_VAT_KEYWORDS.search(context):
            return _rejection(
                EntityType.VAT_NUMBER,
                "Context indicates VAT/tax number (VAT/tax keyword nearby)",
                f"Context: '{_extract_window(context, 40)}'",
                value_clean, page_number, context,
            )

        # Tender reference context
        if _CONTEXT_TENDER_KEYWORDS.search(context):
            if not _looks_like_currency(value_clean):
                return _rejection(
                    EntityType.TENDER_REFERENCE,
                    "Context indicates tender reference (tender/bid/RFQ keyword nearby)",
                    f"Context: '{_extract_window(context, 40)}'",
                    value_clean, page_number, context,
                )

        # Date context
        if _CONTEXT_DATE_KEYWORDS.search(context):
            # Only reject if it looks like a date
            for pattern in [_DATE_ISO_RE, _DATE_TEXT_RE, _DATE_NUMERIC_RE]:
                if pattern.match(value_clean):
                    return _rejection(
                        EntityType.DATE,
                        "Context indicates date (date/deadline keyword nearby)",
                        f"Context: '{_extract_window(context, 40)}'",
                        value_clean, page_number, context,
                    )

        # Clause context
        if _CONTEXT_CLAUSE_KEYWORDS.search(context):
            return _rejection(
                EntityType.CLAUSE_REFERENCE,
                "Context indicates clause/section reference (clause/section keyword nearby)",
                f"Context: '{_extract_window(context, 40)}'",
                value_clean, page_number, context,
            )

    # ── Priority 2: Pattern-based rejection ─────────────────────────
    # Phone number patterns
    if _PHONE_INTERNATIONAL_RE.match(value_clean):
        return _rejection(
            EntityType.PHONE_NUMBER,
            "Pattern matches international phone number format",
            f"Matched '+XX (XXX) XXX-XXXX' pattern: '{value_clean}'",
            value_clean, page_number, context,
        )
    if _PHONE_LOCAL_RE.match(value_clean):
        return _rejection(
            EntityType.PHONE_NUMBER,
            "Pattern matches local phone number format",
            f"Matched '0XX XXX XXXX' pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # Postal code patterns
    for pattern, country in [
        (_POSTAL_CODE_ZA_RE, "South Africa"),
        (_POSTAL_CODE_US_RE, "US"),
        (_POSTAL_CODE_UK_RE, "UK"),
        (_POSTAL_CODE_CA_RE, "Canada"),
    ]:
        if pattern.match(value_clean):
            return _rejection(
                EntityType.POSTAL_CODE,
                f"Pattern matches {country} postal code format",
                f"Matched '{value_clean}' against {country} postal code pattern",
                value_clean, page_number, context,
            )

    # VAT number patterns
    if _VAT_PREFIX_RE.match(value_clean):
        return _rejection(
            EntityType.VAT_NUMBER,
            "Value has 'VAT' prefix indicating VAT number",
            f"Matched VAT prefix pattern: '{value_clean}'",
            value_clean, page_number, context,
        )
    if _VAT_NUMBER_ZA_RE.match(value_clean):
        return _rejection(
            EntityType.VAT_NUMBER,
            "Pattern matches South African VAT number (10 digits starting with 4)",
            f"Matched SA VAT pattern: '{value_clean}'",
            value_clean, page_number, context,
        )
    if _VAT_NUMBER_EU_RE.match(value_clean):
        return _rejection(
            EntityType.VAT_NUMBER,
            "Pattern matches EU VAT number format",
            f"Matched EU VAT pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # Registration numbers (CIDB, CIPC, Company)
    if _CIDB_NUMBER_RE.match(value_clean):
        return _rejection(
            EntityType.REGISTRATION_NUMBER,
            "Pattern matches CIDB registration number",
            f"Matched CIDB pattern: '{value_clean}'",
            value_clean, page_number, context,
        )
    if _CIPC_NUMBER_RE.match(value_clean):
        return _rejection(
            EntityType.REGISTRATION_NUMBER,
            "Pattern matches CIPC/company registration number",
            f"Matched CIPC/Company Reg pattern: '{value_clean}'",
            value_clean, page_number, context,
        )
    if _REGISTRATION_KEYWORD_RE.match(value_clean):
        return _rejection(
            EntityType.REGISTRATION_NUMBER,
            "Pattern matches registration/reference number with keyword prefix",
            f"Matched registration keyword pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # Tender references
    if _TENDER_REF_KEYWORD_RE.match(value_clean):
        return _rejection(
            EntityType.TENDER_REFERENCE,
            "Pattern matches tender reference (Tender/Bid/RFQ prefix with number)",
            f"Matched tender keyword pattern: '{value_clean}'",
            value_clean, page_number, context,
        )
    if _TENDER_REF_PATTERN_RE.match(value_clean):
        return _rejection(
            EntityType.TENDER_REFERENCE,
            "Pattern matches SA tender reference format (ZNT/SCM/TEN/BID prefix)",
            f"Matched SA tender pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # Contract references
    if _CONTRACT_REF_KEYWORD_RE.match(value_clean):
        return _rejection(
            EntityType.CONTRACT_REFERENCE,
            "Pattern matches contract reference (Contract/PO/Order prefix)",
            f"Matched contract keyword pattern: '{value_clean}'",
            value_clean, page_number, context,
        )
    if _CONTRACT_REF_PATTERN_RE.match(value_clean):
        return _rejection(
            EntityType.CONTRACT_REFERENCE,
            "Pattern matches contract code format (CNT/CON/PO prefix)",
            f"Matched contract pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # UUIDs
    if _UUID_RE.match(value_clean):
        return _rejection(
            EntityType.UUID,
            "Pattern matches UUID format (8-4-4-4-12 hex digits)",
            f"Matched UUID pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # Dates
    if _DATE_ISO_RE.match(value_clean) or _DATE_TEXT_RE.match(value_clean) or _DATE_NUMERIC_RE.match(value_clean):
        return _rejection(
            EntityType.DATE,
            "Pattern matches date format",
            f"Matched date pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # Clause references
    if _CLAUSE_KEYWORD_RE.match(value_clean):
        return _rejection(
            EntityType.CLAUSE_REFERENCE,
            "Pattern matches clause/section reference with keyword",
            f"Matched clause keyword pattern: '{value_clean}'",
            value_clean, page_number, context,
        )
    if _CLAUSE_NUMERIC_RE.match(value_clean):
        return _rejection(
            EntityType.CLAUSE_REFERENCE,
            "Pattern matches numeric clause reference (e.g., 1.2.3)",
            f"Matched numeric clause pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # Coordinates
    if _COORDINATE_DMS_RE.match(value_clean) or _COORDINATE_DECIMAL_RE.match(value_clean) or _COORDINATE_DMS_PAIR_RE.match(value_clean):
        return _rejection(
            EntityType.COORDINATE,
            "Pattern matches geographic coordinate format",
            f"Matched GPS/DMS coordinate pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # Percentages
    if _PERCENTAGE_RE.match(value_clean):
        return _rejection(
            EntityType.PERCENTAGE,
            "Pattern matches percentage value (% / percent)",
            f"Matched percentage pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # Dimensions
    if _DIMENSION_RE.match(value_clean):
        return _rejection(
            EntityType.DIMENSION,
            "Pattern matches dimension measurement",
            f"Matched dimension pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # Quantities with units
    if _QUANTITY_WITH_UNIT_RE.match(value_clean):
        return _rejection(
            EntityType.QUANTITY,
            "Pattern matches quantity with unit of measure",
            f"Matched quantity pattern: '{value_clean}'",
            value_clean, page_number, context,
        )

    # ── Priority 3: Financial Entity Classification ────────────────────
    # First check for financial entities before falling back to generic detection
    finance_match = None
    finance_entity_type = None
    
    # Check for financial values
    if _TENDER_VALUE_RE.search(context or value_clean):
        finance_entity_type = EntityType.TENDER_VALUE
        finance_match = _TENDER_VALUE_RE.search(context or value_clean)
        confidence = 0.9
    
    elif _AWARD_VALUE_RE.search(context or value_clean):
        finance_entity_type = EntityType.AWARD_VALUE
        finance_match = _AWARD_VALUE_RE.search(context or value_clean)
        confidence = 0.9
    
    elif _BOQ_QUANTITY_RE.search(context or value_clean):
        finance_entity_type = EntityType.BOQ_QUANTITY
        finance_match = _BOQ_QUANTITY_RE.search(context or value_clean)
        confidence = 0.8
    
    elif _BOQ_RATE_RE.search(context or value_clean):
        finance_entity_type = EntityType.BOQ_RATE
        finance_match = _BOQ_RATE_RE.search(context or value_clean)
        confidence = 0.8
    
    elif _VAT_PERCENT_RE.search(context or value_clean):
        finance_entity_type = EntityType.VAT_PERCENT
        finance_match = _VAT_PERCENT_RE.search(context or value_clean)
        confidence = 0.85
    
    elif _RETENTION_PERCENT_RE.search(context or value_clean):
        finance_entity_type = EntityType.RETENTION_PERCENT
        finance_match = _RETENTION_PERCENT_RE.search(context or value_clean)
        confidence = 0.85
    
    elif _PERFORMANCE_BOND_PERCENT_RE.search(context or value_clean):
        finance_entity_type = EntityType.PERFORMANCE_BOND_PERCENT
        finance_match = _PERFORMANCE_BOND_PERCENT_RE.search(context or value_clean)
        confidence = 0.85
    
    elif _INSURANCE_VALUE_RE.search(context or value_clean):
        finance_entity_type = EntityType.INSURANCE_VALUE
        finance_match = _INSURANCE_VALUE_RE.search(context or value_clean)
        confidence = 0.8
    
    elif _DURATION_RE.search(context or value_clean):
        finance_entity_type = EntityType.DURATION
        finance_match = _DURATION_RE.search(context or value_clean)
        confidence = 0.85
    
    elif _CLOSING_DATE_RE.search(context or value_clean[:200]):  # Limit date checking to context
        finance_entity_type = EntityType.CLOSING_DATE
        finance_match = _CLOSING_DATE_RE.search(context or "")
        confidence = 0.85
    
    elif _TELEPHONE_RE.search(context or value_clean):
        finance_entity_type = EntityType.TELEPHONE
        finance_match = _TELEPHONE_RE.search(context or value_clean)
        confidence = 0.9
    
    elif _POSTAL_CODE_RE.search(context or value_clean):
        finance_entity_type = EntityType.POSTAL_CODE
        finance_match = _POSTAL_CODE_RE.search(context or value_clean)
        confidence = 0.9
    
    elif _REGISTRATION_NUMBER_RE.search(context or value_clean):
        finance_entity_type = EntityType.COMPANY_REGISTRATION
        finance_match = _REGISTRATION_NUMBER_RE.search(context or value_clean)
        confidence = 0.9
    
    elif _REFERENCE_NUMBER_RE.search(context or value_clean):
        finance_entity_type = EntityType.REFERENCE_NUMBER
        finance_match = _REFERENCE_NUMBER_RE.search(context or value_clean)
        confidence = 0.8
    
    elif _WORKFORCE_RE.search(context or value_clean):
        finance_entity_type = EntityType.WORKFORCE
        finance_match = _WORKFORCE_RE.search(context or value_clean)
        confidence = 0.8
    
    # If we found a financial entity, handle it
    if finance_match and finance_entity_type:
        # Extract the numeric portion
        match_text = finance_match.group(0)
        
        # Extract numeric value
        amount_match = re.search(r'\d+(?:\.\d+)?', match_text)
        if amount_match:
            amount = float(amount_match.group(0))
            
            return _acceptance(
                amount=amount,
                currency_code=None,
                currency_name=None,
                currency_symbol=None,
                confidence=confidence,
                evidence=f"Detected as {finance_entity_type.name} using financial pattern",
                source_text=match_text,
                page_number=page_number,
                context=context,
            )
    
    # ── Priority 4: Currency Amount Detection ───────────────────────
    # Use the deterministic currency detector with full context
    currency_evidence = detect_currency(
        text=context or value_clean,
        detected_jurisdiction=jurisdiction,
        jurisdiction_confidence=0.95 if jurisdiction else 0.0,
    )

    if currency_evidence.is_detected and currency_evidence.confidence >= 0.7:
        # Extract the numeric amount from the matched text
        amount = _extract_amount(value_clean)
        if amount is not None:
            return _acceptance(
                amount=amount,
                currency_code=currency_evidence.currency_code,
                currency_name=currency_evidence.currency_name,
                currency_symbol=currency_evidence.currency_symbol,
                confidence=currency_evidence.confidence,
                evidence="; ".join(currency_evidence.evidence),
                source_text=value_clean,
                page_number=page_number,
                context=context,
            )

    # ── Final: Unknown ──────────────────────────────────────────────
    return _rejection(
        EntityType.UNKNOWN,
        "Could not classify as any known entity type",
        f"No pattern, context, or currency evidence matched for: '{value_clean}'",
        value_clean, page_number, context,
    )


# ═══════════════════════════════════════════════════════════════════════
# Batch Classification
# ═══════════════════════════════════════════════════════════════════════

def classify_all_numeric_values(
    text: Optional[str],
    page_number: Optional[int] = None,
    document_section: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Classify all numeric values in a given text string.

    Returns a dict with:
      - accepted: List of CurrencyAmount objects (confidence >= 0.7)
      - rejected: List of all other numeric entity types with reasons

    Each entry includes:
      - type, accepted, reason, evidence, source_text, page_number, context
    """
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    if not text:
        return {"accepted": accepted, "rejected": rejected}

    # Pattern to find potential currency/numeric values
    # Matches: symbols+numbers, numbers+ISO codes, or just numbers
    number_re = re.compile(
        r"""
        (?:
            # Option 1: Currency symbol followed by number
            (?:[Rr$£€¥₦₵₹₽₺zł]\s*)?
            (?:\d{1,3}(?:[,.\s]\d{3})*[,.]\d{1,4}|\d+(?:[,.]\d+)?)
            (?:\s*(?:USD|EUR|GBP|DKK|NOK|SEK|CHF|CAD|AUD|NZD|JPY|AED|SAR|QAR|ZAR|NGN|KES|EGP|GHS|MAD|TZS|UGX|ZMW|BWP|MUR|NAD|LSL|SZL|CNY|INR|BRL|RUB|TRY|PLN)\b)?
        )
        |
        (?:
            # Option 2: ISO code before number
            \b(?:USD|EUR|GBP|DKK|NOK|SEK|CHF|CAD|AUD|NZD|JPY|AED|SAR|QAR|ZAR|NGN|KES|EGP|GHS|MAD|TZS|UGX|ZMW|BWP|MUR|NAD|LSL|SZL|CNY|INR|BRL|RUB|TRY|PLN|R)\b
            \s*
            (?:\d{1,3}(?:[,.\s]\d{3})*[,.]\d{1,4}|\d+(?:[,.]\d+)?)
        )
        |
        (?:
            # Option 3: Standalone numeric value (any number)
            (?:\d{1,3}(?:[,.\s]\d{3})*[,.]\d{1,4}|\d+(?:[,.]\d+)?)
        )
        """,
        re.VERBOSE | re.IGNORECASE
    )

    # Track seen values to avoid duplicates
    seen: set = set()

    for match in number_re.finditer(text):
        value_str = match.group(0).strip()
        if not value_str or value_str in seen:
            continue
        seen.add(value_str)

        # Skip very short values (single digits, years)
        if len(value_str.replace(" ", "")) <= 1:
            continue

        # Get surrounding context (100 chars before and after)
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 100)
        context = text[start:end]

        classification = classify_numeric_value(
            value_str=value_str,
            context=context,
            page_number=page_number,
            document_section=document_section,
            jurisdiction=jurisdiction,
        )

        if classification["accepted"]:
            accepted.append(classification)
        else:
            rejected.append(classification)

    # Sort accepted by confidence descending
    accepted.sort(key=lambda x: x.get("confidence", 0), reverse=True)

    return {"accepted": accepted, "rejected": rejected}


# ═══════════════════════════════════════════════════════════════════════
# Internal Helpers
# ═══════════════════════════════════════════════════════════════════════

def _extract_window(text: str, max_chars: int = 40) -> str:
    """Extract a window of text around a value, truncated for display."""
    clean = text.replace("\n", " ").replace("\r", " ").strip()
    if len(clean) > max_chars:
        return clean[:max_chars] + "..."
    return clean


def _looks_like_digits(value: str) -> bool:
    """Check if the value is primarily composed of digits and separators."""
    cleaned = value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "").replace("+", "")
    return cleaned.isdigit() and len(cleaned) >= 3


def _looks_like_currency(value: str) -> bool:
    """Check if the value looks like a currency amount (has decimal places)."""
    cleaned = value.replace(" ", "").replace(",", "")
    if "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 2:
            return True
    # Check for currency symbols
    symbols = ["R", "$", "£", "€", "¥", "₦", "₹"]
    for s in symbols:
        if s in value:
            return True
    return False


def _extract_amount(value_str: str) -> Optional[float]:
    """Extract a numeric amount from a string, removing currency symbols."""
    cleaned = re.sub(r"[^0-9.,]", "", value_str)
    if not cleaned:
        return None
    try:
        # Handle European format: 1.234,56
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                # European: 1.234,56
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # Standard: 1,234.56
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned and cleaned.count(",") == 1 and "." not in cleaned:
            # Could be decimal comma
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
        return float(cleaned)
    except ValueError:
        return None