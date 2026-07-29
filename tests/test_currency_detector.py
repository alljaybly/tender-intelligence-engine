"""
Tests for the Deterministic Currency Detection Engine.

Covers:
- ISO code with amount detection
- Symbol detection
- No currency (unknown)
- Multi-currency documents
- BOQ item detection
- Procurement metadata detection
- Jurisdiction detection
- Edge cases (empty text, None inputs)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from api.services.currency_detector import (
    detect_currency,
    CurrencyDetector,
    CURRENCY_REGISTRY,
    SYMBOL_MAP,
)
from api.schemas.currency import CurrencyEvidence


class TestCurrencyDetection:
    """Test suite for deterministic currency detection."""

    def test_detect_none_text(self):
        """No text, no BOQ → not detected."""
        result = detect_currency(text=None)
        assert result.is_detected is False
        assert result.currency_code is None
        assert result.confidence == 0.0
        assert "No document text or BOQ items" in result.reason

    def test_detect_empty_text(self):
        """Empty text → not detected."""
        result = detect_currency(text="")
        assert result.is_detected is False
        assert result.currency_code is None

    def test_detect_zar_explicit_iso_with_amount(self):
        """'R 1,500.00' or '1500.00 ZAR' should detect ZAR."""
        # ISO code after amount
        result = detect_currency(text="The total amount is 1,500.00 ZAR for this project.")
        assert result.is_detected is True
        assert result.currency_code == "ZAR"
        assert result.confidence == 1.0
        assert result.detection_method == "iso_code_with_amount"

    def test_detect_usd_explicit_iso_with_amount(self):
        """'500.00 USD' should detect USD."""
        result = detect_currency(text="Total contract value: 500,000.00 USD")
        assert result.is_detected is True
        assert result.currency_code == "USD"
        assert result.confidence == 1.0

    def test_detect_eur_explicit_iso_with_amount(self):
        """'10,000.00 EUR' should detect EUR."""
        result = detect_currency(text="The budget is 10,000.00 EUR")
        assert result.is_detected is True
        assert result.currency_code == "EUR"
        assert result.confidence == 1.0

    def test_detect_gbp_symbol_with_amount(self):
        """'£500.00' should detect GBP."""
        result = detect_currency(text="The bid amount is £500.00")
        assert result.is_detected is True
        assert result.currency_code == "GBP"
        # £ maps to ["GBP", "EGP"] so confidence is 0.7 (not unique)
        assert result.confidence == 0.7

    def test_detect_dkk_symbol_kr_with_amount(self):
        """'500.00 kr' should detect DKK (first in priority)."""
        result = detect_currency(text="Total: 500.00 kr")
        assert result.is_detected is True
        assert result.currency_code == "DKK"
        # "kr" is a suffix symbol, matched via symbol_only fallback
        assert result.confidence == 0.3

    def test_detect_jpy_symbol_with_amount(self):
        """'¥10,000' should detect JPY."""
        result = detect_currency(text="Amount: ¥10,000")
        assert result.is_detected is True
        assert result.currency_code == "JPY"

    def test_detect_iso_code_only_no_amount(self):
        """ISO code without amount → lower confidence."""
        result = detect_currency(text="This tender is denominated in USD.")
        assert result.is_detected is True
        assert result.currency_code == "USD"
        assert result.confidence == 0.6
        assert result.detection_method == "iso_code_only"

    def test_detect_symbol_only_no_amount(self):
        """Symbol without amount → lowest confidence."""
        result = detect_currency(text="Prices are in $.")
        assert result.is_detected is True
        # $ maps to USD first
        assert result.currency_code == "USD"
        # $ maps to 5 possible codes → confidence 0.3
        assert result.confidence == 0.3

    def test_detect_no_currency(self):
        """No currency evidence → not detected."""
        result = detect_currency(text="This is a tender document for cleaning services.")
        assert result.is_detected is False
        assert result.currency_code is None
        assert result.confidence == 0.0
        assert "No reliable currency evidence" in result.reason

    def test_detect_zar_symbol_r_with_amount(self):
        """'R 5,000' should detect ZAR."""
        result = detect_currency(text="Total amount: R 5,000.00")
        assert result.is_detected is True
        assert result.currency_code == "ZAR"
        assert result.confidence >= 0.9

    def test_detect_from_boq_description(self):
        """BOQ item with ISO code in description."""
        boq_items = [
            {"description": "Labour costs in USD", "rate": 50.0, "amount": 1000.0},
            {"description": "Materials", "rate": 200.0, "amount": 4000.0},
        ]
        result = detect_currency(text=None, boq_items=boq_items)
        assert result.is_detected is True
        assert result.currency_code == "USD"
        assert result.detection_method == "boq_item_description"

    def test_currency_detector_class(self):
        """Test the CurrencyDetector class interface."""
        detector = CurrencyDetector()
        result = detector.detect_from_text("1500.00 ZAR")
        assert result.is_detected is True
        assert result.currency_code == "ZAR"

    def test_full_detect_method(self):
        """Test the detect method with all params."""
        detector = CurrencyDetector()
        result = detector.detect(
            text="100.00 GBP",
            detected_jurisdiction="united_kingdom",
            jurisdiction_confidence=0.96,
        )
        # ISO code takes priority over jurisdiction
        assert result.is_detected is True
        assert result.currency_code == "GBP"
        assert result.detection_method == "iso_code_with_amount"

    def test_jurisdiction_detection(self):
        """High-confidence jurisdiction detection."""
        result = detect_currency(
            text="This is a standard tender document.",
            detected_jurisdiction="south_africa",
            jurisdiction_confidence=0.98,
        )
        assert result.is_detected is True
        assert result.currency_code == "ZAR"
        assert result.detection_method == "jurisdiction"
        assert result.confidence == 0.95

    def test_low_confidence_jurisdiction(self):
        """Low-confidence jurisdiction should not trigger detection."""
        result = detect_currency(
            text="Some document text here.",
            detected_jurisdiction="south_africa",
            jurisdiction_confidence=0.50,  # Below 95% threshold
        )
        assert result.is_detected is False

    def test_registry_extensibility(self):
        """CURRENCY_REGISTRY should contain all required currencies."""
        required = {"ZAR", "USD", "EUR", "GBP", "DKK", "SEK", "NOK", "CHF",
                     "CAD", "AUD", "NZD", "JPY", "AED", "SAR", "QAR"}
        for code in required:
            assert code in CURRENCY_REGISTRY, f"Missing currency: {code}"
            info = CURRENCY_REGISTRY[code]
            assert "symbol" in info, f"Missing symbol for {code}"
            assert "name" in info, f"Missing name for {code}"

    def test_evidence_object_fields(self):
        """CurrencyEvidence should have all required fields."""
        result = detect_currency(text="500.00 EUR")
        assert hasattr(result, "currency_code")
        assert hasattr(result, "currency_name")
        assert hasattr(result, "currency_symbol")
        assert hasattr(result, "confidence")
        assert hasattr(result, "detection_method")
        assert hasattr(result, "evidence")
        assert hasattr(result, "source_pages")
        assert hasattr(result, "source_text")
        assert hasattr(result, "reason")
        assert hasattr(result, "is_detected")

    def test_to_dict_roundtrip(self):
        """CurrencyEvidence.to_dict() should roundtrip."""
        result = detect_currency(text="500.00 GBP")
        d = result.to_dict()
        assert d["currency_code"] == "GBP"
        assert d["confidence"] == 1.0
        assert d["is_detected"] is True

        # Reconstruct from dict
        restored = CurrencyEvidence.from_dict(d)
        assert restored.currency_code == "GBP"
        assert restored.confidence == 1.0
        assert restored.is_detected is True

    def test_not_detected_factory(self):
        """not_detected factory should create correct default."""
        nd = CurrencyEvidence.not_detected("No currency found.")
        assert nd.is_detected is False
        assert nd.confidence == 0.0
        assert nd.reason == "No currency found."
        assert nd.detection_method == "none"

    def test_detected_factory(self):
        """detected factory should create proper evidence."""
        d = CurrencyEvidence.detected(
            currency_code="ZAR",
            currency_name="South African Rand",
            currency_symbol="R",
            confidence=0.9,
            detection_method="iso_code_with_amount",
            evidence=["Found R 500 in document"],
            source_text=["R 500"],
        )
        assert d.is_detected is True
        assert d.currency_code == "ZAR"
        assert d.confidence == 0.9
        assert d.format_display() == "ZAR (R) - South African Rand"

    def test_format_display_unknown(self):
        """format_display should show Unknown for undetected."""
        nd = CurrencyEvidence.not_detected()
        assert nd.format_display() == "Currency: Unknown"

    def test_detect_zar_pipe_separated(self):
        """Pipe-separated values with ZAR."""
        result = detect_currency(text="| 1,500.00 | R 500.00 | Total |")
        assert result.is_detected is True
        assert result.currency_code == "ZAR"

    def test_detect_zar_in_table(self):
        """ZAR in tabular format."""
        result = detect_currency(text="Item 1  1000.00 ZAR")
        assert result.is_detected is True
        assert result.currency_code == "ZAR"

    def test_detect_all_required_currencies(self):
        """Spot-check each required currency can be detected."""
        tests = [
            ("100.00 ZAR", "ZAR"),
            ("100.00 USD", "USD"),
            ("100.00 EUR", "EUR"),
            ("100.00 GBP", "GBP"),
            ("100.00 DKK", "DKK"),
            ("100.00 SEK", "SEK"),
            ("100.00 NOK", "NOK"),
            ("100.00 CHF", "CHF"),
            ("100.00 CAD", "CAD"),
            ("100.00 AUD", "AUD"),
            ("100.00 NZD", "NZD"),
            ("100.00 JPY", "JPY"),
            ("100.00 AED", "AED"),
            ("100.00 SAR", "SAR"),
            ("100.00 QAR", "QAR"),
        ]
        for test_text, expected_code in tests:
            result = detect_currency(text=test_text)
            assert result.is_detected is True, f"Failed to detect {expected_code} in: {test_text}"
            assert result.currency_code == expected_code, f"Expected {expected_code}, got {result.currency_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])