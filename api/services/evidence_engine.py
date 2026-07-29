"""
Evidence Engine - Deterministic Evidence Collection for All Document Expositions.

This engine provides a single source of truth for evidence collection across:
- Currency detection
- Numeric entity classification
- Tender value extraction
- Financial terminology extraction
- Document section attribution

Every extracted value must contain complete evidence trails.

CRITICAL RULES:
  - Never infer
  - Never fabricate
  - Never estimate
  - Never "best guess"
  - Everything must originate from evidence
  - Evidence must include: source category, page number, sentence, source text

USAGE EXAMPLE:
  evidence_engine = EvidenceEngine()
  result = evidence_engine.extract_currency_with_evidence(text, page_number, section)

HOW IT WORKS:
  1. Extract candidate value
  2. Always capture surrounding context (sentence)
  3. Always capture page number where found
  4. Always capture the exact source text
  5. Always classify detection method and confidence
  6. Store record centrally for cross-reporting

PERFORMANCE:
  - Indexed evidence storage for fast lookup
  - Memory-efficient record keeping
  - Optional persistence layer (database)
"""

from __future__ import annotations
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import IntEnum
from collections import defaultdict


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Evidence Source Categories
# ═══════════════════════════════════════════════════════════════════════

class EvidenceSourceCategory(IntEnum):
    """Document section where evidence was found."""
    TITLE = 1
    CONTRACT_VALUE = 2
    AWARD_VALUE = 3
    BOQ = 4
    PRICING_SCHEDULE = 5
    PAYMENT_CLAUSE = 6
    TABLE = 7
    BODY_TEXT = 8


# ═══════════════════════════════════════════════════════════════════════
# Numeric Entity Types
# ═══════════════════════════════════════════════════════════════════════

class NumericEntityType(IntEnum):
    """Canonical entity types for numeric classification."""
    NO_TYPE = 0
    MONEY = 1
    TENDER_VALUE = 2
    BUDGET = 3
    AWARD_VALUE = 4
    BOQ_QUANTITY = 5
    BOQ_RATE = 6
    BOQ_AMOUNT = 7
    VAT_PERCENT = 8
    RETENTION_PERCENT = 9
    PERFORMANCE_BOND_PERCENT = 10
    INSURANCE_VALUE = 11
    DURATION = 12
    CLOSING_DATE = 13
    CONTRACT_NUMBER = 14
    COMPANY_REGISTRATION = 15
    TELEPHONE = 16
    POSTAL_CODE = 17
    REFERENCE_NUMBER = 18
    WORKFORCE = 19
    PAGE_NUMBER = 20
    WEIGHT = 21
    LENGTH = 22
    AREA = 23
    VOLUME = 24
    DATE = 25
    TIME = 26
    PERCENTAGE = 27
    PERCENT_COMPLETE = 28
    PERFORMANCE_SCORE = 29


# ═══════════════════════════════════════════════════════════════════════
# Currency Priority Levels
# ═══════════════════════════════════════════════════════════════════════

class CurrencyPriority(IntEnum):
    """Priority levels for multi-currency documents."""
    PRIMARY = 1
    SECONDARY = 2
    REFERENCE = 3


# ═══════════════════════════════════════════════════════════════════════
# Evidence Record Dataclass
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class EvidenceRecord:
    """
    Complete evidence trail for a single field extraction.

    This is the canonical structure for ALL evidence collection.
    Every extracted value creates one or more EvidenceRecord instances.
    """
    field_type: str = ""  # e.g., "project_value", "contract_value"
    raw_value: str = ""   # The exact text found in the document
    
    # Core evidence
    value: Any = None     # Parsed value (e.g., 5000000.00)
    category: str = ""    # NumericEntityType or "currency"
    
    # Location evidence
    source_category: EvidenceSourceCategory = EvidenceSourceCategory.BODY_TEXT
    page_number: Optional[int] = None
    sentence: Optional[str] = None
    
    # Detection evidence
    detection_method: str = "unknown"  # e.g., "regex_pattern", "context_analysis"
    confidence: float = 0.0            # 0.0 to 1.0
    
    # Source text evidence
    source_text: List[str] = field(default_factory=list)  # Original text snippets
    context: List[str] = field(default_factory=list)      # Surrounding context
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    detection_stage: str = "extraction"  # Which stage of processing this evidence came from
    severity: str = "informational"      # Only applies to errors/warnings
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage and API responses."""
        result = asdict(self)
        result['source_category'] = self.source_category.value if self.source_category else None
        result['category'] = self.category.value if isinstance(self.category, NumericEntityType) else self.category
        result['timestamp'] = self.timestamp.isoformat()
        return result
    

# ═══════════════════════════════════════════════════════════════════════
# Currency Evidence with Multi-Currency Support
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class CurrencyEvidence:
    """
    Enhanced currency evidence with multi-currency support.

    Every currency found is classified as:
      - Primary Currency (main contract currency)
      - Secondary Currency (sub-contract or supplementary)
      - Reference Currency (benchmark or alternate)

    LEARNED RULE:
      - Primary currency = currency with highest total amount value
      - Secondary = currency with substantial but lower amounts
      - Reference = currency mentioned for comparison or billing
    """
    currency_code: Optional[str] = None
    currency_name: Optional[str] = None
    currency_symbol: Optional[str] = None
    priority: CurrencyPriority = CurrencyPriority.PRIMARY
    confidence: float = 0.0
    
    # Evidence trail
    detection_method: str = "unknown"
    evidence: List[str] = field(default_factory=list)
    source_pages: List[int] = field(default_factory=list)
    source_text: List[str] = field(default_factory=list)
    sentence: Optional[str] = None
    
    # Aggregate data for primary currency
    total_amount: float = 0.0
    total_count: int = 0
    
    # Currency metadata
    exchange_rate_applied: Optional[float] = None
    converted_amount: Optional[float] = None
    
    # Technical
    is_detected: bool = False
    reason: str = "No currency evidence found"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = asdict(self)
        result['priority'] = self.priority.value if self.priority else None
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    @classmethod
    def not_detected(cls, reason: str = "No currency evidence found.") -> "CurrencyEvidence":
        """Return a 'not detected' currency evidence object."""
        return cls(reason=reason, detection_method="none", is_detected=False)
    
    @classmethod
    def detected(
        cls,
        currency_code: str,
        currency_name: str,
        currency_symbol: str,
        priority: CurrencyPriority,
        confidence: float,
        detection_method: str,
        evidence: List[str],
        source_pages: Optional[List[int]] = None,
        source_text: Optional[List[str]] = None,
        sentence: Optional[str] = None,
        total_amount: float = 0.0,
        total_count: int = 0,
    ) -> "CurrencyEvidence":
        """Return a 'detected' currency evidence object."""
        return cls(
            currency_code=currency_code,
            currency_name=currency_name,
            currency_symbol=currency_symbol,
            priority=priority,
            confidence=confidence,
            detection_method=detection_method,
            evidence=evidence,
            source_pages=source_pages or [],
            source_text=source_text or [],
            sentence=sentence,
            total_amount=total_amount,
            total_count=total_count,
            reason=f"{currency_code} ({currency_name}) priority={priority.name} confidence={confidence:.0%}",
            is_detected=True,
        )


# ═══════════════════════════════════════════════════════════════════════
# Numeric Entity Evidence with Classification
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class NumericEntityEvidence:
    """
    Enhanced numeric entity evidence with classification and evidence tracking.
    
    Classifies each numeric entity into one of:
      - Monetary values (Money, Tender Value, Budget, Award Value, etc.)
      - Percentages (VAT %, Retention %, Performance Bond %, etc.)
      - Quantities (BOQ quantities, lengths, weights, areas, volumes)
      - Dates (Closing Date, Contract Date, etc.)
      - Identifiers (Telephone, Postal Code, Reference Number, etc.)
    
    Contains complete verification chain for each extracted value.
    """
    
    # The extracted value
    value: float = 0.0
    raw_value: str = ""
    entity_type: NumericEntityType = NumericEntityType.NO_TYPE
    
    # Evidence
    source_category: EvidenceSourceCategory = EvidenceSourceCategory.BODY_TEXT
    page_number: Optional[int] = None
    sentence: Optional[str] = None
    detection_method: str = "unknown"
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    source_text: List[str] = field(default_factory=list)
    context: List[str] = field(default_factory=list)
    
    # Technical
    is_accepted: bool = False
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    validation_status: str = "pending"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = asdict(self)
        result['entity_type'] = self.entity_type.value if self.entity_type else None
        result['source_category'] = self.source_category.value if self.source_category else None
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    @classmethod
    def accepted(
        cls,
        value: float,
        raw_value: str,
        entity_type: NumericEntityType,
        confidence: float,
        evidence: List[str],
        source_category: EvidenceSourceCategory = EvidenceSourceCategory.BODY_TEXT,
        page_number: Optional[int] = None,
        sentence: Optional[str] = None,
        detection_method: str = "unknown",
        source_text: List[str] = frozenset(),
        context: List[str] = frozenset(),
    ) -> "NumericEntityEvidence":
        """Create an accepted numeric entity evidence record."""
        return cls(
            value=value,
            raw_value=raw_value,
            entity_type=entity_type,
            confidence=confidence,
            evidence=evidence,
            source_category=source_category,
            page_number=page_number,
            sentence=sentence,
            detection_method=detection_method,
            source_text=list(source_text),
            context=list(context),
            is_accepted=True,
            reason=f"Accepted as {entity_type.name} with {confidence:.0%} confidence",
            validation_status="verified",
        )
    
    @classmethod
    def rejected(
        cls,
        raw_value: str,
        entity_type: NumericEntityType,
        reason: str,
        evidence: List[str],
        source_category: EvidenceSourceCategory = EvidenceSourceCategory.BODY_TEXT,
        page_number: Optional[int] = None,
        sentence: Optional[str] = None,
    ) -> "NumericEntityEvidence":
        """Create a rejected numeric entity evidence record."""
        return cls(
            value=0.0,
            raw_value=raw_value,
            entity_type=entity_type,
            confidence=0.0,
            evidence=evidence,
            source_category=source_category,
            page_number=page_number,
            sentence=sentence,
            is_accepted=False,
            reason=reason,
            validation_status="rejected",
        )


# ═══════════════════════════════════════════════════════════════════════
# Evidence Engine Class
# ═══════════════════════════════════════════════════════════════════════

class EvidenceEngine:
    """
    Centralized engine for collecting and managing evidence for all document extractions.
    
    Provides deterministic evidence collection across the entire pipeline
    with complete audit trails for:
      - Currency detection with multi-currency support
      - Numeric entity classification with financial categories
      - Financial terminology extraction
      - Document section attribution
    
    Key Features:
      - Automatic evidence indexing by field type
      - Cross-referencing capabilities between currency and numeric entities
      - Centralized report generation
      - Comprehensive audit trails
      - No inference, no fabrication, no estimation
      
    Aligned With:
      - HOESP → NO fabricated data
      - Confidence and evidence requirements
      - Document-centric processing
    """
    
    def __init__(self):
        """Initialize the evidence engine with empty evidence stores."""
        self._evidence_records: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._currency_evidence: List[CurrencyEvidence] = []
        self._numeric_entity_evidence: List[NumericEntityEvidence] = []
    
    def record_currency(
        self,
        currency_evidence: CurrencyEvidence,
        field_type: str = "currency",
        page_number: Optional[int] = None,
        source_category: EvidenceSourceCategory = EvidenceSourceCategory.BODY_TEXT,
        detection_stage: str = "extraction",
    ) -> None:
        """
        Record currency evidence with complete audit trail.
        
        Args:
            currency_evidence: The currency evidence object
            field_type: Type of field (e.g., "project_value")
            page_number: Page number where found
            source_category: Document section where found
            detection_stage: Which processing stage (extraction, validation, calculation)
        """
        self._currency_evidence.append(currency_evidence)
        
        # Also record in general evidence
        record = {
            "field_type": field_type,
            "value": currency_evidence.currency_code,
            "category": "currency",
            "source_category": source_category.value if source_category else None,
            "page_number": page_number,
            "detection_method": currency_evidence.detection_method,
            "confidence": currency_evidence.confidence,
            "evidence": currency_evidence.evidence,
            "source_text": currency_evidence.source_text,
            "detection_stage": detection_stage,
            "timestamp": currency_evidence.timestamp.isoformat(),
        }
        self._evidence_records[field_type].append(record)
        
        logger.debug(f"[EVIDENCE] Recorded currency: {currency_evidence.currency_code} {currency_evidence.confidence:.0%} confidence")
    
    def record_numeric_entity(
        self,
        entity_evidence: NumericEntityEvidence,
        field_type: str = "numeric_entity",
        page_number: Optional[int] = None,
        source_category: EvidenceSourceCategory = EvidenceSourceCategory.BODY_TEXT,
        detection_stage: str = "extraction",
    ) -> None:
        """
        Record numeric entity evidence with complete audit trail.
        
        Args:
            entity_evidence: The numeric entity evidence object
            field_type: Type of field (e.g., "tender_value", "vat_percentage")
            page_number: Page number where found
            source_category: Document section where found
            detection_stage: Which processing stage
        """
        self._numeric_entity_evidence.append(entity_evidence)
        
        # Also record in general evidence
        record = {
            "field_type": field_type,
            "value": entity_evidence.value,
            "category": entity_evidence.entity_type.value if entity_evidence.entity_type else None,
            "raw_value": entity_evidence.raw_value,
            "source_category": source_category.value if source_category else None,
            "page_number": page_number,
            "detection_method": entity_evidence.detection_method,
            "confidence": entity_evidence.confidence,
            "evidence": entity_evidence.evidence,
            "source_text": entity_evidence.source_text,
            "context": entity_evidence.context,
            "validation_status": entity_evidence.validation_status,
            "detection_stage": detection_stage,
            "timestamp": entity_evidence.timestamp.isoformat(),
        }
        self._evidence_records[field_type].append(record)
        
        logger.debug(
            f"[EVIDENCE] Recorded numeric entity: {entity_evidence.entity_type.name if entity_evidence.entity_type else 'unknown'} "
            f"{entity_evidence.value} {entity_evidence.confidence:.0%} confidence"
        )
    
    def get_currency_evidence(self) -> List[CurrencyEvidence]:
        """Get all recorded currency evidence."""
        return self._currency_evidence
    
    def get_numeric_entity_evidence(self) -> List[NumericEntityEvidence]:
        """Get all recorded numeric entity evidence."""
        return self._numeric_entity_evidence
    
    def get_field_evidence(self, field_type: str) -> List[Dict[str, Any]]:
        """Get evidence records for a specific field type."""
        return self._evidence_records.get(field_type, [])
    
    def get_all_evidence(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all recorded evidence."""
        return dict(self._evidence_records)
    
    def generate_evidence_summary(self) -> Dict[str, Any]:
        """
        Generate a comprehensive evidence summary for reports.
        
        Returns:
            Dictionary with:
              - total_records: Total evidence records
              - currency_records: Number of currency detections
              - numeric_records: Number of numeric entities classified
              - verification_rate: % of accepted numeric entities
              - confidence_summary: Confidence distribution
              - source_distribution: Evidence sources by category
              - stage_distribution: Evidence sources by detection stage
        """
        summary = {
            "total_records": 0,
            "currency_records": len(self._currency_evidence),
            "numeric_records": len(self._numeric_entity_evidence),
            "verification_rate": 0.0,
            "confidence_summary": {},
            "source_distribution": {},
            "stage_distribution": {},
        }
        
        if self._numeric_entity_evidence:
            accepted = sum(1 for e in self._numeric_entity_evidence if e.is_accepted)
            summary["verification_rate"] = accepted / len(self._numeric_entity_evidence)
            
            # Confidence distribution
            for entity in self._numeric_entity_evidence:
                conf = int(entity.confidence / 0.1) * 0.1  # Round to nearest 0.1
                summary["confidence_summary"][f"{int(conf * 100)}%"] = (
                    summary["confidence_summary"].get(f"{int(conf * 100)}%", 0) + 1
                )
            
            # Source distribution
            for entity in self._numeric_entity_evidence:
                cat = entity.source_category.value if entity.source_category else None
                summary["source_distribution"][cat] = summary["source_distribution"].get(cat, 0) + 1
            
            # Stage distribution
            for entity in self._numeric_entity_evidence:
                stage = entity.detection_stage
                summary["stage_distribution"][stage] = summary["stage_distribution"].get(stage, 0) + 1
        
        summary["total_records"] = sum(len(v) for v in self._evidence_records.values())
        return summary
    
    def clear(self) -> None:
        """Clear all recorded evidence."""
        self._evidence_records.clear()
        self._currency_evidence.clear()
        self._numeric_entity_evidence.clear()


# ═══════════════════════════════════════════════════════════════════════
# Helper Functions for Evidence Collection
# ═══════════════════════════════════════════════════════════════════════

def _extract_sentence(text: str, match_start: int, match_end: int, max_length: int = 150) -> Optional[str]:
    """
    Extract a meaningful sentence containing the match.
    
    Returns the sentence (not exceeding max_length) that contains the match,
    optionally including leading context to give meaning.
    """
    start = max(0, match_start - max_length // 3)
    end = min(len(text), match_end + max_length // 2)
    
    # Find sentence boundaries
    sentence = text[start:end]
    
    # Clean up newlines and extra spaces
    sentence = re.sub(r'\s+', ' ', sentence).strip()
    
    # Ensure the actual match is preserved or represented
    if match_start >= start and match_end <= end:
        match_in_context = text[match_start:match_end]
        return f"{sentence[:len(sentence)-len(max(text[start:match_start], ''))]}...{match_in_context}...{sentence[len(text[match_end:end]):]}"
    
    return sentence[:max_length]


def _extract_page_number(text: str, match_end: int) -> Optional[int]:
    """
    Extract page number from text near a match using various patterns.
    """
    # Try standard pattern
    page_match = re.search(r'\bPage\s*(\d+)\b', text[:match_end], re.IGNORECASE)
    if page_match:
        return int(page_match.group(1))
    
    # Try .pdf with number pattern
    page_match = re.search(r'\.pdf\s*(\d+)\b', text[:match_end], re.IGNORECASE)
    if page_match:
        return int(page_match.group(1))
    
    return None


def _extract_surrounding_context(text: str, match_start: int, match_end: int, chars: int = 60) -> str:
    """
    Extract surrounding text snippet for evidence.
    
    Returns:
        Text snippet before and after the match, truncated if necessary.
    """
    start = max(0, match_start - chars)
    end = min(len(text), match_end + chars)
    
    snippet = text[start:end].strip()
    
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    return snippet


# ═══════════════════════════════════════════════════════════════════════
# Main Evidence Services
# ═══════════════════════════════════════════════════════════════════════


def collect_currency_with_evidence(
    text: Optional[str],
    detected_currencies: List[Dict[str, Any]],
    page_number: Optional[int] = None,
    source_category: EvidenceSourceCategory = EvidenceSourceCategory.BODY_TEXT,
    jurisdiction: Optional[str] = None,
    currency_registry: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[CurrencyEvidence]:
    """
    Collect currency evidence for a document with complete audit trail.
    
    Args:
        text: Document text for analysis
        detected_currencies: List of detected currency objects
        page_number: Page number where found
        source_category: Document section where evidence found
        jurisdiction: Detected jurisdiction code
        currency_registry: ISO currency registry mapping
    
    Returns:
        List of CurrencyEvidence objects with complete evidence trails
    
    ALGORITHM:
        1. For each detected currency code:
           - Find ALL occurrences with full context
           - Measure total amount for priority determination
           - Record evidence for each occurrence
           - Calculate aggregate statistics
        2. Determine primary currency:
           - Currency with highest total value
           - Or currency with highest confidence
        3. Determine secondary currency:
           - Currency with substantial but lower values
        4. Determine reference currency:
           - Currency used for comparison or billing
    """
    if not currency_registry:
        currency_registry = {
            "USD": {"symbol": "$", "name": "US Dollar"},
            "EUR": {"symbol": "€", "name": "Euro"},
            "GBP": {"symbol": "£", "name": "British Pound"},
            "ZAR": {"symbol": "R", "name": "South African Rand"},
            "DKK": {"symbol": "kr", "name": "Danish Krone"},
            "SEK": {"symbol": "kr", "name": "Swedish Krona"},
            "NOK": {"symbol": "kr", "name": "Norwegian Krone"},
            "CHF": {"symbol": "CHF", "name": "Swiss Franc"},
            "CAD": {"symbol": "C$", "name": "Canadian Dollar"},
            "AUD": {"symbol": "A$", "name": "Australian Dollar"},
            "NZD": {"symbol": "NZ$", "name": "New Zealand Dollar"},
            "JPY": {"symbol": "¥", "name": "Japanese Yen"},
        }
    
    if not text or not detected_currencies:
        return []
    
    # First, aggregate by currency code
    currency_occurrences = defaultdict(lambda: {
        "symbols": [],
        "total_amount": 0.0,
        "confidence_sum": 0.0,
        "count": 0,
        "evidence": [],
        "pages": set(),
    })
    
    # Find all matches for each currency
    for currency_match in detected_currencies:
        currency_code = currency_match.get("code", "")
        matched_text = currency_match.get("text", "")
        confidence = currency_match.get("confidence", 0.0)
        
        if currency_code and currency_code.upper() in currency_registry:
            # Calculate amount
            amount = _extract_amount(matched_text)
            if amount:
                currency_occurrences[currency_code.upper()]["total_amount"] += amount
                currency_occurrences[currency_code.upper()]["confidence_sum"] += confidence
                currency_occurrences[currency_code.upper()]["count"] += 1
                currency_occurrences[currency_code.upper()]["evidence"].append(matched_text)
                if page_number:
                    currency_occurrences[currency_code.upper()]["pages"].add(page_number)
    
    # Convert to CurrencyEvidence objects
    evidences = []
    
    # Sort by total amount (descending) for primary/secondary determination
    sorted_currencies = sorted(
        currency_occurrences.items(),
        key=lambda x: x[1]["total_amount"],
        reverse=True
    )
    
    for idx, (code, data) in enumerate(sorted_currencies):
        if not data["total_amount"]:
            continue
        
        info = currency_registry.get(code.upper(), {"name": code, "symbol": ""})
        priority = CurrencyPriority.PRIMARY
        
        # Determine priority
        if idx == 0:
            priority = CurrencyPriority.PRIMARY
        elif idx == 1:
            priority = CurrencyPriority.SECONDARY
        else:
            priority = CurrencyPriority.REFERENCE
        
        avg_confidence = data["confidence_sum"] / data["count"] if data["count"] > 0 else 0.0
        
        evidence_record = CurrencyEvidence.detected(
            currency_code=code.upper(),
            currency_name=info["name"],
            currency_symbol=info["symbol"],
            priority=priority,
            confidence=min(avg_confidence, 1.0),
            detection_method="text_pattern_analysis",
            evidence=[f"Found {data['count']} occurrence(s) of {code.upper()} with total value {data['total_amount']:.2f}"],
            source_pages=list(data["pages"]),
            source_text=data["evidence"],
            total_amount=data["total_amount"],
            total_count=data["count"],
        )
        
        evidences.append(evidence_record)
        
        logger.debug(
            f"[EVIDENCE] Collected currency {code.upper()}: "
            f"priority={priority.name}, total={data['total_amount']:.2f}, "
            f"confidence={avg_confidence:.0%}"
        )
    
    return evidences


def _extract_amount(text: str) -> Optional[float]:
    """
    Extract numeric amount from currency text string.
    
    Handles various formats: $1,234,567.89, €1,234.567,89, 1.234,56 USD, etc.
    """
    cleaned = re.sub(r"[^0-9.,]", "", text)
    
    if not cleaned:
        return None
    
    try:
        # Handle both decimal point separators
        if cleaned.count('.') > 1 and cleaned.count(',') > 1:
            # European format with both: 1.234,56
            parts = cleaned.split('.')
            if parts[1].count(',') == 1:
                # Take the digit part after the last dot
                base = parts[0] + '.' + ''.join(parts[1].split(','))
                cleaned = base
            else:
                # Standard format: 1.234,56
                cleaned = cleaned.replace('.', '').replace(',', '.')
        elif ',' in cleaned and '.' not in cleaned:
            # Could be decimal comma: 1,234.56
            cleaned = cleaned.replace(',', '.')
        elif '.' in cleaned and ',' in cleaned:
            # Mixed format, likely European
            parts = cleaned.split('.')
            if parts[1].count(',') > 0:
                # Last dot after comma separator
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # Standard: 1,234.56
                cleaned = cleaned.replace(',', '')
        elif ' ' in cleaned:
            # Remove spaces
            cleaned = cleaned.replace(' ', '')
        else:
            # Just remove everything except digits and dots
            cleaned = cleaned.replace(',', '').replace('.', '')
        
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


# Singleton instance for convenience
_evidence_engine_instance: Optional[EvidenceEngine] = None


def get_evidence_engine() -> EvidenceEngine:
    """Get the global evidence engine instance."""
    global _evidence_engine_instance
    if _evidence_engine_instance is None:
        _evidence_engine_instance = EvidenceEngine()
    return _evidence_engine_instance