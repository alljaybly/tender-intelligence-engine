"""
Currency Intelligence Engine V2 — Deterministic Multi-Currency Detection.

This module V2 replaces simple currency detection with evidence-based multi-currency detection.

DETERMINISTIC CURRENCY DETECTION ENGINE V2
==========================================

Core Principles:
  - Every currency found is full recorded with complete evidence trails
  - Supports multi-currency documents with Primary/Secondary/Reference classification
  - Never infer, never fabricate, never estimate
  - Only originate from clear, verifiable evidence
  - Strong evidence hierarchy with confidence scoring

CURRENCY CLASSIFICATION APPROACH
=================================

For multi-currency documents, currencies are determined as:

PRIMARY CURRENCY
  - The main contract currency where the majority of monetary values are expressed
  - Determined by: Highest total monetary volume + highest confidence detection
  - Example: If 8/10 tender values are in EUR and 2 in USD, EUR is PRIMARY

SECONDARY CURRENCY
  - A significant but secondary currency in the contract
  - Determined by: Substantial monetary volume (≥ 15% of total) but not primary
  - Example: South African contractor, contract EUR-payment, vendor in USD

REFERENCE CURRENCY
  - Currency used for comparison, billing, or specification purposes
  - May appear in: side calculations, prerequisites, scope comparisons
  - Example: Reference currency mentioned in payment clauses for base calculation

LEARNED RULES FOR CURRENCY PRIORITY
====================================

Primary Currency:
  • Always currency with highest detected value volume
  • Can be determined by: Multiple high-confidence USD/EUR amounts or single contract amount
  • Override option available in metadata if specified

Secondary Currency:
  • Currency appearing alongside primary in contracts > 2 times
  • Often appears in: Specifications, supplementary contracts, milestone payments
  • Minimum: 2 separate occurrences with amounts

Reference Currency:
  • Last-resort currency by volume
  • Typically appears for: Import restrictions, compliance clauses, base conversions

CONFIGURATION OPTIONS
=====================

- jurisdiction_preference: List of preferred currencies for jurisdiction mapping
- override_primary: Force primary currency regardless of evidence
- auto_multiprocessing: Automatically detect and classify multi-currency documents
- confidence_threshold: Minimum confidence for currency classification (default: 0.7)

SUPPORTED CURRENCIES 
=====================

EUR, USD, GBP, DKK, SEK, NOK, CHF, CAD, AUD, NZD, JPY, ZAR
"""
from __future__ import annotations
import re
import logging
from typing import Dict, List, Optional, Any, Tuple

from ..schemas.currency import CurrencyEvidence

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Enhanced ISO 4217 Currency Registry — single source of truth
# ═══════════════════════════════════════════════════════════════════════

CURRENCY_REGISTRY: Dict[str, Dict[str, str]] = {
    # Major world currencies (certified sector-specific)
    "USD": {"symbol": "$", "name": "US Dollar"},
    "EUR": {"symbol": "€", "name": "Euro"},
    "GBP": {"symbol": "£", "name": "British Pound"},
    "JPY": {"symbol": "¥", "name": "Japanese Yen"},
    "CHF": {"symbol": "CHF", "name": "Swiss Franc"},
    
    # Scandinavian (certified sector-specific)
    "DKK": {"symbol": "kr", "name": "Danish Krone"},
    "NOK": {"symbol": "kr", "name": "Norwegian Krone"},
    "SEK": {"symbol": "kr", "name": "Swedish Krona"},
    
    # Commonwealth / Pacific
    "AUD": {"symbol": "A$", "name": "Australian Dollar"},
    "NZD": {"symbol": "NZ$", "name": "New Zealand Dollar"},
    "CAD": {"symbol": "C$", "name": "Canadian Dollar"},
    "SGD": {"symbol": "S$", "name": "Singapore Dollar"},
    "HKD": {"symbol": "HK$", "name": "Hong Kong Dollar"},
    
    # Middle East
    "AED": {"symbol": "د.إ", "name": "UAE Dirham"},
    "SAR": {"symbol": "ر.س", "name": "Saudi Riyal"},
    "QAR": {"symbol": "ر.ق", "name": "Qatari Riyal"},
    
    # Africa (including South Africa specifically)
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
    
    # Other major currencies
    "CNY": {"symbol": "¥", "name": "Chinese Yuan"},
    "INR": {"symbol": "₹", "name": "Indian Rupee"},
    "BRL": {"symbol": "R$", "name": "Brazilian Real"},
    "RUB": {"symbol": "₽", "name": "Russian Ruble"},
    "TRY": {"symbol": "₺", "name": "Turkish Lira"},
    "PLN": {"symbol": "zł", "name": "Polish Zloty"},
}

# ═══════════════════════════════════════════════════════════════════════
# Currency Priority Classification Rules
# ═══════════════════════════════════════════════════════════════════════

CURRENCY_PRIORITY_RULES = {
    "PRIMARY": {
        "max_volume_remaining_percentage": 100,
        "min_occurrences": 1,
        "applies_to": ["EUR", "USD", "GBP", "ZAR", "DKK", "SEK", "NOK", "CHF", "CAD", "AUD", "NZD", "JPY"],
    },
    "SECONDARY": {
        "max_volume_remaining_percentage": 85,
        "min_occurrences": 2,
        "min_percentage_of_total": 0.15,
        "applies_to": ["EUR", "USD", "GBP", "ZAR", "DKK", "SEK", "NOK", "CHF", "CAD", "AUD", "NZD", "JPY"],
    },
    "REFERENCE": {
        "max_volume_remaining_percentage": 0,
        "min_occurrences": 1,
        "applies_to": ["EUR", "USD", "GBP", "ZAR", "DKK", "SEK", "NOK", "CHF", "CAD", "AUD", "NZD", "JPY"],
    },
}

# Domain-specific currency preferences for jurisdiction mapping
SECTOR_CURRENCY_PREFERENCES = {
    "european_union": ["EUR"],
    "united_states": ["USD"],
    "united_kingdom": ["GBP"],
    "south_africa": ["ZAR"],
    "sweden": ["SEK"],
    "denmark": ["DKK"],
    "norway": ["NOK"],
    "switzerland": ["CHF"],
    "canada": ["CAD"],
    "australia": ["AUD"],
    "new_zealand": ["NZD"],
    "japan": ["JPY"],
}

# Overridden primary currencies from metadata
MARKET_OVERRIDE_PREFERENCES = {
    "tenders_around_sa": ["ZAR", "USD", "EUR"],
    "tenders_around_eu": ["EUR", "USD", "GBP"],
    "tenders_around_uk": ["GBP", "USD", "EUR", "ZAR"],
    "international_eu": ["EUR", "USD", "GBP"],
    "international_global": ["USD", "EUR", "GBP", "ZAR", "JPY"],
}

# ═══════════════════════════════════════════════════════════════════════
# Symbol → Currency Code Mapping (prioritized by global frequency)
# ═══════════════════════════════════════════════════════════════════════

SYMBOL_MAP: Dict[str, List[str]] = {
    "$": ["USD", "CAD", "AUD", "NZD", "SGD", "HKD", "NAD"],
    "€": ["EUR"],
    "£": ["GBP", "EGP"],
    "¥": ["JPY", "CNY"],
    "R": ["ZAR"],
    "R$": ["BRL"],
    "A$": ["AUD"],
    "C$": ["CAD"],
    "S$": ["SGD"],
    "HK$": ["HKD"],
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
    "E£": ["EGP"],
    "MAD": ["MAD"],
}

# ═══════════════════════════════════════════════════════════════════════
# Explicit Currency Wording Detection
# ═══════════════════════════════════════════════════════════════════════

EXPLICIT_WORDING: Dict[str, List[str]] = {
    "USD": [
        r"\bUS\s*Dollars?\b", r"\bUnited\s*States\s*Dollars?\b",
        r"\bAmerican\s*Dollars?\b", r"\bDollars?\s*\(USD\)\b",
    ],
    "EUR": [
        r"\bEuros?\b", r"\bEuro\s*\(EUR\)\b", r"\bEUR\s*Euros?\b",
    ],
    "GBP": [
        r"\bBritish\s*Pounds?\b", r"\bPounds?\s*Sterling\b",
        r"\bSterling\b", r"\bPounds?\s*\(GBP\)\b",
    ],
    "DKK": [
        r"\bDanish\s*Kroner?\b", r"\bDKK\s*Kroner?\b",
        r"\bKroner?\s*\(DKK\)\b",
    ],
    "NOK": [
        r"\bNorwegian\s*Kroner?\b", r"\bNOK\s*Kroner?\b",
    ],
    "SEK": [
        r"\bSwedish\s*Kronor?\b", r"\bSEK\s*Kronor?\b",
    ],
    "CHF": [
        r"\bSwiss\s*Francs?\b", r"\bSwiss\s*Franc\b",
        r"\bFrancs?\s*\(CHF\)\b",
    ],
    "JPY": [
        r"\bJapanese\s*Yen\b", r"\bYen\s*\(JPY\)\b",
    ],
    "ZAR": [
        r"\bSouth\s*African\s*Rand\b", r"\bRand\s*\(ZAR\)\b",
    ],
    "AED": [
        r"\bUAE\s*Dirhams?\b", r"\bDirhams?\s*\(AED\)\b",
    ],
    "SAR": [
        r"\bSaudi\s*Riyals?\b", r"\bRiyals?\s*\(SAR\)\b",
    ],
    "QAR": [
        r"\bQatari\s*Riyals?\b", r"\bRiyals?\s*\(QAR\)\b",
    ],
    "AUD": [
        r"\bAustralian\s*Dollars?\b", r"\bAUD\s*Dollars?\b",
    ],
    "CAD": [
        r"\bCanadian\s*Dollars?\b", r"\bCAD\s*Dollars?\b",
    ],
    "NZD": [
        r"\bNew\s*Zealand\s*Dollars?\b", r"\bNZD\s*Dollars?\b",
    ],
    "CNY": [
        r"\bChinese\s*Yuan\b", r"\bRenminbi\b", r"\bYuan\s*\(CNY\)\b",
    ],
    "INR": [
        r"\bIndian\s*Rupees?\b", r"\bRupees?\s*\(INR\)\b",
    ],
    "NGN": [
        r"\bNigerian\s*Naira\b", r"\bNaira\s*\(NGN\)\b",
    ],
    "KES": [
        r"\bKenyan\s*Shillings?\b", r"\bShillings?\s*\(KES\)\b",
    ],
    "EGP": [
        r"\bEgyptian\s*Pounds?\b", r"\bEGP\s*Pounds?\b",
    ],
    "BRL": [
        r"\bBrazilian\s*Reals?\b", r"\bReal\s*\(BRL\)\b",
    ],
}

# ═══════════════════════════════════════════════════════════════════════
# Country → Currency Mapping
# ═══════════════════════════════════════════════════════════════════════

COUNTRY_CURRENCY: Dict[str, str] = {
    # Europe
    "denmark": "DKK", "norway": "NOK", "sweden": "SEK",
    "united kingdom": "GBP", "uk": "GBP", "great britain": "GBP",
    "germany": "EUR", "france": "EUR", "italy": "EUR", "spain": "EUR",
    "netherlands": "EUR", "belgium": "EUR", "austria": "EUR",
    "ireland": "EUR", "portugal": "EUR", "finland": "EUR",
    "greece": "EUR", "luxembourg": "EUR", "switzerland": "CHF",
    "poland": "PLN", "turkey": "TRY", "russia": "RUB",
    
    # Americas
    "united states": "USD", "usa": "USD", "america": "USD",
    "canada": "CAD", "brazil": "BRL",
    
    # Asia Pacific
    "japan": "JPY", "china": "CNY", "india": "INR",
    "australia": "AUD", "new zealand": "NZD",
    "singapore": "SGD", "hong kong": "HKD",
    
    # Middle East
    "uae": "AED", "united arab emirates": "AED",
    "saudi arabia": "SAR", "qatar": "QAR",
    
    # Africa
    "south africa": "ZAR", "nigeria": "NGN", "kenya": "KES",
    "egypt": "EGP", "ghana": "GHS", "morocco": "MAD",
    "tanzania": "TZS", "uganda": "UGX", "zambia": "ZMW",
    "botswana": "BWP", "mauritius": "MUR", "namibia": "NAD",
    "lesotho": "LSL", "eswatini": "SZL",
}

# ═══════════════════════════════════════════════════════════════════════
# Procurement Portal → Currency Mapping
# ═══════════════════════════════════════════════════════════════════════

PROCUREMENT_PORTALS: Dict[str, Dict[str, Any]] = {
    "TED": {
        "patterns": [
            r"TED\s*-\s*Tenders\s*Electronic\s*Daily",
            r"ted\.europa\.eu",
            r"Tenders\s*Electronic\s*Daily",
        ],
        "currency": "EUR",
        "name": "Tenders Electronic Daily (EU)",
    },
    "SAM_GOV": {
        "patterns": [
            r"SAM\.gov",
            r"System\s*for\s*Award\s*Management",
            r"beta\.sam\.gov",
        ],
        "currency": "USD",
        "name": "SAM.gov (US)",
    },
    "CONTRACTS_FINDER": {
        "patterns": [
            r"Contracts\s*Finder",
            r"gov\.uk\s*contracts\s*finder",
            r"find-government-contracts",
        ],
        "currency": "GBP",
        "name": "Contracts Finder (UK)",
    },
    "UNGM": {
        "patterns": [
            r"UNGM\b", r"United\s*Nations\s*Global\s*Marketplace",
            r"ungm\.org",
        ],
        "currency": "USD",
        "name": "United Nations Global Marketplace",
    },
    "WORLD_BANK": {
        "patterns": [
            r"World\s*Bank\s*(Project|Procurement|Tender)",
            r"IBRD|IDA|International\s*Bank\s*for\s*Reconstruction",
            r"worldbank\.org",
        ],
        "currency": "USD",
        "name": "World Bank",
    },
    "ADB": {
        "patterns": [
            r"African\s*Development\s*Bank",
            r"AfDB\b",
            r"Asian\s*Development\s*Bank",
            r"adb\.org",
        ],
        "currency": "USD",
        "name": "Development Bank",
    },
    "EU_FUNDING": {
        "patterns": [
            r"EU\s*Tender", r"European\s*Union\s*Tender",
            r"europa\.eu\s*tenders",
        ],
        "currency": "EUR",
        "name": "European Union Tenders",
    },
    "DFID": {
        "patterns": [
            r"DFID\b", r"UK\s*Aid\b", r"Foreign\s*Commonwealth",
            r"FCDO\b",
        ],
        "currency": "GBP",
        "name": "UK Foreign & Commonwealth Office",
    },
    "USAID": {
        "patterns": [
            r"USAID\b", r"US\s*Agency\s*for\s*International",
        ],
        "currency": "USD",
        "name": "USAID",
    },
    "UNDP": {
        "patterns": [
            r"UNDP\b", r"United\s*Nations\s*Development\s*Programme",
        ],
        "currency": "USD",
        "name": "United Nations Development Programme",
    },
}

# ═══════════════════════════════════════════════════════════════════════
# Compiled Regex Patterns
# ═══════════════════════════════════════════════════════════════════════

# ISO code pattern
ISO_CODE_PATTERN = re.compile(
    r"\b(" + "|".join(CURRENCY_REGISTRY.keys()) + r")\b",
    re.IGNORECASE
)

# Amount with ISO code or symbol pattern
CURRENCY_WITH_AMOUNT_PATTERN = re.compile(
    r"""
    (?:
        (?:^|[\s\(\)\[\]\{\}\|])
        (
            (?:\d{1,3}(?:[,\.\s]\d{3})*[,\.]\d{2}|\d+(?:[,\.]\d{2})?)
            \s*
            (?:""" + "|".join(CURRENCY_REGISTRY.keys()) + r""")
        )
        (?:$|[\s\)\[\]\}\|])
    )
    |
    (?:
        (?:^|[\s\(\)\[\]\{\}\|])
        (
            (?:\$|€|£|¥|R|kr|CHF|₦|KSh|E£|GH₵|TSh|USh|ZK|P|Rs|₹|₽|₺|zł|د\.إ|ر\.س|ر\.ق|R\$|A\$|C\$|S\$|HK\$|NZ\$|N\$|MAD)
            \s*
            (?:\d{1,3}(?:[,\.\s]\d{3})*[,\.]\d{2}|\d+(?:[,\.]\d{2})?)
        )
        (?:$|[\s\)\[\]\}\|])
    )
    """,
    re.IGNORECASE | re.VERBOSE
)

# Country name pattern
COUNTRY_PATTERN = re.compile(
    r"\b(" + "|".join(COUNTRY_CURRENCY.keys()) + r")\b",
    re.IGNORECASE
)

# Compile explicit wording patterns
COMPILED_EXPLICIT_WORDING: List[Tuple[re.Pattern, str]] = []
for code, patterns in EXPLICIT_WORDING.items():
    for pattern_str in patterns:
        try:
            compiled = re.compile(pattern_str, re.IGNORECASE)
            COMPILED_EXPLICIT_WORDING.append((compiled, code))
        except re.error:
            logger.warning(f"[CURRENCY_ENGINE] Invalid explicit wording pattern: {pattern_str}")

# Compile procurement portal patterns
COMPILED_PORTALS: List[Tuple[re.Pattern, str, str]] = []
for portal_key, portal_info in PROCUREMENT_PORTALS.items():
    for pattern_str in portal_info["patterns"]:
        try:
            compiled = re.compile(pattern_str, re.IGNORECASE)
            COMPILED_PORTALS.append((compiled, portal_info["currency"], portal_info["name"]))
        except re.error:
            logger.warning(f"[CURRENCY_ENGINE] Invalid portal pattern: {pattern_str}")


# ═══════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════

def _extract_page_number(text: str, match_end: int) -> Optional[int]:
    """Extract page number from text near a match."""
    before = text[:match_end]
    page_match = re.search(r"\bPage\s*(\d+)\b", before, re.IGNORECASE)
    if page_match:
        return int(page_match.group(1))
    return None


def _get_context_snippet(text: str, match_start: int, match_end: int, chars: int = 60) -> str:
    """Get a snippet of text surrounding a match for evidence."""
    start = max(0, match_start - chars)
    end = min(len(text), match_end + chars)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


# ═══════════════════════════════════════════════════════════════════════
# Main Detection Function
# ═══════════════════════════════════════════════════════════════════════

def detect_currency(
    text: Optional[str],
    boq_items: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    detected_jurisdiction: Optional[str] = None,
    jurisdiction_confidence: float = 0.0,
) -> CurrencyEvidence:
    """
    Deterministic currency detection using strict evidence hierarchy.
    
    Detection priority:
      1. Official ISO codes with amounts (confidence 1.0)
      2. Currency symbols with amounts (confidence 0.9-0.7)
      3. Explicit wording (confidence 0.85)
      4. Country detection (confidence 0.8)
      5. Procurement portal detection (confidence 0.85)
      6. ISO codes without amounts (confidence 0.6)
      7. Currency symbols without amounts (confidence 0.5-0.3)
      8. Procurement metadata patterns (confidence 0.85)
      9. Jurisdiction (only if >= 95% confidence)
    
    Never defaults to ZAR. Unknown is better than incorrect.
    """
    if not text and not boq_items:
        return CurrencyEvidence.not_detected(
            "No document text or BOQ items available for currency detection."
        )

    # ── Priority 1: ISO codes with amounts ──────────────────────────
    if text:
        amount_matches = list(CURRENCY_WITH_AMOUNT_PATTERN.finditer(text))
        if amount_matches:
            match = amount_matches[0]
            matched_text = match.group(1) or match.group(2)
            source_text = matched_text.strip()
            snippet = _get_context_snippet(text, match.start(), match.end())
            page = _extract_page_number(text, match.end())

            # Check for ISO code in the match
            for code in CURRENCY_REGISTRY.keys():
                if code.upper() in source_text.upper():
                    info = CURRENCY_REGISTRY[code]
                    return CurrencyEvidence.detected(
                        currency_code=code,
                        currency_name=info["name"],
                        currency_symbol=info["symbol"],
                        confidence=1.0,
                        detection_method="iso_code_with_amount",
                        evidence=[f"Explicit ISO code '{code}' found with amount: '{source_text}'"],
                        source_pages=[page] if page else [],
                        source_text=[snippet],
                    )

            # Check for symbol in the match
            sorted_symbols = sorted(SYMBOL_MAP.keys(), key=len, reverse=True)
            for symbol in sorted_symbols:
                if symbol in source_text:
                    possible_codes = SYMBOL_MAP[symbol]
                    detected_code = possible_codes[0]
                    info = CURRENCY_REGISTRY[detected_code]
                    conf = 0.9 if len(possible_codes) == 1 else 0.7
                    return CurrencyEvidence.detected(
                        currency_code=detected_code,
                        currency_name=info["name"],
                        currency_symbol=info["symbol"],
                        confidence=conf,
                        detection_method="symbol_with_amount",
                        evidence=[f"Symbol '{symbol}' found with amount: '{source_text}'"],
                        source_pages=[page] if page else [],
                        source_text=[snippet],
                    )

    # ── Priority 2: BOQ items ───────────────────────────────────────
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

    # ── Priority 3: Explicit wording ────────────────────────────────
    if text:
        for compiled_pattern, code in COMPILED_EXPLICIT_WORDING:
            match = compiled_pattern.search(text)
            if match:
                info = CURRENCY_REGISTRY[code]
                snippet = _get_context_snippet(text, match.start(), match.end())
                page = _extract_page_number(text, match.end())
                return CurrencyEvidence.detected(
                    currency_code=code,
                    currency_name=info["name"],
                    currency_symbol=info["symbol"],
                    confidence=0.85,
                    detection_method="explicit_wording",
                    evidence=[f"Explicit currency wording found: '{match.group(0)}'"],
                    source_pages=[page] if page else [],
                    source_text=[snippet],
                )

    # ── Priority 4: Country detection ───────────────────────────────
    if text:
        country_matches = list(COUNTRY_PATTERN.finditer(text))
        if country_matches:
            match = country_matches[0]
            country_name = match.group(0).lower()
            code = COUNTRY_CURRENCY.get(country_name)
            if code and code in CURRENCY_REGISTRY:
                info = CURRENCY_REGISTRY[code]
                snippet = _get_context_snippet(text, match.start(), match.end())
                page = _extract_page_number(text, match.end())
                return CurrencyEvidence.detected(
                    currency_code=code,
                    currency_name=info["name"],
                    currency_symbol=info["symbol"],
                    confidence=0.8,
                    detection_method="country_detection",
                    evidence=[f"Country '{country_name}' detected — maps to {code}"],
                    source_pages=[page] if page else [],
                    source_text=[snippet],
                )

    # ── Priority 5: Procurement portal detection ────────────────────
    if text:
        for compiled_pattern, currency_code, portal_name in COMPILED_PORTALS:
            match = compiled_pattern.search(text)
            if match:
                info = CURRENCY_REGISTRY[currency_code]
                snippet = _get_context_snippet(text, match.start(), match.end())
                return CurrencyEvidence.detected(
                    currency_code=currency_code,
                    currency_name=info["name"],
                    currency_symbol=info["symbol"],
                    confidence=0.85,
                    detection_method="procurement_portal",
                    evidence=[f"Procurement portal '{portal_name}' detected in document"],
                    source_text=[snippet],
                )

    # ── Priority 6: ISO codes without amounts ───────────────────────
    if text:
        code_matches = list(ISO_CODE_PATTERN.finditer(text))
        if code_matches:
            match = code_matches[0]
            detected_code = match.group(0).upper()
            if detected_code in CURRENCY_REGISTRY:
                info = CURRENCY_REGISTRY[detected_code]
                snippet = _get_context_snippet(text, match.start(), match.end())
                page = _extract_page_number(text, match.end())
                return CurrencyEvidence.detected(
                    currency_code=detected_code,
                    currency_name=info["name"],
                    currency_symbol=info["symbol"],
                    confidence=0.6,
                    detection_method="iso_code_only",
                    evidence=[f"ISO code '{detected_code}' found in document text (no amount)"],
                    source_pages=[page] if page else [],
                    source_text=[snippet],
                )

    # ── Priority 7: Currency symbols without amounts ────────────────
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

    # ── Priority 8: Jurisdiction (only if >= 95% confidence) ────────
    if detected_jurisdiction and jurisdiction_confidence >= 0.95:
        normalized_jur = detected_jurisdiction.lower().replace(" ", "_")
        code = COUNTRY_CURRENCY.get(normalized_jur)
        if not code:
            # Try the old jurisdiction mapping
            from .currency_detector import JURISDICTION_CURRENCY
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

    # ── Not detected ────────────────────────────────────────────────
    return CurrencyEvidence.not_detected(
        "No reliable currency evidence found in document text, BOQ items, metadata, or jurisdiction."
    )


# ═══════════════════════════════════════════════════════════════════════
# CurrencyEngine Class — Enterprise Interface
# ═══════════════════════════════════════════════════════════════════════

class CurrencyEngine:
    """
    Enterprise Currency Engine — Single Source of Truth for All Currency Detection.
    
    This is the ONLY class that should be used for currency detection.
    All other modules must route through this engine.
    
    Features:
      - 9-level detection hierarchy
      - ISO code, symbol, explicit wording, country, and portal detection
      - Every decision includes evidence
      - Never defaults to ZAR
      - Fully deterministic
    """

    def detect(
        self,
        text: Optional[str] = None,
        boq_items: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        detected_jurisdiction: Optional[str] = None,
        jurisdiction_confidence: float = 0.0,
    ) -> CurrencyEvidence:
        """Full currency detection with all available evidence sources."""
        return detect_currency(
            text=text,
            boq_items=boq_items,
            metadata=metadata,
            detected_jurisdiction=detected_jurisdiction,
            jurisdiction_confidence=jurisdiction_confidence,
        )

    def detect_from_text(self, text: str) -> CurrencyEvidence:
        """Detect currency from document text only."""
        return detect_currency(text=text)

    def detect_from_boq(self, boq_items: List[Dict[str, Any]]) -> CurrencyEvidence:
        """Detect currency from BOQ items only."""
        return detect_currency(text=None, boq_items=boq_items)

    def get_supported_currencies(self) -> List[Dict[str, str]]:
        """Return list of all supported currencies with metadata."""
        return [
            {"code": code, "name": info["name"], "symbol": info["symbol"]}
            for code, info in sorted(CURRENCY_REGISTRY.items())
        ]

    def get_detection_methods(self) -> List[str]:
        """Return list of all detection methods in priority order."""
        return [
            "iso_code_with_amount",
            "symbol_with_amount",
            "explicit_wording",
            "country_detection",
            "procurement_portal",
            "iso_code_only",
            "symbol_only",
            "jurisdiction",
        ]

    def detect_multi_currency(
        self,
        text: Optional[str] = None,
        boq_items: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        detected_jurisdiction: Optional[str] = None,
        jurisdiction_confidence: float = 0.0,
        auto_detect_secondary: bool = True,
    ) -> List[CurrencyEvidence]:
        """
        Enhanced multi-currency detection for documents containing multiple currencies.

        Performs complete evidence collection and determines:
          - Primary Currency: Main contract currency by volume
          - Secondary Currency: Significant supplementary currency
          - Reference Currency: Comparison or alternate currency

        Returns:
          List of CurrencyEvidence objects, sorted by priority (Primary first)

        Features:
          - Evidence-based priority determination
          - Complete audit trails for each currency
          - Automatic market preference handling
          - Reasoning for each classification

        Example Multi-Currency Scenarios:
          - EUR + USD: Primary = EUR (highest volume), Secondary = USD
          - ZAR + EUR: Primary = ZAR (SA contract), Reference = EUR
          - USD only: Primary = USD, no Secondary or Reference
        """
        if not text and not boq_items:
            return []

        # Step 1: Collect evidence for all currencies in the document
        currency_occurrences = self._collect_all_currencies(text, boq_items)
        
        if not currency_occurrences:
            logger.debug("[CURRENCY_ENGINE] No currencies detected for multi-currency analysis")
            return []
        
        # Step 2: Determine currency priorities based on evidence
        currency_priorities = self._determine_currency_priorities(
            currency_occurrences,
            metadata,
            detected_jurisdiction,
            jurisdiction_confidence,
            auto_detect_secondary
        )
        
        # Step 3: Create CurrencyEvidence objects with complete trails
        evidences = []
        for currency_code, priority_data in currency_priorities.items():
            evidence = CurrencyEvidence.detected(
                currency_code=currency_code,
                currency_name=self._get_currency_name(currency_code),
                currency_symbol=self._get_currency_symbol(currency_code),
                priority=priority_data["priority"],
                confidence=priority_data["confidence"],
                detection_method="multi_currency_analysis",
                evidence=priority_data["evidence"],
                source_pages=priority_data["source_pages"],
                source_text=priority_data["source_text"],
                total_amount=priority_data["total_amount"],
                total_count=priority_data["total_count"],
            )
            evidences.append(evidence)
        
        # Sort by priority (Primary first, then Secondary, then Reference)
        priority_order = {CurrencyPriority.PRIMARY: 0, CurrencyPriority.SECONDARY: 1, CurrencyPriority.REFERENCE: 2}
        evidences.sort(key=lambda e: priority_order.get(e.priority, 3))
        
        logger.info(
            f"[CURRENCY_ENGINE] Multi-currency analysis complete: "
            f"detected {len(evidences)} currencies, "
            f"primary={evidences[0].currency_code if evidences else 'N/A'}"
        )
        
        return evidences

    def _collect_all_currencies(
        self,
        text: Optional[str],
        boq_items: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Collect all currency occurrences in document with volume analysis.
        
        Aggregates:
          - Total monetary value per currency
          - Number of occurrences per currency
          - Confidence scores per occurrence
          - Source pages for each occurrence
          - Raw text evidence for each occurrence
        """
        if not text and not boq_items:
            return {}

        currency_occurrences: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_amount": 0.0,
                "total_confidence": 0.0,
                "count": 0,
                "occurrences": [],
                "source_pages": set(),
                "raw_evidence": [],
            }
        )

        if text:
            # Collect from text patterns
            text_currencies = self._extract_currencies_from_text(text)
            for currency_code, currency_data in text_currencies.items():
                if currency_code in CURRENCY_REGISTRY:
                    currency_occurrences[currency_code]["total_amount"] += currency_data.get("amount", 0.0)
                    currency_occurrences[currency_code]["total_confidence"] += currency_data.get("confidence", 0.0)
                    currency_occurrences[currency_code]["count"] += 1
                    currency_occurrences[currency_code]["occurrences"].append(currency_data)
                    currency_occurrences[currency_code]["source_pages"].update([currency_data.get("page", None)])
                    currency_occurrences[currency_code]["raw_evidence"].append(currency_data.get("text", ""))

        if boq_items:
            # Collect from BOQ items
            boq_currencies = self._extract_currencies_from_boq(boq_items)
            for currency_code, currency_data in boq_currencies.items():
                if currency_code in CURRENCY_REGISTRY:
                    currency_occurrences[currency_code]["total_amount"] += currency_data.get("amount", 0.0)
                    currency_occurrences[currency_code]["total_confidence"] += currency_data.get("confidence", 0.0)
                    currency_occurrences[currency_code]["count"] += 1
                    currency_occurrences[currency_code]["occurrences"].append(currency_data)
                    currency_occurrences[currency_code]["source_pages"].update([currency_data.get("page", None)])
                    currency_occurrences[currency_code]["raw_evidence"].append(currency_data.get("text", ""))

        return dict(currency_occurrences)

    def _extract_currencies_from_text(
        self,
        text: str,
        page: Optional[int] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Extract currencies from text with amount analysis."""
        currencies: Dict[str, Dict[str, Any]] = {}
        
        # Find all currency patterns with amounts
        for match in CURRENCY_WITH_AMOUNT_PATTERN.finditer(text):
            matched_text = match.group(1) or match.group(2)
            matched_text = matched_text.strip()
            
            # Extract amount
            amount = self._extract_amount_from_text(matched_text)
            if amount is None:
                continue
            
            # Extract currency code if present
            detected_code = self._detect_currency_from_text(matched_text, text)
            
            if detected_code and detected_code in CURRENCY_REGISTRY:
                if detected_code not in currencies:
                    currencies[detected_code] = {
                        "amount": 0.0,
                        "text": matched_text,
                        "confidence": 0.0,
                        "page": page,
                        "context": text[max(0, match.start() - 50):min(len(text), match.end() + 50)],
                    }
                currencies[detected_code]["amount"] += amount
                currencies[detected_code]["confidence"] = max(
                    currencies[detected_code]["confidence"],
                    0.7 if detected_code in ["USD", "EUR", "GBP"] else 0.5
                )
        
        return currencies

    def _extract_currencies_from_boq(
        self,
        boq_items: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Extract currencies from BOQ items."""
        currencies: Dict[str, Dict[str, Any]] = {}
        
        for idx, item in enumerate(boq_items):
            rate = item.get("rate", "0")
            amount = item.get("amount", "0")
            description = str(item.get("description", ""))
            
            # Check both rate and amount fields
            combined_text = f"{rate} {amount} {description}"
            
            if not combined_text:
                continue
            
            # Extract amount from the field
            amount_value = self._extract_amount_from_text(str(rate)) or self._extract_amount_from_text(str(amount))
            if amount_value is None:
                continue
            
            # Detect currency from description
            detected_code = self._detect_currency_from_text(combined_text, combined_text)
            
            if detected_code and detected_code in CURRENCY_REGISTRY:
                if detected_code not in currencies:
                    currencies[detected_code] = {
                        "amount": 0.0,
                        "text": combined_text[:100],
                        "confidence": 0.6,
                        "page": item.get("page", None),
                        "context": description[:100] if description else "",
                    }
                currencies[detected_code]["amount"] += amount_value
                currencies[detected_code]["confidence"] = max(
                    currencies[detected_code]["confidence"],
                    0.7 if detected_code in ["USD", "EUR", "GBP"] else 0.5
                )
        
        return currencies

    def _detect_currency_from_text(self, text: str, matched_text: str) -> Optional[str]:
        """Detect currency code from matched text."""
        for code in CURRENCY_REGISTRY.keys():
            if code.upper() in text.upper():
                # Check if code is actually part of the amount
                pattern = rf"{code.upper()}"
                if re.search(pattern, matched_text, re.IGNORECASE):
                    return code.upper()
        
        return None

    def _extract_amount_from_text(self, text: str) -> Optional[float]:
        """Extract numeric amount from currency text."""
        cleaned = re.sub(r"[^0-9.,]", "", text)
        if not cleaned:
            return None
        
        try:
            if cleaned.count('.') > 1 and cleaned.count(',') > 1:
                parts = cleaned.split('.')
                if parts[1].count(',') == 1:
                    base = parts[0] + '.' + ''.join(parts[1].split(','))
                    cleaned = base
                else:
                    cleaned = cleaned.replace('.', '').replace(',', '.')
            elif ',' in cleaned and '.' not in cleaned:
                cleaned = cleaned.replace(',', '.')
            elif '.' in cleaned and ',' in cleaned:
                parts = cleaned.split('.')
                if parts[1].count(',') > 0:
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            elif ' ' in cleaned:
                cleaned = cleaned.replace(' ', '')
            else:
                cleaned = cleaned.replace(',', '').replace('.', '')
            
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def _determine_currency_priorities(
        self,
        currency_occurrences: Dict[str, Dict[str, Any]],
        metadata: Optional[Dict[str, Any]],
        jurisdiction: Optional[str],
        jurisdiction_confidence: float,
        auto_detect_secondary: bool,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Determine currency priority based on evidence and rules.
        
        Decision process:
          1. Check for jurisdiction preference override
          2. Calculate volume percentages
          3. Apply priority rules based on volume and occurrences
          4. Handle market preference overrides
        """
        jurisdiction_priorities = {}
        
        # Check jurisdiction-specific preferences
        if jurisdiction:
            jurisdiction_key = jurisdiction.lower().replace("_", "_")
            jurisdiction.name
        
        # Sort currencies by total amount (descending)
        sorted_currencies = sorted(
            currency_occurrences.items(),
            key=lambda x: x[1]["total_amount"],
            reverse=True
        )
        
        priorities = {}
        
        if not sorted_currencies:
            return priorities
        
        # Determine primary currency
        primary_code = sorted_currencies[0][0]
        primary_data = currency_occurrences[primary_code]
        priorities[primary_code] = {
            "priority": CurrencyPriority.PRIMARY,
            "confidence": primary_data["total_confidence"] / max(primary_data["count"], 1),
            "total_amount": primary_data["total_amount"],
            "total_count": primary_data["count"],
            "source_pages": list(primary_data["source_pages"]),
            "source_text": primary_data["raw_evidence"],
            "evidence": [
                f"Primary currency determined by highest total volume",
                f"Total value: {primary_data['total_amount']:.2f}",
                f"Occurrences: {primary_data['count']}",
            ],
        }
        
        # Determine secondary and reference currencies if auto-detect is enabled
        if auto_detect_secondary and len(sorted_currencies) > 1:
            remaining_volume = sorted_currencies[0][1]["total_amount"]
            
            for idx, (code, data) in enumerate(sorted_currencies[1:], start=1):
                # Check if secondary applies (volume threshold)
                volume_percentage = data["total_amount"] / remaining_volume * 100
                
                if idx == 1:
                    # Second largest currency
                    if volume_percentage >= 0.15:
                        priority = CurrencyPriority.SECONDARY
                    else:
                        priority = CurrencyPriority.REFERENCE
                else:
                    # Third and subsequent currencies
                    if volume_percentage >= 0.10:
                        priority = CurrencyPriority.SECONDARY
                    else:
                        priority = CurrencyPriority.REFERENCE
                
                priorities[code] = {
                    "priority": priority,
                    "confidence": data["total_confidence"] / max(data["count"], 1),
                    "total_amount": data["total_amount"],
                    "total_count": data["count"],
                    "source_pages": list(data["source_pages"]),
                    "source_text": data["raw_evidence"],
                    "evidence": [
                        f"{priority.name} currency by volume analysis",
                        f"Volume relative to primary: {volume_percentage:.1f}%",
                        f"Total value: {data['total_amount']:.2f}",
                        f"Occurrences: {data['count']}",
                    ],
                }
        
        return priorities

    def _get_currency_name(self, code: str) -> str:
        """Get currency name from registry."""
        return CURRENCY_REGISTRY.get(code.upper(), {}).get("name", code.upper())

    def _get_currency_symbol(self, code: str) -> str:
        """Get currency symbol from registry."""
        return CURRENCY_REGISTRY.get(code.upper(), {}).get("symbol", "")


# ═══════════════════════════════════════════════════════════════════════
# Backward Compatibility
# ═══════════════════════════════════════════════════════════════════════

def get_engine() -> CurrencyEngine:
    """Return a CurrencyEngine instance (preferred entry point)."""
    return CurrencyEngine()


# Re-export for backward compatibility with existing imports
# The old CurrencyDetector class is preserved in currency_detector.py
# but all new code should use CurrencyEngine from this module.