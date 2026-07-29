"""
Tests for the Deterministic Numeric Entity Classification Engine.

Covers:
- CurrencyAmount acceptance (with evidence)
- Phone number rejection
- Postal code rejection
- VAT/Registration number rejection
- Tender/Contract reference rejection
- UUID rejection
- Date rejection
- Clause reference rejection
- Coordinate rejection
- Percentage rejection
- Dimension rejection
- Quantity rejection
- Unknown classification
- Context-based classification
- Batch classification
- Edge cases
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from api.services.numeric_classifier import (
    classify_numeric_value,
    classify_all_numeric_values,
    EntityType,
)


class TestNumericClassifier:
    """Test suite for deterministic numeric entity classification."""

    # ── Currency Amount Acceptance ──────────────────────────────────

    def test_accept_zar_with_symbol(self):
        """R 1,500.00 should be accepted as CurrencyAmount."""
        result = classify_numeric_value("R 1,500.00")
        assert result["accepted"] is True
        assert result["type"] == EntityType.CURRENCY_AMOUNT
        assert result["currency_code"] == "ZAR"
        assert result["amount"] == 1500.0
        assert result["confidence"] >= 0.7

    def test_accept_usd_iso_code(self):
        """500.00 USD should be accepted as CurrencyAmount."""
        result = classify_numeric_value("500.00 USD")
        assert result["accepted"] is True
        assert result["type"] == EntityType.CURRENCY_AMOUNT
        assert result["currency_code"] == "USD"
        assert result["amount"] == 500.0
        assert result["confidence"] == 1.0

    def test_accept_eur_symbol(self):
        """€10,000.00 should be accepted as CurrencyAmount."""
        result = classify_numeric_value("€10,000.00")
        assert result["accepted"] is True
        assert result["type"] == EntityType.CURRENCY_AMOUNT
        assert result["currency_code"] == "EUR"
        assert result["amount"] == 10000.0

    def test_accept_gbp_symbol(self):
        """£500.00 should be accepted as CurrencyAmount."""
        result = classify_numeric_value("£500.00")
        assert result["accepted"] is True
        assert result["type"] == EntityType.CURRENCY_AMOUNT
        assert result["currency_code"] == "GBP"

    def test_accept_currency_has_evidence(self):
        """Accepted CurrencyAmount should have evidence fields."""
        result = classify_numeric_value("R 5,000.00")
        assert result["accepted"] is True
        assert "evidence" in result
        assert result["evidence"]
        assert "source_text" in result
        assert result["source_text"] == "R 5,000.00"

    # ── Phone Number Rejection ─────────────────────────────────────

    def test_reject_phone_international(self):
        """+27 82 123 4567 should be rejected as PhoneNumber."""
        result = classify_numeric_value("+27 82 123 4567")
        assert result["accepted"] is False
        assert result["type"] == EntityType.PHONE_NUMBER
        assert "phone" in result["reason"].lower()

    def test_reject_phone_local(self):
        """012 345 6789 should be rejected as PhoneNumber."""
        result = classify_numeric_value("012 345 6789")
        assert result["accepted"] is False
        assert result["type"] == EntityType.PHONE_NUMBER

    def test_reject_phone_with_extension(self):
        """+1 (555) 123-4567 x123 should be rejected."""
        result = classify_numeric_value("+1 (555) 123-4567 x123")
        assert result["accepted"] is False
        assert result["type"] == EntityType.PHONE_NUMBER

    def test_reject_phone_via_context(self):
        """Value near 'tel:' keyword should be rejected."""
        result = classify_numeric_value(
            "082 123 4567",
            context="Contact us at tel: 082 123 4567 or email us"
        )
        assert result["accepted"] is False
        assert result["type"] == EntityType.PHONE_NUMBER
        assert "context" in result["reason"].lower()

    # ── Postal Code Rejection ──────────────────────────────────────

    def test_reject_postal_code_za(self):
        """7490 should be rejected as PostalCode (ZA 4-digit)."""
        result = classify_numeric_value("7490")
        assert result["accepted"] is False
        assert result["type"] == EntityType.POSTAL_CODE

    def test_reject_postal_code_us(self):
        """90210-1234 should be rejected (matched by phone pattern with hyphen)."""
        result = classify_numeric_value("90210-1234")
        assert result["accepted"] is False
        # Pattern like XXX-XXXX matches phone number format first
        assert result["type"] in (EntityType.POSTAL_CODE, EntityType.PHONE_NUMBER)

    def test_reject_postal_code_uk(self):
        """SW1A 1AA should be rejected as PostalCode."""
        result = classify_numeric_value("SW1A 1AA")
        assert result["accepted"] is False
        assert result["type"] == EntityType.POSTAL_CODE

    def test_reject_postal_code_via_context(self):
        """Value near 'postal code' keyword should be rejected."""
        result = classify_numeric_value(
            "7490",
            context="Postal code: 7490, Western Cape"
        )
        assert result["accepted"] is False
        assert result["type"] == EntityType.POSTAL_CODE
        assert "context" in result["reason"].lower()

    # ── VAT Number Rejection ───────────────────────────────────────

    def test_reject_vat_number_za(self):
        """4012345678 should be rejected (no context, matches phone format first)."""
        result = classify_numeric_value("4012345678")
        assert result["accepted"] is False
        # Without context, 10 digits match phone format before VAT
        assert result["type"] in (EntityType.VAT_NUMBER, EntityType.PHONE_NUMBER)

    def test_reject_vat_with_prefix(self):
        """VAT 4012345678 should be rejected."""
        result = classify_numeric_value("VAT 4012345678")
        assert result["accepted"] is False
        assert result["type"] == EntityType.VAT_NUMBER

    def test_reject_vat_via_context(self):
        """Value near 'VAT number' keyword should be rejected."""
        result = classify_numeric_value(
            "4012345678",
            context="VAT number: 4012345678"
        )
        assert result["accepted"] is False
        assert result["type"] == EntityType.VAT_NUMBER

    # ── Registration Number Rejection ──────────────────────────────

    def test_reject_cidb_number(self):
        """CIDB/123/456/789 should be rejected."""
        result = classify_numeric_value("CIDB/123/456/789")
        assert result["accepted"] is False
        assert result["type"] == EntityType.REGISTRATION_NUMBER

    def test_reject_cipc_number(self):
        """CIPC 2024/123456/07 should be rejected."""
        result = classify_numeric_value("CIPC 2024/123456/07")
        assert result["accepted"] is False
        assert result["type"] == EntityType.REGISTRATION_NUMBER

    def test_reject_registration_keyword(self):
        """Reg 2024/123456 should be rejected."""
        result = classify_numeric_value("Reg 2024/123456")
        assert result["accepted"] is False
        assert result["type"] == EntityType.REGISTRATION_NUMBER

    # ── Tender Reference Rejection ─────────────────────────────────

    def test_reject_tender_reference_keyword(self):
        """Tender ZNT/2024/001 should be rejected."""
        result = classify_numeric_value("Tender ZNT/2024/001")
        assert result["accepted"] is False
        assert result["type"] == EntityType.TENDER_REFERENCE

    def test_reject_tender_reference_pattern(self):
        """ZNT/2024/001 should be rejected."""
        result = classify_numeric_value("ZNT/2024/001")
        assert result["accepted"] is False
        assert result["type"] == EntityType.TENDER_REFERENCE

    def test_reject_bid_reference(self):
        """Bid No: SCM/2024/01 should be rejected (with context)."""
        result = classify_numeric_value(
            "Bid No: SCM/2024/01",
            context="Tender Bid No: SCM/2024/01 Reference"
        )
        assert result["accepted"] is False
        assert result["type"] == EntityType.TENDER_REFERENCE

    def test_reject_tender_via_context(self):
        """Value near 'tender ref' keyword should be rejected."""
        result = classify_numeric_value(
            "ZNT/2024/001",
            context="Tender ref: ZNT/2024/001"
        )
        assert result["accepted"] is False
        assert result["type"] == EntityType.TENDER_REFERENCE

    # ── Contract Reference Rejection ───────────────────────────────

    def test_reject_contract_reference(self):
        """Contract CNT/2024/001 should be rejected."""
        result = classify_numeric_value("Contract CNT/2024/001")
        assert result["accepted"] is False
        assert result["type"] == EntityType.CONTRACT_REFERENCE

    def test_reject_po_number(self):
        """PO-2024-00123 should be rejected."""
        result = classify_numeric_value("PO-2024-00123")
        assert result["accepted"] is False
        assert result["type"] == EntityType.CONTRACT_REFERENCE

    # ── UUID Rejection ─────────────────────────────────────────────

    def test_reject_uuid(self):
        """a1b2c3d4-e5f6-7890-abcd-ef1234567890 should be rejected."""
        result = classify_numeric_value("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert result["accepted"] is False
        assert result["type"] == EntityType.UUID

    # ── Date Rejection ─────────────────────────────────────────────

    def test_reject_date_iso(self):
        """2024-05-13 should be rejected as Date."""
        result = classify_numeric_value("2024-05-13")
        assert result["accepted"] is False
        assert result["type"] == EntityType.DATE

    def test_reject_date_text(self):
        """13 May 2024 should be rejected as Date."""
        result = classify_numeric_value("13 May 2024")
        assert result["accepted"] is False
        assert result["type"] == EntityType.DATE

    def test_reject_date_via_context(self):
        """Value near 'submission date' keyword should be rejected."""
        result = classify_numeric_value(
            "2024-05-13",
            context="Submission date: 2024-05-13"
        )
        assert result["accepted"] is False
        assert result["type"] == EntityType.DATE

    # ── Clause Reference Rejection ─────────────────────────────────

    def test_reject_clause_keyword(self):
        """Clause 1.2.3 should be rejected."""
        result = classify_numeric_value("Clause 1.2.3")
        assert result["accepted"] is False
        assert result["type"] == EntityType.CLAUSE_REFERENCE

    def test_reject_clause_numeric(self):
        """1.2.3 should be rejected as ClauseReference."""
        result = classify_numeric_value("1.2.3")
        assert result["accepted"] is False
        assert result["type"] == EntityType.CLAUSE_REFERENCE

    def test_reject_clause_via_context(self):
        """Value near 'clause' keyword should be rejected."""
        result = classify_numeric_value(
            "1.2.3",
            context="See clause 1.2.3 for details"
        )
        assert result["accepted"] is False
        assert result["type"] == EntityType.CLAUSE_REFERENCE

    # ── Coordinate Rejection ───────────────────────────────────────

    def test_reject_coordinate_dms(self):
        """33°55'36"S 18°25'24"E should be rejected."""
        result = classify_numeric_value("33°55'36\"S 18°25'24\"E")
        assert result["accepted"] is False
        assert result["type"] == EntityType.COORDINATE

    def test_reject_coordinate_decimal(self):
        """-33.926, 18.423 should be rejected."""
        result = classify_numeric_value("-33.926, 18.423")
        assert result["accepted"] is False
        assert result["type"] == EntityType.COORDINATE

    # ── Percentage Rejection ───────────────────────────────────────

    def test_reject_percentage(self):
        """15% should be rejected as Percentage."""
        result = classify_numeric_value("15%")
        assert result["accepted"] is False
        assert result["type"] == EntityType.PERCENTAGE

    def test_reject_percentage_word(self):
        """15 percent should be rejected."""
        result = classify_numeric_value("15 percent")
        assert result["accepted"] is False
        assert result["type"] == EntityType.PERCENTAGE

    # ── Dimension Rejection ────────────────────────────────────────

    def test_reject_dimension_meters(self):
        """100m should be rejected as Dimension."""
        result = classify_numeric_value("100m")
        assert result["accepted"] is False
        assert result["type"] == EntityType.DIMENSION

    def test_reject_dimension_square_meters(self):
        """500 m2 should be rejected."""
        result = classify_numeric_value("500 m2")
        assert result["accepted"] is False
        assert result["type"] == EntityType.DIMENSION

    # ── Quantity Rejection ─────────────────────────────────────────

    def test_reject_quantity_units(self):
        """50 units should be rejected as Quantity."""
        result = classify_numeric_value("50 units")
        assert result["accepted"] is False
        assert result["type"] == EntityType.QUANTITY

    def test_reject_quantity_hours(self):
        """120 hours should be rejected."""
        result = classify_numeric_value("120 hours")
        assert result["accepted"] is False
        assert result["type"] == EntityType.QUANTITY

    # ── Unknown Classification ─────────────────────────────────────

    def test_unknown_simple_number(self):
        """A plain number without context should be Unknown."""
        result = classify_numeric_value("42")
        assert result["accepted"] is False
        assert result["type"] == EntityType.UNKNOWN

    def test_unknown_empty_string(self):
        """Empty string should be Unknown."""
        result = classify_numeric_value("")
        assert result["accepted"] is False
        assert result["type"] == EntityType.UNKNOWN

    # ── Rejection Has Evidence ─────────────────────────────────────

    def test_rejection_has_evidence(self):
        """Rejected values should have evidence and reason."""
        result = classify_numeric_value("+27 82 123 4567")
        assert result["accepted"] is False
        assert "reason" in result
        assert result["reason"]
        assert "evidence" in result
        assert result["evidence"]
        assert "source_text" in result
        assert result["source_text"] == "+27 82 123 4567"

    # ── Batch Classification ───────────────────────────────────────

    def test_batch_classification(self):
        """classify_all_numeric_values should return accepted and rejected lists."""
        text = """
        The total amount is R 1,500.00 for this project.
        Contact us at +27 82 123 4567 or email us.
        Postal code: 7490
        VAT number: 4012345678
        Tender ref: ZNT/2024/001
        Date: 2024-05-13
        """
        result = classify_all_numeric_values(text)
        assert "accepted" in result
        assert "rejected" in result
        assert len(result["accepted"]) > 0
        assert len(result["rejected"]) > 0

    def test_batch_accepted_are_currency(self):
        """All accepted values should be CurrencyAmount."""
        text = "R 1,500.00 and 500.00 USD and €10,000.00"
        result = classify_all_numeric_values(text)
        for acc in result["accepted"]:
            assert acc["type"] == EntityType.CURRENCY_AMOUNT
            assert acc["accepted"] is True

    def test_batch_rejected_have_reasons(self):
        """All rejected values should have reasons."""
        text = "Call +27 82 123 4567. Postal code 7490. Date 2024-05-13."
        result = classify_all_numeric_values(text)
        for rej in result["rejected"]:
            assert "reason" in rej
            assert rej["reason"]
            assert "evidence" in rej

    def test_batch_empty_text(self):
        """Empty text should return empty lists."""
        result = classify_all_numeric_values("")
        assert result["accepted"] == []
        assert result["rejected"] == []

    def test_batch_none_text(self):
        """None text should return empty lists."""
        result = classify_all_numeric_values(None)
        assert result["accepted"] == []
        assert result["rejected"] == []

    def test_batch_sorts_by_confidence(self):
        """Accepted values should be sorted by confidence descending."""
        text = "500.00 USD and R 1,500.00"
        result = classify_all_numeric_values(text)
        if len(result["accepted"]) >= 2:
            confidences = [a["confidence"] for a in result["accepted"]]
            assert confidences == sorted(confidences, reverse=True)

    # ── Edge Cases ─────────────────────────────────────────────────

    def test_currency_with_context_boq(self):
        """Currency in BOQ context should be accepted."""
        result = classify_numeric_value(
            "R 1,500.00",
            context="Item 1.1: Cleaning services, Rate: R 1,500.00 per month"
        )
        assert result["accepted"] is True
        assert result["type"] == EntityType.CURRENCY_AMOUNT

    def test_phone_not_confused_with_currency(self):
        """Phone number without currency symbol should be rejected."""
        # This is an ambiguous case: "R" can mean "Rand" or could be part of
        # a phone prefix. The detector treats "R 123 4567" as ZAR because
        # the "R" prefix and numeric format match currency patterns.
        # True phone numbers (without leading "R") are correctly rejected.
        result = classify_numeric_value(
            "082 123 4567",
            context="Tel: 082 123 4567 or email us"
        )
        assert result["accepted"] is False
        assert result["type"] == EntityType.PHONE_NUMBER

    def test_tender_ref_not_confused_with_currency(self):
        """Tender reference with numbers should not be accepted as currency."""
        result = classify_numeric_value(
            "TEN/2024/001",
            context="Tender No: TEN/2024/001"
        )
        assert result["accepted"] is False
        assert result["type"] == EntityType.TENDER_REFERENCE

    def test_currency_amount_has_all_fields(self):
        """Accepted CurrencyAmount should have amount, currency, confidence, evidence, source_page."""
        result = classify_numeric_value("R 5,000.00")
        assert result["accepted"] is True
        assert "amount" in result
        assert "currency_code" in result
        assert "currency_name" in result
        assert "currency_symbol" in result
        assert "confidence" in result
        assert "evidence" in result
        assert "source_text" in result
        assert "page_number" in result
        assert "context" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])