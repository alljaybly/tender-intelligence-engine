"""
CurrencyEvidence schema — deterministic currency detection result.

Every currency detection produces a CurrencyEvidence object.
Currency is NEVER defaulted. Unknown is better than incorrect.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class CurrencyEvidence:
    """
    Complete evidence trail for a currency detection decision.

    Every field documents WHY a currency was chosen (or not chosen).
    """
    currency_code: Optional[str] = None       # ISO 4217 code (e.g. "ZAR", "USD")
    currency_name: Optional[str] = None       # Human-readable name (e.g. "South African Rand")
    currency_symbol: Optional[str] = None     # Symbol (e.g. "R", "$", "€")
    confidence: float = 0.0                   # 0.0 (none) to 1.0 (certain)
    detection_method: str = "none"            # "iso_code", "symbol", "procurement_metadata", "jurisdiction", "none"
    evidence: List[str] = field(default_factory=list)  # Human-readable evidence strings
    source_pages: List[int] = field(default_factory=list)  # Page numbers where evidence found
    source_text: List[str] = field(default_factory=list)  # Text snippets containing evidence
    reason: str = "No reliable currency evidence found."  # Plain English explanation
    is_detected: bool = False                 # True only if confidence >= threshold

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON storage and API responses."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CurrencyEvidence":
        """Deserialize from dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def not_detected(cls, reason: str = "No reliable currency evidence found.") -> "CurrencyEvidence":
        """Return a 'not detected' evidence object."""
        return cls(reason=reason, detection_method="none")

    @classmethod
    def detected(
        cls,
        currency_code: str,
        currency_name: str,
        currency_symbol: str,
        confidence: float,
        detection_method: str,
        evidence: List[str],
        source_pages: List[int] = None,
        source_text: List[str] = None,
    ) -> "CurrencyEvidence":
        """Return a 'detected' evidence object."""
        return cls(
            currency_code=currency_code,
            currency_name=currency_name,
            currency_symbol=currency_symbol,
            confidence=confidence,
            detection_method=detection_method,
            evidence=evidence,
            source_pages=source_pages or [],
            source_text=source_text or [],
            reason=f"Currency detected: {currency_code} ({currency_name}) via {detection_method}",
            is_detected=True,
        )

    def format_display(self) -> str:
        """Return a human-readable display string."""
        if not self.is_detected:
            return "Currency: Unknown"
        symbol_part = f" ({self.currency_symbol})" if self.currency_symbol else ""
        return f"{self.currency_code}{symbol_part} - {self.currency_name}"