"""
Deterministic Currency Detection Engine — evidence-based, no defaults.

Detection Order (strict priority):
  1. Explicit ISO codes with amounts (confidence 1.0)
  2. Currency symbols with amounts (confidence 0.9-0.7)
  3. ISO codes without amounts (confidence 0.6)
  4. Currency symbols without amounts (confidence 0.5-0.3)
  5. Structured procurement metadata (TED, World Bank, UN, ADB, AfDB)
  6. Detected jurisdiction (only if confidence >= 95%)

Never defaults to ZAR. Unknown is better than incorrect.
"""
from __future__ import annotations
import re
import logging
from typing import Dict, List, Optional, Any, Tuple

from ..schemas.currency import CurrencyEvidence

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# ISO 4217 Currency Registry — extend this dict to add new currencies
# No code changes needed elsewhere for new currencies.
# ═══════════════════════════════════════════════════════════════════════

CURRENCY_REGISTRY: Dict[str, Dict[str, str]] = {
    # Major world currencies
    "USD": {"symbol": "$", "name": "US Dollar"},
    "EUR": {"symbol": "€", "name": "Euro"},
    "GBP": {"symbol": "£", "name": "British Pound"},
    "JPY": {"symbol": "¥", "name": "Japanese Yen"},
    "CHF": {"symbol": "CHF", "name": "Swiss Franc"},
    
    # Scandinavian
    "DKK": {"symbol": "kr", "name": "Danish Krone"},
    "NOK": {"symbol": "kr", "name": "Norwegian Krone"},
    "SEK": {"symbol": "kr", "name": "Swedish Krona"},
    
    # Commonwealth / Pacific
    "AUD": {"symbol": "A$", "name": "Australian Dollar"},
    "NZD": {"symbol": "NZ$", "name": "New Zealand Dollar"},
    "CAD": {"symbol": "C$", "name": "Canadian Dollar"},
    
    # Middle East
    "AED": {"symbol": "د.إ", "name": "UAE Dirham"},
    "SAR": {"symbol": "ر.س", "name": "Saudi Riyal"},
    "QAR": {"symbol": "ر.ق", "name": "Qatari Riyal"},
    
    # Africa
    "ZAR": {"symbol": "R", "name": "South African Rand"},
    "NGN": {"symbol": "₦", "name": "Nigerian Naira"},
    "KES": {"symbol": "KSh", "name": "Kenyan Shilling"},
    "EGP": {"symbol": "E£", "name": "Egyptian Pound"},
    "GHS": {"symbol": "GH₵", "name": "Ghanaian Cedi"},
    "MAD": {"symbol": "MAD", "name": "Moroccan Dirham"},
    "TZS": {"symbol": "TSh", "name": "Tanzanian Shilling"},
    "UGX": {"symbol": "USh", "name": "Ugandan Shilling"},
    "ZMW": {"symbol": "ZK", "name": "Zambian Kwacha"},
    "BWP": {"symbol": "P", "name": "Botswana Pula"},
    "MUR": {"symbol": "Rs", "name": "Mauritian Rupee"},
    "NAD": {"symbol": "N$", "name": "Namibian Dollar"},
    "LSL": {"symbol": "L", "name": "Lesotho Loti"},
    "SZL": {"symbol": "E", "name": "Eswatini Lilangeni"},
    
    # Other
    "CNY": {"symbol": "¥", "name": "Chinese Yuan"},
    "INR": {"symbol": "₹", "name": "Indian Rupee"},
    "BRL": {"symbol": "R$", "name": "Brazilian Real"},
    "RUB": {"symbol": "₽", "name": "Russian Ruble"},
    "TRY": {"symbol": "₺", "name": "Turkish Lira"},
    "PLN": {"symbol": "zł", "name": "Polish Zloty"},
}

# Symbol to possible currency codes (prioritized by global frequency)
SYMBOL_MAP: Dict[str, List[str]] = {
    "$": ["USD", "CAD", "AUD", "NZD", "NAD"],
    "€": ["EUR"],
    "£": ["GBP", "EGP"],
    "¥": ["JPY", "CNY"],
    "R": ["ZAR"],
    "R$": ["BRL"],
    "A$": ["AUD"],
    "C$": ["CAD"],
    "NZ$": ["NZD"],
    "N$": ["NAD"],
    "kr": ["DKK", "NOK", "SEK"],
    "CHF": ["CHF"],
    "KSh": ["KES"],
    "GH₵": ["GHS"],
    "TSh": ["TZS"],
    "USh": ["UGX"],
    "ZK": ["ZMW"],
    "P": ["BWP"],
    "Rs": ["MUR"],
    "₹": ["INR"],
    "₦": ["NGN"],
    "₽": ["RUB"],
    "₺": ["TRY"],
    "zł": ["PLN"],
    "د.إ": ["AED"],
    "ر.س": ["SAR"],
    "ر.ق": ["QAR"],
}

# Procurement metadata patterns (TED, World Bank, UN, ADB, AfDB)
PROCUREMENT_PATTERNS: Dict[str, List[Dict[str, Any]]] = {
    "TED": [
        {"pattern": r"TED\s+-\s+Tenders\s+Electronic\s+Daily", "jurisdictions": ["EUR"]},
        {"pattern": r"ted\.europa\.eu", "jurisdictions": ["EUR"]},
    ],
    "WORLD_BANK": [
        {"pattern": r"World\s+Bank\s+(Project|Procurement|Tender)", "jurisdictions": ["USD"]},
        {"pattern": r"IBRD|IDA|International\s+Bank\s+for\s+Reconstruction", "jurisdictions": ["USD"]},
    ],
    "UN": [
        {"pattern": r"United\s+Nations\s+(Development|Procurement|Project)", "jurisdictions": ["USD"]},
        {"pattern": r"UNOPS|UNDP|UNICEF|WFP\s+Procurement", "jurisdictions": ["USD"]},
    ],
    "ADB": [
        {"pattern": r"African\s+Development\s+Bank|AfDB", "jurisdictions": ["USD"]},
        {"pattern": r"Asian\s+Development\s+Bank|ADB", "jurisdictions": ["USD"]},
    ],
}

# Jurisdiction → currency mapping (only used at >= 95% confidence)
JURISDICTION_CURRENCY: Dict[str, str] = {
    "south_africa": "ZAR",
    "united_states": "USD",
    "united_kingdom": "GBP",
    "european_union": "EUR",
    "denmark": "DKK",
    "sweden": "SEK",
    "norway": "NOK",
    "switzerland": "CHF",
    "japan": "JPY",
    "australia": "AUD",
    "new_zealand": "NZD",
    "canada": "CAD",
    "uae": "AED",
    "saudi_arabia": "SAR",
    "qatar": "QAR",
    "nigeria": "NGN",
    "kenya": "KES",
    "egypt": "EGP",
    "ghana": "GHS",
    "morocco": "MAD",
    "tanzania": "TZS",
    "uganda": "UGX",
    "zambia": "ZMW",
    "botswana": "BWP",
    "mauritius": "MUR",
    "namibia": "NAD",
    "lesotho": "LSL",
    "eswatini": "SZL",
    "china": "CNY",
    "india": "INR",
    "brazil": "BRL",
    "russia": "RUB",
    "turkey": "TRY",
    "poland": "PLN",
}

# Compiled regex patterns
ISO_CODE_PATTERN = re.compile(
    r"\b(" + "|".join(CURRENCY_REGISTRY.keys()) + r")\b",
    re.IGNORECASE
)

# Pattern for "amount ISO_CODE" or "SYMBOL amount"
CURRENCY_WITH_AMOUNT_PATTERN = re.compile(
    r"""
    (?:
        (?:^|[\s\(\)\[\]\{\}])
        (
            (?:\d{1,3}(?:[,\.\s]\d{3})*[,\.]\d{2}|\d+(?:[,\.]\d{2})?)
            \s*
            (?:""" + "|".join(CURRENCY_REGISTRY.keys()) + r""")
        )
        (?:$|[\s\)\[\]\{\}])
    )
    |
    (?:
        (?:^|[\s\(\)\[\]\{\}])
        (
            (?:\$|€|£|¥|R|kr|CHF|₦|KSh|E£|GH₵|TSh|USh|ZK|P|Rs|₹|₽|₺|zł|د\.إ|ر\.س|ر\.ق|R\$|A\$|C\$|NZ\$|N\$)
            \s*
            (?:\d{1,3}(?:[,\.\s]\d{3})*[,\.]\d{2}|\d+(?:[,\.]\d{2})?)
        )
        (?:$|[\s\)\[\]\{\}])
    )
    """,
    re.IGNORECASE | re.VERBOSE
)

# Compiled procurement patterns
COMPILED_PROCUREMENT: List[Tuple[re.Pattern, str]] = []
for source, patterns in PROCUREMENT_PATTERNS.items():
    for entry in patterns:
        try:
            compiled = re.compile(entry["pattern"], re.IGNORECASE)
            for jur in entry["jurisdictions"]:
                COMPILED_PROCUREMENT.append((compiled, jur))
        except re.error:
            logger.warning(f"[CURRENCY] Invalid procurement pattern: {entry['pattern']}")


def _extract_page_number(text: str, match_end: int) -> Optional[int]:
    """Extract page number from text near a match."""
    # Look for "Page X" before the match
    before = text[:match_end]
    page_match = re.search(r"\bPage\s*(\d+)\b", before, re.IGNORECASE)
    if page_match:
        return int(page_match.group(1))
    return None


def detect_currency(
    text: Optional[str],
    boq_items: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    detected_jurisdiction: Optional[str] = None,
    jurisdiction_confidence: float = 0.0,
) -> CurrencyEvidence:
    """
    Deterministic currency detection using evidence only.

    Detection priority:
    1. Explicit ISO codes with amounts (confidence 1.0)
    2. Currency symbols with amounts (confidence 0.9-0.7)
    3. ISO codes without amounts (confidence 0.6)
    4. Currency symbols without amounts (confidence 0.5-0.3)
    5. Structured procurement metadata (TED, World Bank, UN, ADB, AfDB)
    6. Detected jurisdiction (only if confidence >= 95%)

    Args:
        text: Full document text
        boq_items: Extracted BOQ items (may contain currency in amounts)
        metadata: Document metadata
        detected_jurisdiction: Jurisdiction code from entity extraction
        jurisdiction_confidence: Confidence of jurisdiction detection (0.0-1.0)

    Returns:
        CurrencyEvidence object (never None, never defaults to ZAR)
    """
    if not text and not boq_items:
        return CurrencyEvidence.not_detected("No document text or BOQ items available for currency detection.")

    # ── Priority 1: Explicit ISO codes with amounts ────────────────
    if text:
        amount_matches = list(CURRENCY_WITH_AMOUNT_PATTERN.finditer(text))
        if amount_matches:
            match = amount_matches[0]
            matched_text = match.group(1) or match.group(2)
            source_text = matched_text.strip()

            # Check for ISO code
            for code in CURRENCY_REGISTRY.keys():
                if code.upper() in source_text.upper():
                    info = CURRENCY_REGISTRY[code]
                    page = _extract_page_number(text, match.end())
                    return CurrencyEvidence.detected(
                        currency_code=code,
                        currency_name=info["name"],
                        currency_symbol=info["symbol"],
                        confidence=1.0,
                        detection_method="iso_code_with_amount",
                        evidence=[f"Explicit ISO code '{code}' found with amount: '{source_text}'"],
                        source_pages=[page] if page else [],
                        source_text=[source_text],
                    )

            # Check for symbol
            # Sort symbols by length (longest first) to match multi-char symbols first
            sorted_symbols = sorted(SYMBOL_MAP.keys(), key=len, reverse=True)
            for symbol in sorted_symbols:
                if symbol in source_text:
                    possible_codes = SYMBOL_MAP[symbol]
                    detected_code = possible_codes[0]
                    info = CURRENCY_REGISTRY[detected_code]
                    conf = 0.9 if len(possible_codes) == 1 else 0.7
                    page = _extract_page_number(text, match.end())
                    return CurrencyEvidence.detected(
                        currency_code=detected_code,
                        currency_name=info["name"],
                        currency_symbol=info["symbol"],
                        confidence=conf,
                        detection_method="symbol_with_amount",
                        evidence=[f"Symbol '{symbol}' found with amount: '{source_text}'"],
                        source_pages=[page] if page else [],
                        source_text=[source_text],
                    )

    # ── Priority 2: Check BOQ items for currency evidence ──────────
    if boq_items:
        for item in boq_items:
            rate = item.get("rate")
            amount = item.get("amount")
            description = str(item.get("description", ""))
            # Check description for ISO codes
            for code in CURRENCY_REGISTRY.keys():
                if code.upper() in description.upper():
                    info = CURRENCY_REGISTRY[code]
                    return CurrencyEvidence.detected(
                        currency_code=code,
                        currency_name=info["name"],
                        currency_symbol=info["symbol"],
                        confidence=0.8,
                        detection_method="boq_item_description",
                        evidence=[f"ISO code '{code}' found in BOQ item description: '{description[:100]}'"],
                        source_text=[description[:200]],
                    )

    # ── Priority 3: ISO codes without amounts ──────────────────────
    if text:
        code_matches = list(ISO_CODE_PATTERN.finditer(text))
        if code_matches:
            match = code_matches[0]
            detected_code = match.group(0).upper()
            if detected_code in CURRENCY_REGISTRY:
                info = CURRENCY_REGISTRY[detected_code]
                page = _extract_page_number(text, match.end())
                return CurrencyEvidence.detected(
                    currency_code=detected_code,
                    currency_name=info["name"],
                    currency_symbol=info["symbol"],
                    confidence=0.6,
                    detection_method="iso_code_only",
                    evidence=[f"ISO code '{detected_code}' found in document text (no amount)"],
                    source_pages=[page] if page else [],
                    source_text=[match.group(0)],
                )

    # ── Priority 4: Currency symbols without amounts ───────────────
    if text:
        sorted_symbols = sorted(SYMBOL_MAP.keys(), key=len, reverse=True)
        for symbol in sorted_symbols:
            if symbol in text:
                possible_codes = SYMBOL_MAP[symbol]
                detected_code = possible_codes[0]
                info = CURRENCY_REGISTRY[detected_code]
                conf = 0.5 if len(possible_codes) == 1 else 0.3
                return CurrencyEvidence.detected(
                    currency_code=detected_code,
                    currency_name=info["name"],
                    currency_symbol=info["symbol"],
                    confidence=conf,
                    detection_method="symbol_only",
                    evidence=[f"Symbol '{symbol}' found in document text (no amount, low confidence)"],
                    source_text=[symbol],
                )

    # ── Priority 5: Procurement metadata ───────────────────────────
    if text:
        for compiled_pattern, jurisdiction in COMPILED_PROCUREMENT:
            if compiled_pattern.search(text):
                code = JURISDICTION_CURRENCY.get(jurisdiction.lower())
                if code and code in CURRENCY_REGISTRY:
                    info = CURRENCY_REGISTRY[code]
                    return CurrencyEvidence.detected(
                        currency_code=code,
                        currency_name=info["name"],
                        currency_symbol=info["symbol"],
                        confidence=0.85,
                        detection_method="procurement_metadata",
                        evidence=[f"Procurement source '{jurisdiction}' detected in document"],
                        source_text=[jurisdiction],
                    )

    # ── Priority 6: Jurisdiction (only if >= 95% confidence) ───────
    if detected_jurisdiction and jurisdiction_confidence >= 0.95:
        normalized_jur = detected_jurisdiction.lower().replace(" ", "_")
        code = JURISDICTION_CURRENCY.get(normalized_jur)
        if code and code in CURRENCY_REGISTRY:
            info = CURRENCY_REGISTRY[code]
            return CurrencyEvidence.detected(
                currency_code=code,
                currency_name=info["name"],
                currency_symbol=info["symbol"],
                confidence=0.95,
                detection_method="jurisdiction",
                evidence=[f"Jurisdiction '{detected_jurisdiction}' detected with {jurisdiction_confidence:.0%} confidence"],
            )

    # ── Not detected ───────────────────────────────────────────────
    return CurrencyEvidence.not_detected("No reliable currency evidence found in document text, BOQ items, metadata, or jurisdiction.")


# ── Backward-compatible alias ───────────────────────────────────────
def get_detector():
    """Return the detect_currency function for backward compatibility."""
    return CurrencyDetector()


class CurrencyDetector:
    """
    CurrencyDetector class for backward compatibility with pipeline.py.
    
    Wraps the detect_currency function in a class interface.
    """

    def detect_from_text(self, text: str) -> CurrencyEvidence:
        """Detect currency from document text only."""
        return detect_currency(text=text)

    def detect(
        self,
        text: Optional[str] = None,
        boq_items: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        detected_jurisdiction: Optional[str] = None,
        jurisdiction_confidence: float = 0.0,
    ) -> CurrencyEvidence:
        """Full currency detection with all available evidence."""
        return detect_currency(
            text=text,
            boq_items=boq_items,
            metadata=metadata,
            detected_jurisdiction=detected_jurisdiction,
            jurisdiction_confidence=jurisdiction_confidence,
        )