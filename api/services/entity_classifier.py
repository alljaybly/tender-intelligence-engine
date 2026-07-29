"""
Entity Classification Engine v1 — Every Numeric Value Classified.

This engine replaces every regex that mistakes phone numbers, registration numbers,
and postcodes for BOQ prices. Every numeric value must be classified before use.

No numeric value may enter pricing, BOQ, or currency detection until classified.

Classification classes:
  Currency, Quantity, BOQ Amount, Percentage, Telephone, Postal Code,
  Registration Number, VAT Number, Company Number, Tender Number,
  Contract Value, Date, Time, Page Number, CPV Code, Reference Number,
  ID, Address Number, Dimension, Weight, Length, Area, Volume, Unknown

Each classification includes: Type, Confidence, Evidence, Page, Reason.
"""
from __future__ import annotations
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

from .currency_engine import CurrencyEngine
from ..schemas.currency import CurrencyEvidence

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Entity Classification Result
# ═══════════════════════════════════════════════════════════════════════

class EntityType:
    """Canonical entity types for numeric classification."""
    CURRENCY = "Currency"
    QUANTITY = "Quantity"
    BOQ_AMOUNT = "BOQAmount"
    PERCENTAGE = "Percentage"
    TELEPHONE = "Telephone"
    POSTAL_CODE = "PostalCode"
    REGISTRATION_NUMBER = "RegistrationNumber"
    VAT_NUMBER = "VATNumber"
    COMPANY_NUMBER = "CompanyNumber"
    TENDER_NUMBER = "TenderNumber"
    CONTRACT_VALUE = "ContractValue"
    DATE = "Date"
    TIME = "Time"
    PAGE_NUMBER = "PageNumber"
    CPV_CODE = "CPVCode"
    REFERENCE_NUMBER = "ReferenceNumber"
    ID = "ID"
    ADDRESS_NUMBER = "AddressNumber"
    DIMENSION = "Dimension"
    WEIGHT = "Weight"
    LENGTH = "Length"
    AREA = "Area"
    VOLUME = "Volume"
    UNKNOWN = "Unknown"


@dataclass
class EntityClassification:
    """Complete classification result for a single numeric entity."""
    entity_type: str                           # EntityType constant
    confidence: float = 0.0                    # 0.0 to 1.0
    evidence: List[str] = field(default_factory=list)
    source_text: str = ""
    page_number: Optional[int] = None
    context: Optional[str] = None
    reason: str = ""
    is_currency: bool = False
    currency_code: Optional[str] = None
    currency_name: Optional[str] = None
    currency_symbol: Optional[str] = None
    amount: Optional[float] = None
    detection_method: str = "pattern_match"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source_text": self.source_text,
            "page_number": self.page_number,
            "context": self.context[:200] if self.context else None,
            "reason": self.reason,
            "is_currency": self.is_currency,
            "currency_code": self.currency_code,
            "currency_name": self.currency_name,
            "currency_symbol": self.currency_symbol,
            "amount": self.amount,
            "detection_method": self.detection_method,
        }


# ═══════════════════════════════════════════════════════════════════════
# Compiled Pattern Registry (single source of truth)
# ═══════════════════════════════════════════════════════════════════════

# ─── Telephone Patterns ────────────────────────────────────────────
_TELEPHONE_INTERNATIONAL = re.compile(
    r"""
    ^\s*
    (?:\+?\d{1,3}[-\s.])?          # Country code
    \(?\d{2,4}\)?                   # Area code
    [-\s.]?\d{3,4}                  # Prefix
    [-\s.]?\d{3,4}                  # Line number
    (?:\s*(?:x|ext)\.?\s*\d{1,6})? # Extension
    \s*$
    """, re.VERBOSE
)
_TELEPHONE_LOCAL = re.compile(
    r"^\s*(?:0\d{1,2})?[-\s.]?\d{3,4}[-\s.]?\d{4,6}\s*$", re.VERBOSE
)

# ─── Postal Code Patterns ──────────────────────────────────────────
_POSTAL_CODE_ZA = re.compile(r"^\s*\d{4}\s*$")
_POSTAL_CODE_US = re.compile(r"^\s*\d{5}(?:-\d{4})?\s*$")
_POSTAL_CODE_UK = re.compile(r"^\s*[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\s*$", re.IGNORECASE)
_POSTAL_CODE_CA = re.compile(r"^\s*[A-Z]\d[A-Z]\s*\d[A-Z]\d\s*$", re.IGNORECASE)

# ─── South African Postal Code (4 digits, must not be a year)
_POSTAL_CODE_SA_EXACT = re.compile(r"^\s*\d{4}\s*$")
# Valid SA postal codes: 0001-9999, but reject common years like 2024, 2025, 2026
_VALID_SA_POSTAL_CODES = set(str(i).zfill(4) for i in range(1, 10000))
_REJECT_YEARS = {str(y) for y in range(1900, 2100)}

# ─── Registration / Company Number Patterns ────────────────────────
_COMPANY_NUMBER_SA = re.compile(
    r"^\s*(?:\d{4}\s*[/\-]\s*\d{3,6}\s*[/\-]\s*\d{3,6}|\d{7,8}\s*[/\-]\s*\d{3,6})\s*$"
)
_CIPC_NUMBER = re.compile(
    r"^\s*(?:CIPC|CK)\s*[/:\-]?\s*\d{4}\s*/\s*\d+\s*/\s*\d+\s*$", re.IGNORECASE
)
_COMPANY_HOUSE_NUMBER = re.compile(
    r"^\s*\d{8}\s*$"  # UK Companies House: 8 digits
)
_COMPANY_KEYWORD = re.compile(
    r"^\s*(?:Company|Registration|Reg|Co\.|Corp|Inc|Ltd|Pty)\s*[:\-]?\s*[\dA-Z/\-]{4,}",
    re.IGNORECASE
)

# ─── VAT Number Patterns ───────────────────────────────────────────
_VAT_SA = re.compile(r"^\s*4\d{9}\s*$")           # SA VAT: 10 digits starting with 4
_VAT_EU = re.compile(r"^\s*[A-Z]{2}\s*\d{8,12}\s*$", re.IGNORECASE)
_VAT_KEYWORD = re.compile(r"^\s*(?:VAT|Vat|vat)\s*[:\-]?\s*\d+", re.IGNORECASE)
_VAT_UK = re.compile(r"^\s*GB\s*\d{9}\s*$", re.IGNORECASE)
_VAT_GB = re.compile(r"^\s*GB\s*\d{3}\s*\d{4}\s*\d{3}\s*$", re.IGNORECASE)

# ─── Tender Number Patterns ────────────────────────────────────────
_TENDER_SA = re.compile(
    r"^\s*(?:ZNT|SCM|TEN|BID|CONTRACT|RFQ|RFP|EOI|ITT|ITB)\s*[/\-]?\s*\d[\d/\-]{3,}\s*$",
    re.IGNORECASE
)
_TENDER_KEYWORD = re.compile(
    r"^\s*(?:Tender|Bid|RFQ|RFP|RFI|EOI|ITT|ITB|Quote)\s*[:\-]?\s*[A-Z0-9/\-]{4,}",
    re.IGNORECASE
)
_TENDER_INTERNATIONAL = re.compile(
    r"^\s*(?:UN|WB|ADB|EU|USAID|DFID|FCDO)\s*[/\-]?\s*[\dA-Z/\-]{4,}",
    re.IGNORECASE
)

# ─── CPV Code Pattern (EU procurement) ──────────────────────────────
_CPV_CODE = re.compile(r"^\s*\d{8}\s*$")

# ─── Date Patterns ──────────────────────────────────────────────────
_DATE_ISO = re.compile(r"^\s*\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}\s*$")
_DATE_TEXT = re.compile(
    r"^\s*\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\s*$",
    re.IGNORECASE
)
_DATE_NUMERIC = re.compile(r"^\s*\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}\s*$")
_DATE_REVERSE = re.compile(r"^\s*\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}\s*$")

# ─── Time Patterns ──────────────────────────────────────────────────
_TIME_24H = re.compile(r"^\s*\d{2}:\d{2}(?::\d{2})?\s*$")
_TIME_12H = re.compile(r"^\s*\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)\s*$")
_TIME_HOURS = re.compile(r"^\s*\d{1,2}\s*(?:am|pm|AM|PM|hrs|hours|h)\s*$", re.IGNORECASE)

# ─── Page Number Patterns ──────────────────────────────────────────
_PAGE_NUMBER_SINGLE = re.compile(r"^\s*Page\s*\d+\s*$", re.IGNORECASE)
_PAGE_NUMBER_RANGE = re.compile(r"^\s*Page\s*\d+\s*(?:of|/|-)\s*\d+\s*$", re.IGNORECASE)
_PAGE_JUST_NUMBER = re.compile(r"^\s*(?:p\.?|pg\.?)\s*\d+", re.IGNORECASE)

# ─── Percentage Patterns ───────────────────────────────────────────
_PERCENTAGE_SYMBOL = re.compile(r"^\s*[\d\.,]+\s*%\s*$")
_PERCENTAGE_WORD = re.compile(r"^\s*[\d\.,]+\s*(?:percent|percentage|pct|per\s*centum)\s*$", re.IGNORECASE)

# ─── Dimension / Weight / Length / Area / Volume ───────────────────
_DIMENSION_GENERIC = re.compile(
    r"^\s*[\d\.,]+\s*(?:mm|cm|m|km)\s*$", re.IGNORECASE
)
_WEIGHT = re.compile(
    r"^\s*[\d\.,]+\s*(?:kg|kgs|g|mg|tonnes|tons|ton|t|kgm)\s*$", re.IGNORECASE
)
_LENGTH = re.compile(
    r"^\s*[\d\.,]+\s*(?:mm|cm|m|km|ft|feet|in|inch|yd|yard|mile|miles)\s*$", re.IGNORECASE
)
_AREA = re.compile(
    r"^\s*[\d\.,]+\s*(?:m2|m²|sq\.?\s*m|ft2|ha|hectares?|acres?)\s*$", re.IGNORECASE
)
_VOLUME = re.compile(
    r"^\s*[\d\.,]+\s*(?:m3|m³|cu\.?\s*m|litres?|l|gallons?|gal)\s*$", re.IGNORECASE
)

# ─── Quantity Patterns ──────────────────────────────────────────────
_QUANTITY_UNIT = re.compile(
    r"^\s*[\d\.,]+\s*(?:units?|items?|each|pcs?|pieces?|boxes?|no\.?|nr\.?|qty[" ".]?|count)\s*$",
    re.IGNORECASE
)

# ─── Address Number Patterns ───────────────────────────────────────
_ADDRESS_NUMBER = re.compile(r"^\s*\d{1,5}\s*$")

# ─── Reference / ID Number Patterns ────────────────────────────────
_REFERENCE_KEYWORD = re.compile(
    r"^\s*(?:Ref|Reference|ID|No\.?|Number|Account|Order|Serial|Batch|Lot)\s*[:\-]?\s*[\dA-Z/\-]{4,}",
    re.IGNORECASE
)
_ID_NUMBER_SA = re.compile(r"^\s*\d{13}\s*$")  # SA ID: 13 digits
_ID_NUMBER_GENERIC = re.compile(r"^\s*\d{9,11}\s*$")

# ─── Contract Value Patterns ───────────────────────────────────────
_CONTRACT_VALUE_KEYWORD = re.compile(
    r"(?:contract\s*(?:value|price|sum|amount|total)|total\s*(?:contract|bid|tender)|bid\s*(?:price|value|amount)|estimated\s*(?:value|cost|price)|procurement\s*(?:value|budget))",
    re.IGNORECASE
)


# ═══════════════════════════════════════════════════════════════════════
# Context Keywords
# ═══════════════════════════════════════════════════════════════════════

_CONTEXT_TELEPHONE = re.compile(
    r"(?:tel\.?|phone|fax|mobile|cell|contact|telephone|call|whatsapp|dial|ring)",
    re.IGNORECASE
)
_CONTEXT_POSTAL = re.compile(
    r"(?:postal\s*code|postcode|zip|p\.?\s*o\.?\s*box|code|postal)",
    re.IGNORECASE
)
_CONTEXT_VAT = re.compile(
    r"(?:vat|vat\s*number|tax\s*number|tax\s*reference|vat\s*registration)",
    re.IGNORECASE
)
_CONTEXT_TENDER = re.compile(
    r"(?:tender\s*(?:no|number|ref|reference|id)|bid\s*(?:no|number|ref)|rfq\s*(?:no|number|ref)|tender\s*number|bid\s*number)",
    re.IGNORECASE
)
_CONTEXT_DATE = re.compile(
    r"(?:date|submission\s*date|closing\s*date|deadline|due\s*date|issued|published|signed|dated|opening\s*date|bid\s*deadline)",
    re.IGNORECASE
)
_CONTEXT_COMPANY = re.compile(
    r"(?:company|registration|reg\s*no|cidb|cipc|enterprise|organisation|business)",
    re.IGNORECASE
)
_CONTEXT_CONTRACT_VALUE = re.compile(
    r"(?:contract|value|amount\s*due|total\s*cost|estimated\s*cost|budget|price|bid\s*price)",
    re.IGNORECASE
)
_CONTEXT_PAGE = re.compile(
    r"(?:page|pg|p\.)\s*\d+",
    re.IGNORECASE
)
_CONTEXT_TIME = re.compile(
    r"(?:time|hours|at\s+\d|by\s+\d|deadline|submission\s+time|closing\s+time)",
    re.IGNORECASE
)
_CONTEXT_CPV = re.compile(
    r"(?:cpv\s*code|cpv\s*number|common\s*procurement\s*vocabulary)",
    re.IGNORECASE
)
_CONTEXT_DIMENSION = re.compile(
    r"(?:length|width|height|depth|thickness|diameter|radius|size)", re.IGNORECASE
)
_CONTEXT_WEIGHT = re.compile(
    r"(?:weight|mass|load|tonnage|payload)", re.IGNORECASE
)
_CONTEXT_AREA = re.compile(
    r"(?:area|footprint|floor\s*area|site\s*area|land\s*area|surface)", re.IGNORECASE
)
_CONTEXT_VOLUME = re.compile(
    r"(?:volume|capacity|cubic|litre)", re.IGNORECASE
)


# ═══════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════

def _get_context_window(text: str, max_chars: int = 40) -> str:
    """Extract a shortened context window for display."""
    clean = text.replace("\n", " ").replace("\r", " ").strip()
    if len(clean) > max_chars:
        return clean[:max_chars] + "..."
    return clean


def _looks_like_digits(value: str) -> bool:
    """Check if the value is primarily digits and separators."""
    cleaned = value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "").replace("+", "").replace("/", "")
    return cleaned.isdigit() and len(cleaned) >= 3


def _extract_numeric_amount(value_str: str) -> Optional[float]:
    """Extract a numeric amount from a string, removing non-numeric chars."""
    cleaned = re.sub(r"[^0-9.,\-\s]", "", value_str).strip()
    if not cleaned:
        return None
    try:
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned and cleaned.count(",") == 1 and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
        return float(cleaned)
    except ValueError:
        return None


def _is_year(value: str) -> bool:
    """Check if a 4-digit number is likely a year."""
    cleaned = value.strip()
    if cleaned.isdigit() and len(cleaned) == 4:
        year = int(cleaned)
        if 1900 <= year <= 2100:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# Classification Function
# ═══════════════════════════════════════════════════════════════════════

def _rejected(entity_type: str, reason: str, evidence: str,
              source_text: str, page: Optional[int] = None,
              context: Optional[str] = None, confidence: float = 1.0) -> EntityClassification:
    """Build a rejection classification."""
    return EntityClassification(
        entity_type=entity_type,
        confidence=confidence,
        evidence=[evidence],
        source_text=source_text,
        page_number=page,
        context=context,
        reason=reason,
        is_currency=False,
    )


def _accepted_currency(amount: float, currency_code: str, currency_name: str,
                       currency_symbol: str, confidence: float, evidence: str,
                       source_text: str, page: Optional[int] = None,
                       context: Optional[str] = None) -> EntityClassification:
    """Build a currency acceptance classification."""
    return EntityClassification(
        entity_type=EntityType.CURRENCY,
        confidence=confidence,
        evidence=[evidence],
        source_text=source_text,
        page_number=page,
        context=context,
        reason=f"Accepted as {currency_code} ({confidence:.0%} confidence)",
        is_currency=True,
        currency_code=currency_code,
        currency_name=currency_name,
        currency_symbol=currency_symbol,
        amount=amount,
        detection_method="currency_engine",
    )


# ═══════════════════════════════════════════════════════════════════════
# Currency Engine Instance
# ═══════════════════════════════════════════════════════════════════════

_currency_engine = CurrencyEngine()


# ═══════════════════════════════════════════════════════════════════════
# Main Classification Entry Point
# ═══════════════════════════════════════════════════════════════════════

def classify_entity(
    value_str: str,
    context: Optional[str] = None,
    page_number: Optional[int] = None,
    document_section: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> EntityClassification:
    """
    Classify a single numeric entity using evidence-based rules.

    Rules:
      1. Context-based classification first (strongest signal)
      2. Pattern-based classification (structural signals)
      3. Currency detection via CurrencyEngine (evidence-based)
      4. Unknown for anything that doesn't match

    Args:
        value_str: The raw text value to classify
        context: Surrounding text (50-100 chars)
        page_number: Page number in document
        document_section: e.g. "header", "footer", "body", "boq"
        jurisdiction: e.g. "south_africa", "denmark"

    Returns:
        EntityClassification with type, confidence, evidence, page, reason
    """
    value = value_str.strip()
    if not value:
        return _rejected(EntityType.UNKNOWN, "Empty value", "No text to classify", value_str, page_number)

    ctx = context or ""

    # ═══════════════════════════════════════════════════════════════════
    # Priority 1: Context-based Classification
    # ═══════════════════════════════════════════════════════════════════

    # Contract value context (must check before general currency)
    if _CONTEXT_CONTRACT_VALUE.search(ctx):
        currency_result = _currency_engine.detect_from_text(value + " " + ctx)
        if currency_result.is_detected and currency_result.confidence >= 0.6:
            amount = _extract_numeric_amount(value)
            if amount is not None:
                return _accepted_currency(
                    amount=amount,
                    currency_code=currency_result.currency_code,
                    currency_name=currency_result.currency_name,
                    currency_symbol=currency_result.currency_symbol,
                    confidence=currency_result.confidence,
                    evidence=f"Contract value context: '{_get_context_window(ctx, 30)}' with {currency_result.format_display()}",
                    source_text=value,
                    page=page_number,
                    context=context,
                )

    # Telephone context
    if _CONTEXT_TELEPHONE.search(ctx):
        if _looks_like_digits(value):
            return _rejected(
                EntityType.TELEPHONE, "Context indicates telephone number",
                f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
            )

    # Postal code context
    if _CONTEXT_POSTAL.search(ctx):
        cleaned = value.replace(" ", "")
        if cleaned.isdigit() and len(cleaned) in (4, 5, 6):
            return _rejected(
                EntityType.POSTAL_CODE, "Context indicates postal code",
                f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
            )

    # VAT context
    if _CONTEXT_VAT.search(ctx):
        return _rejected(
            EntityType.VAT_NUMBER, "Context indicates VAT number",
            f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
        )

    # Company/registration context
    if _CONTEXT_COMPANY.search(ctx):
        cleaned = value.replace(" ", "").replace("/", "").replace("-", "")
        if cleaned.isdigit() and len(cleaned) >= 6:
            return _rejected(
                EntityType.COMPANY_NUMBER, "Context indicates company/registration number",
                f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
            )

    # Tender reference context
    if _CONTEXT_TENDER.search(ctx):
        return _rejected(
            EntityType.TENDER_NUMBER, "Context indicates tender reference number",
            f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
        )

    # Date context
    if _CONTEXT_DATE.search(ctx):
        for pat in [_DATE_ISO, _DATE_TEXT, _DATE_NUMERIC, _DATE_REVERSE]:
            if pat.match(value):
                return _rejected(
                    EntityType.DATE, "Context indicates date",
                    f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
                )

    # Time context
    if _CONTEXT_TIME.search(ctx):
        for pat in [_TIME_24H, _TIME_12H, _TIME_HOURS]:
            if pat.match(value):
                return _rejected(
                    EntityType.TIME, "Context indicates time",
                    f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
                )

    # Page number context
    if _CONTEXT_PAGE.search(ctx):
        if _PAGE_JUST_NUMBER.match(value) or value.strip().isdigit():
            return _rejected(
                EntityType.PAGE_NUMBER, "Context indicates page number",
                f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
            )

    # CPV code context
    if _CONTEXT_CPV.search(ctx):
        if _CPV_CODE.match(value):
            return _rejected(
                EntityType.CPV_CODE, "Context indicates CPV code",
                f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
            )

    # Dimension context
    if _CONTEXT_DIMENSION.search(ctx):
        if _DIMENSION_GENERIC.match(value) or _LENGTH.match(value):
            return _rejected(
                EntityType.DIMENSION, "Context indicates dimension",
                f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
            )

    # Weight context
    if _CONTEXT_WEIGHT.search(ctx):
        if _WEIGHT.match(value):
            return _rejected(
                EntityType.WEIGHT, "Context indicates weight",
                f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
            )

    # Area context
    if _CONTEXT_AREA.search(ctx):
        if _AREA.match(value):
            return _rejected(
                EntityType.AREA, "Context indicates area measurement",
                f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
            )

    # Volume context
    if _CONTEXT_VOLUME.search(ctx):
        if _VOLUME.match(value):
            return _rejected(
                EntityType.VOLUME, "Context indicates volume measurement",
                f"Context: '{_get_context_window(ctx, 30)}'", value, page_number, context,
            )

    # ═══════════════════════════════════════════════════════════════════
    # Priority 2: Pattern-based Classification
    # ═══════════════════════════════════════════════════════════════════

    # Page number (Page X / Page X of Y / p.X)
    if _PAGE_NUMBER_SINGLE.match(value) or _PAGE_NUMBER_RANGE.match(value) or _PAGE_JUST_NUMBER.match(value):
        return _rejected(
            EntityType.PAGE_NUMBER, "Pattern matches page number format",
            f"Matched page number pattern: '{value}'", value, page_number, context,
        )

    # Page number (just a number like 1-9999, but only if in header/footer)
    if document_section in ("header", "footer") and value.strip().isdigit():
        n = int(value.strip())
        if 1 <= n <= 9999:
            return _rejected(
                EntityType.PAGE_NUMBER, "Numeric value in header/footer — likely page number",
                f"Found '{value}' in {document_section} section", value, page_number, context,
            )

    # Telephone (international)
    if _TELEPHONE_INTERNATIONAL.match(value):
        return _rejected(
            EntityType.TELEPHONE, "Pattern matches international telephone format",
            f"Matched '+XX (XXX) XXX-XXXX': '{value}'", value, page_number, context,
        )

    # Telephone (local)
    if _TELEPHONE_LOCAL.match(value):
        return _rejected(
            EntityType.TELEPHONE, "Pattern matches local telephone format",
            f"Matched '0XX XXX XXXX': '{value}'", value, page_number, context,
        )

    # Time (24h, 12h)
    if _TIME_24H.match(value) or _TIME_12H.match(value) or _TIME_HOURS.match(value):
        return _rejected(
            EntityType.TIME, "Pattern matches time format",
            f"Matched time pattern: '{value}'", value, page_number, context,
        )

    # Date (ISO, text, numeric)
    if _DATE_ISO.match(value) or _DATE_TEXT.match(value) or _DATE_NUMERIC.match(value) or _DATE_REVERSE.match(value):
        return _rejected(
            EntityType.DATE, "Pattern matches date format",
            f"Matched date pattern: '{value}'", value, page_number, context,
        )

    # Percentage
    if _PERCENTAGE_SYMBOL.match(value) or _PERCENTAGE_WORD.match(value):
        return _rejected(
            EntityType.PERCENTAGE, "Pattern matches percentage value",
            f"Matched percentage pattern: '{value}'", value, page_number, context,
        )

    # Weight
    if _WEIGHT.match(value):
        return _rejected(
            EntityType.WEIGHT, "Pattern matches weight measurement",
            f"Matched weight pattern: '{value}'", value, page_number, context,
        )

    # Length
    if _LENGTH.match(value):
        return _rejected(
            EntityType.LENGTH, "Pattern matches length measurement",
            f"Matched length pattern: '{value}'", value, page_number, context,
        )

    # Area
    if _AREA.match(value):
        return _rejected(
            EntityType.AREA, "Pattern matches area measurement",
            f"Matched area pattern: '{value}'", value, page_number, context,
        )

    # Volume
    if _VOLUME.match(value):
        return _rejected(
            EntityType.VOLUME, "Pattern matches volume measurement",
            f"Matched volume pattern: '{value}'", value, page_number, context,
        )

    # Dimension (generic)
    if _DIMENSION_GENERIC.match(value):
        return _rejected(
            EntityType.DIMENSION, "Pattern matches dimension measurement",
            f"Matched dimension pattern: '{value}'", value, page_number, context,
        )

    # Quantity with unit
    if _QUANTITY_UNIT.match(value):
        return _rejected(
            EntityType.QUANTITY, "Pattern matches quantity with unit",
            f"Matched quantity pattern: '{value}'", value, page_number, context,
        )

    # VAT (SA)
    if _VAT_KEYWORD.match(value):
        return _rejected(
            EntityType.VAT_NUMBER, "Pattern matches VAT number with prefix",
            f"Matched VAT prefix: '{value}'", value, page_number, context,
        )
    if _VAT_SA.match(value):
        return _rejected(
            EntityType.VAT_NUMBER, "Pattern matches SA VAT format (4 + 9 digits)",
            f"Matched SA VAT: '{value}'", value, page_number, context,
        )
    if _VAT_EU.match(value):
        return _rejected(
            EntityType.VAT_NUMBER, "Pattern matches EU VAT format (XX + 8-12 digits)",
            f"Matched EU VAT: '{value}'", value, page_number, context,
        )
    if _VAT_UK.match(value) or _VAT_GB.match(value):
        return _rejected(
            EntityType.VAT_NUMBER, "Pattern matches UK VAT format",
            f"Matched UK VAT: '{value}'", value, page_number, context,
        )

    # Company / Registration numbers
    if _COMPANY_KEYWORD.match(value):
        return _rejected(
            EntityType.COMPANY_NUMBER, "Pattern matches company/registration number with keyword",
            f"Matched company keyword: '{value}'", value, page_number, context,
        )
    if _CIPC_NUMBER.match(value):
        return _rejected(
            EntityType.COMPANY_NUMBER, "Pattern matches CIPC company registration number",
            f"Matched CIPC: '{value}'", value, page_number, context,
        )
    if _COMPANY_NUMBER_SA.match(value):
        return _rejected(
            EntityType.COMPANY_NUMBER, "Pattern matches SA company registration number format",
            f"Matched SA company: '{value}'", value, page_number, context,
        )
    if _COMPANY_HOUSE_NUMBER.match(value):
        return _rejected(
            EntityType.COMPANY_NUMBER, "Pattern matches UK Companies House number (8 digits)",
            f"Matched UK company: '{value}'", value, page_number, context,
        )

    # Tender numbers
    if _TENDER_SA.match(value):
        return _rejected(
            EntityType.TENDER_NUMBER, "Pattern matches SA tender reference (ZNT/SCM/TEN/BID)",
            f"Matched SA tender: '{value}'", value, page_number, context,
        )
    if _TENDER_KEYWORD.match(value):
        return _rejected(
            EntityType.TENDER_NUMBER, "Pattern matches tender reference with keyword",
            f"Matched tender keyword: '{value}'", value, page_number, context,
        )
    if _TENDER_INTERNATIONAL.match(value):
        return _rejected(
            EntityType.TENDER_NUMBER, "Pattern matches international tender reference (UN/WB/ADB/EU)",
            f"Matched international tender: '{value}'", value, page_number, context,
        )

    # CPV code
    if _CPV_CODE.match(value) and not _is_year(value):
        return _rejected(
            EntityType.CPV_CODE, "Pattern matches CPV code format (8 digits)",
            f"Matched CPV format: '{value}'", value, page_number, context,
        )

    # Reference / ID
    if _REFERENCE_KEYWORD.match(value):
        return _rejected(
            EntityType.REFERENCE_NUMBER, "Pattern matches reference/ID number with keyword",
            f"Matched reference keyword: '{value}'", value, page_number, context,
        )

    # SA ID number (13 digits)
    if _ID_NUMBER_SA.match(value):
        return _rejected(
            EntityType.ID, "Pattern matches SA ID number (13 digits)",
            f"Matched SA ID: '{value}'", value, page_number, context,
        )

    # Generic ID (9-11 digits)
    if _ID_NUMBER_GENERIC.match(value):
        return _rejected(
            EntityType.ID, "Pattern matches generic ID number (9-11 digits)",
            f"Matched generic ID: '{value}'", value, page_number, context,
        )

    # Postal codes (must be after date/year check)
    cleaned_postal = value.replace(" ", "")
    # SA postal code: 4 digits, not a year
    if _POSTAL_CODE_SA_EXACT.match(value) and cleaned_postal in _VALID_SA_POSTAL_CODES and cleaned_postal not in _REJECT_YEARS:
        return _rejected(
            EntityType.POSTAL_CODE, "Pattern matches SA postal code (4 digits)",
            f"Matched SA postal code: '{value}'", value, page_number, context,
        )
    if _POSTAL_CODE_US.match(value) and not _is_year(cleaned_postal):
        return _rejected(
            EntityType.POSTAL_CODE, "Pattern matches US postal code (5+4)",
            f"Matched US postal code: '{value}'", value, page_number, context,
        )
    if _POSTAL_CODE_UK.match(value):
        return _rejected(
            EntityType.POSTAL_CODE, "Pattern matches UK postal code (alphanumeric)",
            f"Matched UK postal code: '{value}'", value, page_number, context,
        )
    if _POSTAL_CODE_CA.match(value):
        return _rejected(
            EntityType.POSTAL_CODE, "Pattern matches Canada postal code (A#A #A#)",
            f"Matched Canada postal code: '{value}'", value, page_number, context,
        )

    # Address number (1-5 digits standalone)
    if _ADDRESS_NUMBER.match(value) and _looks_like_digits(value):
        return _rejected(
            EntityType.ADDRESS_NUMBER, "Pattern matches address/street number",
            f"Matched address number: '{value}'", value, page_number, context,
            confidence=0.6,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Priority 3: Currency Detection via CurrencyEngine
    # ═══════════════════════════════════════════════════════════════════

    currency_result = _currency_engine.detect(
        text=value + (" " + ctx if ctx else ""),
        detected_jurisdiction=jurisdiction,
        jurisdiction_confidence=0.95 if jurisdiction else 0.0,
    )

    if currency_result.is_detected and currency_result.confidence >= 0.6:
        amount = _extract_numeric_amount(value)
        if amount is not None:
            return _accepted_currency(
                amount=amount,
                currency_code=currency_result.currency_code,
                currency_name=currency_result.currency_name,
                currency_symbol=currency_result.currency_symbol,
                confidence=currency_result.confidence,
                evidence="; ".join(currency_result.evidence),
                source_text=value,
                page=page_number,
                context=context,
            )

    # ═══════════════════════════════════════════════════════════════════
    # Priority 4: Unknown
    # ═══════════════════════════════════════════════════════════════════

    return _rejected(
        EntityType.UNKNOWN, "Could not classify — no pattern, context, or currency evidence matched",
        f"No classification for: '{value}'", value, page_number, context,
        confidence=0.0,
    )


# ═══════════════════════════════════════════════════════════════════════
# Batch Classification
# ═══════════════════════════════════════════════════════════════════════

def classify_all(
    text: Optional[str],
    page_number: Optional[int] = None,
    document_section: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Classify every numeric value in a text.

    Returns dict with:
      - accepted: Currency values that can enter pricing/BOQ
      - rejected: All other numeric entities with reasons
    """
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    if not text:
        return {"accepted": accepted, "rejected": rejected}

    # Find all numeric values including currency amounts
    numeric_re = re.compile(
        r"""
        (?:
            (?:[Rr$£€¥₦₵₹₽₺zł]\s*)?
            (?:\d{1,3}(?:[,.\s]\d{3})*[,.]\d{1,4}|\d+(?:[,.]\d+)?)
            (?:\s*(?:USD|EUR|GBP|DKK|NOK|SEK|CHF|CAD|AUD|NZD|JPY|AED|SAR|QAR|ZAR|NGN|KES|EGP|GHS|MAD|TZS|UGX|ZMW|BWP|MUR|NAD|LSL|SZL|CNY|INR|BRL|RUB|TRY|PLN)\b)?
        )
        |
        (?:
            \b(?:USD|EUR|GBP|DKK|NOK|SEK|CHF|CAD|AUD|NZD|JPY|AED|SAR|QAR|ZAR|NGN|KES|EGP|GHS|MAD|TZS|UGX|ZMW|BWP|MUR|NAD|LSL|SZL|CNY|INR|BRL|RUB|TRY|PLN|R)\b
            \s*
            (?:\d{1,3}(?:[,.\s]\d{3})*[,.]\d{1,4}|\d+(?:[,.]\d+)?)
        )
        |
        (?:
            (?:\d{1,3}(?:[,.\s]\d{3})*[,.]\d{1,4}|\d+(?:[,.]\d+)?)
        )
        """,
        re.VERBOSE | re.IGNORECASE
    )

    seen: set = set()

    for match in numeric_re.finditer(text):
        value_str = match.group(0).strip()
        if not value_str or value_str in seen:
            continue
        seen.add(value_str)

        if len(value_str.replace(" ", "")) <= 1:
            continue

        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 80)
        ctx = text[start:end]

        classification = classify_entity(
            value_str=value_str,
            context=ctx,
            page_number=page_number,
            document_section=document_section,
            jurisdiction=jurisdiction,
        )

        if classification.is_currency:
            accepted.append(classification.to_dict())
        else:
            rejected.append(classification.to_dict())

    accepted.sort(key=lambda x: x.get("confidence", 0), reverse=True)

    return {"accepted": accepted, "rejected": rejected}


# ═══════════════════════════════════════════════════════════════════════
# Integration Helpers
# ═══════════════════════════════════════════════════════════════════════

def get_classification_matrix() -> Dict[str, List[str]]:
    """
    Return the full classification matrix showing which patterns
    map to which entity types.
    """
    return {
        EntityType.TELEPHONE: [
            "+XX (XXX) XXX-XXXX", "0XX XXX XXXX", "Local extensions"
        ],
        EntityType.POSTAL_CODE: [
            "XXXX (ZA)", "XXXXX (US)", "XXX XXX (UK)", "A#A #A# (CA)"
        ],
        EntityType.COMPANY_NUMBER: [
            "CIPC XXXX/XXX/XXX", "8 digit UK", "Reg: XXXXXX"
        ],
        EntityType.VAT_NUMBER: [
            "4XXXXXXXXX (SA)", "XX-XXXXXXXX (EU)", "GB XXX XXXX XX"
        ],
        EntityType.TENDER_NUMBER: [
            "ZNT/XXXX/XXXX", "SCM-XXXX-XXXX", "UN/XXXXX"
        ],
        EntityType.CPV_CODE: [
            "XXXXXXXX (8 digits, not a year)"
        ],
        EntityType.DATE: [
            "2024-01-01", "01-Jan-2024", "01/01/2024"
        ],
        EntityType.TIME: [
            "14:30", "2:30 PM", "14:30:00"
        ],
        EntityType.PAGE_NUMBER: [
            "Page 5", "Page 5 of 20", "p.5"
        ],
        EntityType.PERCENTAGE: [
            "15%", "15 percent", "15 pct"
        ],
        EntityType.WEIGHT: [
            "100 kg", "2.5 tonnes", "500 g"
        ],
        EntityType.LENGTH: [
            "10 m", "100 cm", "50 ft"
        ],
        EntityType.AREA: [
            "500 m2", "2 ha", "1000 sq m"
        ],
        EntityType.VOLUME: [
            "1000 l", "5 m3", "50 litres"
        ],
        EntityType.ID: [
            "13-digit SA ID", "9-11 digit generic ID"
        ],
        EntityType.ADDRESS_NUMBER: [
            "123 (street number)"
        ],
        EntityType.CURRENCY: [
            "R 1,500.00", "500 USD", "€ 1.000,00"
        ],
        EntityType.QUANTITY: [
            "10 units", "5 items", "100 pcs"
        ],
        EntityType.UNKNOWN: [
            "Anything that doesn't match above patterns"
        ],
    }