"""
Evidence Schema Manager and Report Integration Support.

This module provides comprehensive support for evidence display across all reports.

EVIDENCE DISPLAY REQUIREMENTS
==============================

Every extracted field must display:

• Verified From: Source category where value was found
  - title, contract_value, award_value, boq, pricing_schedule, payment_clause, table, body_text

• Page: Page number where evidence found

• Evidence: Full evidence trail and context

• Confidence: Detection confidence (0.0 to 1.0)

EVIDENCE STORE STRUCTURE
========================

{
  "field_name": {
    "verified_from": EvidenceSourceCategory,
    "page": int,
    "evidence": List[str],
    "confidence": float,
    "source_text": str,
    "context": str
  }
}

REPORT INTEGRATION
=================

All reports consume evidence from the schema manager:
- Completion Guide
- Readiness Report
- Submission Package
- Audit Report
- Result Viewer

NO HALLUCINATION
================

Evidence displayed must:
• Always include source category
• Always include page number
• Always include evidence context
• Always include confidence score
• Never be inferred or fabricated
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

from .services.evidence_engine import (
    EvidenceRecord,
    CurrencyEvidence,
    NumericEntityEvidence,
    EvidenceSourceCategory,
    NumericEntityType,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Report Evidence Display Components
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class EvidenceDisplay:
    """
    Complete evidence display component for use in reports.

    This structure provides all required evidence information for report display.
    """
    field_name: str = ""
    value: Any = None
    verified_from: str = ""
    page: Optional[int] = None
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.0
    source_text: str = ""
    context: str = ""
    detected_entity_type: Optional[str] = None
    
    def format_for_display(self) -> str:
        """Format evidence for professional report display."""
        parts = [f"Verified from: {self.verified_from}"]
        
        if self.page:
            parts.append(f"Page: {self.page}")
        
        if self.confidence > 0:
            parts.append(f"Confidence: {self.confidence:.0%}")
        
        evidence_str = "; ".join(self.evidence) if self.evidence else "No evidence available"
        parts.append(f"Evidence: {evidence_str[:150]}...")
        
        return "\n".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage and API responses."""
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# Report Evidence Builder
# ═══════════════════════════════════════════════════════════════════════

class ReportEvidenceBuilder:
    """
    Specialized evidence builder for report generation.

    Provides:
      • Evidence formatting for PDF reports
      • Confidence summaries and risk indicators
      • Evidence quality assessments
      • Report-ready evidence structures
    """
    
    def __init__(self):
        self._evidence_records: Dict[str, Any] = {}
    
    def add_evidence(
        self,
        field_name: str,
        value: Any,
        verified_from: EvidenceSourceCategory,
        page: Optional[int] = None,
        evidence: List[str] = None,
        confidence: float = 0.0,
        source_text: str = "",
        context: str = "",
        entity_type: Optional[NumericEntityType] = None,
    ) -> None:
        """
        Add an evidence record for a specific field.
        
        Args:
            field_name: Name of the field/document section
            value: Extracted value
            verified_from: Evidence source category
            page: Page number where found
            evidence: List of evidence strings
            confidence: Detection confidence (0.0-1.0)
            source_text: Original source text
            context: Surrounding context
            entity_type: Numeric entity type
        """
        self._evidence_records[field_name] = EvidenceDisplay(
            field_name=field_name,
            value=value,
            verified_from=verified_from.name if verified_from else "",
            page=page,
            evidence=evidence or [],
            confidence=confidence,
            source_text=source_text,
            context=context,
            detected_entity_type=entity_type.name if isinstance(entity_type, NumericEntityType) else entity_type,
        )
        
        logger.debug(f"[SCHEMA_BUILDER] Added evidence for: {field_name} verified_from={verified_from.name if verified_from else ''}")
    
    def get_evidence_record(self, field_name: str) -> Optional[EvidenceDisplay]:
        """Get evidence record for a specific field."""
        return self._evidence_records.get(field_name)
    
    def get_all_evidence(self) -> Dict[str, EvidenceDisplay]:
        """Get all evidence records."""
        return dict(self._evidence_records)
    
    def generate_evidence_summary(self) -> Dict[str, Any]:
        """
        Generate a comprehensive evidence summary for reports.
        
        Returns:
            Dictionary with evidence summary statistics
        """
        summary = {
            "total_fields": len(self._evidence_records),
            "fields_with_high_confidence": 0,
            "fields_with_med_confidence": 0,
            "fields_with_low_confidence": 0,
            "confidence_distribution": {},
            "evidence_sources": {},
            "average_confidence": 0.0,
        }
        
        if not self._evidence_records:
            return summary
        
        confidences = []
        
        for field, evid in self._evidence_records.items():
            conf = evid.confidence
            
            # Categorize confidence
            if conf >= 0.8:
                summary["fields_with_high_confidence"] += 1
            elif conf >= 0.5:
                summary["fields_with_med_confidence"] += 1
            else:
                summary["fields_with_low_confidence"] += 1
            
            # Track distribution
            conf_bucket = int(conf / 0.2) * 0.2
            conf_key = f"{int(conf_bucket * 100)}%"
            summary["confidence_distribution"][conf_key] = summary["confidence_distribution"].get(conf_key, 0) + 1
            
            # Track sources
            if evid.verified_from:
                summary["evidence_sources"][evid.verified_from] = summary["evidence_sources"].get(evid.verified_from, 0) + 1
            
            confidences.append(conf)
        
        total_conf = sum(confidences) / len(confidences) if confidences else 0
        summary["average_confidence"] = total_conf
        
        return summary
    
    def generate_critical_fields_report(
        self,
        critical_fields: List[str],
        confidence_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Generate critical fields report with evidence validation.
        
        Args:
            critical_fields: Fields that are critical for decision making
            confidence_threshold: Threshold for considering validation sufficient
            
        Returns:
            List of critical field reports with evidence details
        """
        critical_reports = []
        
        for field in critical_fields:
            evid = self._evidence_records.get(field)
            
            if not evid:
                critical_reports.append({
                    "field_name": field,
                    "status": "missing_evidence",
                    "message": "No evidence recorded for this field",
                })
                continue
            
            # Determine validation status
            if evid.confidence >= confidence_threshold and evid.evidence:
                status = "verified"
                status_color = "green"
            elif evid.confidence >= confidence_threshold:
                status = "partial"
                status_color = "amber"
            else:
                status = "unverified"
                status_color = "red"
            
            critical_reports.append({
                "field_name": field,
                "value": evid.value,
                "verified_from": evid.verified_from,
                "page": evid.page,
                "confidence": evid.confidence,
                "status": status,
                "status_color": status_color,
                "evidence": evid.evidence[:5],  # First 5 evidence items
                "remaining_evidence": len(evid.evidence) - 5 if len(evid.evidence) > 5 else 0,
            })
        
        return critical_reports
    
    def clear(self) -> None:
        """Clear all evidence records."""
        self._evidence_records.clear()


# ═══════════════════════════════════════════════════════════════════════
# Report Evidence Display Constants and Helpers
# ═══════════════════════════════════════════════════════════════════════

EVIDENCE_DISPLAY_ORDER = [
    "field_name",
    "value",
    "verified_from",
    "page",
    "evidence",
    "confidence",
]

EVIDENCE_CONFIDENCE_THRESHOLDS = {
    "high": 0.8,
    "medium": 0.5,
    "low": 0.0,
}

def confidence_to_color(confidence: float) -> str:
    """
    Convert confidence score to color for report display.
    
    Args:
        confidence: Confidence score (0.0 to 1.0)
    
    Returns:
        Color code for display (green, amber, or red)
    """
    if confidence >= 0.8:
        return "green"
    elif confidence >= 0.5:
        return "amber"
    else:
        return "red"


def confidence_to_status(confidence: float) -> str:
    """
    Convert confidence score to status string for reports.
    
    Args:
        confidence: Confidence score (0.0 to 1.0)
    
    Returns:
        Status description
    """
    if confidence >= 0.8:
        return "Verified"
    elif confidence >= 0.5:
        return "Partial"
    else:
        return "Unverified"


def format_evidence_for_pdf(evidence_display: EvidenceDisplay) -> str:
    """
    Format evidence display for professional PDF report output.
    
    Returns multi-line formatted text suitable for report generation.
    """
    lines = [
        f"Field: {evidence_display.field_name}",
        f"Value: {evidence_display.value}",
        f"Verified from: {evidence_display.verified_from}",
    ]
    
    if evidence_display.page:
        lines.append(f"Page: {evidence_display.page}")
    
    evidence_summary = "; ".join(evidence_display.evidence[:3])  # First 3 evidence items
    if evidence_display.evidence:
        lines.append(f"Evidence: {evidence_summary}")
    
    lines.append(f"Confidence: {evidence_display.confidence:.0%}")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Evidence-to-Schema Conversion Functions
# ═══════════════════════════════════════════════════════════════════════

def currency_evidence_to_display(
    currency_evidence: CurrencyEvidence,
    field_name: str = "currency",
) -> EvidenceDisplay:
    """
    Convert CurrencyEvidence to EvidenceDisplay format.
    
    Args:
        currency_evidence: Currency evidence object
        field_name: Name of the field/document section
    
    Returns:
        EvidenceDisplay object
    """
    return EvidenceDisplay(
        field_name=field_name,
        value=currency_evidence.currency_code,
        verified_from="body_text",
        page=None,  # Could be extracted from evidence if available
        evidence=currency_evidence.evidence,
        confidence=currency_evidence.confidence,
        source_text="; ".join(currency_evidence.source_text[:5]),
        context=" ".join(currency_evidence.source_text[5:10]) if len(currency_evidence.source_text) > 5 else "",
    )


def numeric_entity_evidence_to_display(
    entity_evidence: NumericEntityEvidence,
    field_name: str = "numeric_entity",
) -> EvidenceDisplay:
    """
    Convert NumericEntityEvidence to EvidenceDisplay format.
    
    Args:
        entity_evidence: Numeric entity evidence object
        field_name: Name of the field/document section
    
    Returns:
        EvidenceDisplay object
    """
    return EvidenceDisplay(
        field_name=field_name,
        value=entity_evidence.value,
        verified_from=entity_evidence.source_category.name if entity_evidence.source_category else "",
        page=entity_evidence.page_number,
        evidence=entity_evidence.evidence,
        confidence=entity_evidence.confidence,
        source_text=entity_evidence.source_text[0] if entity_evidence.source_text else "",
        context=" ".join(entity_evidence.context[:5]) if entity_evidence.context else "",
        detected_entity_type=entity_evidence.entity_type.name if entity_evidence.entity_type else None,
    )


# ═══════════════════════════════════════════════════════════════════════
# Schema Manager Integration
# ═══════════════════════════════════════════════════════════════════════

class EvidenceSchemaManager:
    """
    Centralized schema manager for evidence display integration.
    
    Provides unified interface for managing evidence across all reports.
    """
    
    def __init__(self):
        self._evidence_builder = ReportEvidenceBuilder()
    
    def add_currency_evidence(
        self,
        currency_evidence: CurrencyEvidence,
        field_name: str,
        verified_from: EvidenceSourceCategory,
        page: Optional[int] = None,
    ) -> None:
        """Add currency evidence to schema manager."""
        self._evidence_builder.add_evidence(
            field_name=field_name,
            value=currency_evidence.currency_code,
            verified_from=verified_from,
            page=page,
            evidence=currency_evidence.evidence,
            confidence=currency_evidence.confidence,
            source_text="; ".join(currency_evidence.source_text[:3]) if currency_evidence.source_text else "",
        )
    
    def add_numeric_entity_evidence(
        self,
        entity_evidence: NumericEntityEvidence,
        field_name: str,
        verified_from: EvidenceSourceCategory,
        page: Optional[int] = None,
    ) -> None:
        """Add numeric entity evidence to schema manager."""
        self._evidence_builder.add_evidence(
            field_name=field_name,
            value=entity_evidence.value,
            verified_from=verified_from,
            page=page,
            evidence=entity_evidence.evidence,
            confidence=entity_evidence.confidence,
            source_text=entity_evidence.source_text[0] if entity_evidence.source_text else "",
            context="; ".join(entity_evidence.context[:5]) if entity_evidence.context else "",
            entity_type=entity_evidence.entity_type,
        )
    
    def get_evidence_summary(self) -> Dict[str, Any]:
        """Get complete evidence summary."""
        return self._evidence_builder.generate_evidence_summary()
    
    def get_critical_fields_report(
        self,
        critical_fields: List[str],
        confidence_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Get critical fields validation report."""
        return self._evidence_builder.generate_critical_fields_report(critical_fields, confidence_threshold)
    
    def get_all_evidence(self) -> Dict[str, EvidenceDisplay]:
        """Get all evidence records."""
        return self._evidence_builder.get_all_evidence()
    
    def clear(self) -> None:
        """Clear all evidence records."""
        self._evidence_builder.clear()


# Singleton global instance
_evidence_schema_manager: Optional[EvidenceSchemaManager] = None


def get_evidence_schema_manager() -> EvidenceSchemaManager:
    """Get the global evidence schema manager instance."""
    global _evidence_schema_manager
    if _evidence_schema_manager is None:
        _evidence_schema_manager = EvidenceSchemaManager()
    return _evidence_schema_manager