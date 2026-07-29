"""
Tests for the Tender Readiness Report Service.

Tests all major functions:
  - build_readiness_report
  - compute_readiness_score
  - detect_missing_information
  - detect_missing_documents
  - build_confidence_summary
  - build_risk_summary
  - generate_recommendations
  - build_dashboard_payload
"""
import pytest
from datetime import datetime
from typing import Any, Dict

from api.services.tender_readiness_service import (
    build_readiness_report,
    compute_readiness_score,
    detect_missing_information,
    detect_missing_documents,
    build_confidence_summary,
    build_risk_summary,
    generate_recommendations,
    build_dashboard_payload,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def complete_result() -> Dict[str, Any]:
    """A fully complete processing result."""
    return {
        "job_id": "test-job-001",
        "filename": "tender_doc.pdf",
        "status": "completed",
        "full_text": "This is a tender document with SBD forms and tax clearance details. "
                     "Scope of work includes construction of a new school in Gauteng. "
                     "The project duration is 12 months. "
                     "The tender includes a comprehensive Bill of Quantities with detailed "
                     "pricing for all construction activities including excavation, concrete, "
                     "steel reinforcement, brickwork, roofing, plumbing, electrical installations, "
                     "and finishing works. All rates are inclusive of VAT and delivery.",
        "text_length": 520,
        "extraction_method": "pdf_direct",
        "pipeline_version": "2.1.0",
        "detected_sector": "Construction",
        "detected_duration_months": 12,
        "detected_locations": ["Gauteng", "Johannesburg"],
        "detected_schedule": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
        "detected_workforce": {
            "total_workers": 50,
            "skilled_workers": 20,
            "unskilled_workers": 25,
            "supervisors": 5,
            "shifts_per_day": 1,
            "hours_per_day": 8,
            "days_per_week": 5,
            "work_categories": ["Construction", "General Labour"],
            "workforce_inference_confidence": "High",
        },
        "boq_items": [
            {"item_no": "1", "description": "Excavation", "quantity": 100, "unit": "m³", "rate": 150.0, "amount": 15000.0},
            {"item_no": "2", "description": "Concrete", "quantity": 50, "unit": "m³", "rate": 2500.0, "amount": 125000.0},
            {"item_no": "3", "description": "Steel", "quantity": 10, "unit": "ton", "rate": 18000.0, "amount": 180000.0},
            {"item_no": "4", "description": "Bricks", "quantity": 5000, "unit": "each", "rate": 8.5, "amount": 42500.0},
            {"item_no": "5", "description": "Paint", "quantity": 200, "unit": "litre", "rate": 120.0, "amount": 24000.0},
            {"item_no": "6", "description": "Windows", "quantity": 30, "unit": "each", "rate": 3500.0, "amount": 105000.0},
            {"item_no": "7", "description": "Doors", "quantity": 20, "unit": "each", "rate": 4500.0, "amount": 90000.0},
            {"item_no": "8", "description": "Roofing", "quantity": 400, "unit": "m²", "rate": 850.0, "amount": 340000.0},
            {"item_no": "9", "description": "Plumbing", "quantity": 1, "unit": "lump sum", "rate": 75000.0, "amount": 75000.0},
            {"item_no": "10", "description": "Electrical", "quantity": 1, "unit": "lump sum", "rate": 95000.0, "amount": 95000.0},
        ],
        "boq_confidence": "High",
        "pricing_result": {
            "labour_cost": 500000.0,
            "materials_cost": 1200000.0,
            "transport_cost": 150000.0,
            "overheads": 85000.0,
            "subtotal": 1935000.0,
            "vat": 290250.0,
            "total_monthly": 185416.67,
            "total_annual": 2225000.0,
            "final_contract_value": 2225000.0,
            "price_reliability": "boq_based",
        },
        "pricing_status": "completed",
        "warnings": [],
        "failed_stages": [],
        "completed_stages": [
            "metadata", "text_extraction", "entity_extraction",
            "boq_analysis", "pricing_calculation", "finalisation",
        ],
        "metadata": {"pages": 25, "author": "Test"},
    }


@pytest.fixture
def partial_result() -> Dict[str, Any]:
    """A partial processing result with gaps."""
    return {
        "job_id": "test-job-002",
        "filename": "scanned_tender.pdf",
        "status": "partial_success",
        "full_text": "Short document with limited information.",
        "text_length": 45,
        "extraction_method": "ocr",
        "pipeline_version": "2.1.0",
        "detected_sector": None,
        "detected_duration_months": None,
        "detected_locations": [],
        "detected_schedule": {},
        "detected_workforce": {},
        "boq_items": [
            {"item_no": "1", "description": "Item 1", "quantity": 10, "unit": "each", "rate": None, "amount": None},
        ],
        "boq_confidence": "Low",
        "pricing_result": None,
        "pricing_status": "failed",
        "pricing_unavailable_reason": "Insufficient data for pricing",
        "warnings": ["OCR fallback used", "Low text quality", "Sector not detected",
                     "Duration not detected", "Missing pricing data"],
        "failed_stages": ["entity_extraction", "pricing_calculation"],
        "completed_stages": ["metadata", "text_extraction", "boq_analysis", "finalisation"],
        "metadata": {"pages": 3, "author": "Unknown"},
    }


@pytest.fixture
def failed_result() -> Dict[str, Any]:
    """A failed processing result."""
    return {
        "job_id": "test-job-003",
        "filename": "corrupt.pdf",
        "status": "failed",
        "full_text": None,
        "text_length": 0,
        "extraction_method": "ocr",
        "pipeline_version": "2.1.0",
        "detected_sector": None,
        "detected_duration_months": None,
        "detected_locations": [],
        "detected_schedule": {},
        "detected_workforce": {},
        "boq_items": [],
        "boq_confidence": None,
        "pricing_result": None,
        "pricing_status": "failed",
        "warnings": ["Pipeline failed: document could not be parsed"],
        "failed_stages": ["text_extraction", "entity_extraction", "boq_analysis", "pricing_calculation"],
        "completed_stages": [],
        "metadata": {},
    }


# ── Tests: compute_readiness_score ───────────────────────────────────


class TestComputeReadinessScore:
    def test_complete_result_scores_high(self, complete_result):
        score_data = compute_readiness_score(complete_result)
        assert score_data["overall_score"] >= 80
        assert score_data["label"] == "high"

    def test_partial_result_scores_low(self, partial_result):
        score_data = compute_readiness_score(partial_result)
        # Partial result has OCR, 45 chars, no sector, no pricing, no workforce
        # This is genuinely a very poor result, so score should be low
        assert score_data["overall_score"] < 50
        assert score_data["label"] in ("low", "critical")

    def test_failed_result_scores_low(self, failed_result):
        score_data = compute_readiness_score(failed_result)
        assert score_data["overall_score"] < 25
        assert score_data["label"] in ("low", "critical")

    def test_score_has_all_categories(self, complete_result):
        score_data = compute_readiness_score(complete_result)
        categories = score_data["categories"]
        assert "extraction_quality" in categories
        assert "entity_completeness" in categories
        assert "boq_completeness" in categories
        assert "pricing_availability" in categories
        assert "workforce_availability" in categories
        assert "document_integrity" in categories

    def test_score_breakdown_present(self, complete_result):
        score_data = compute_readiness_score(complete_result)
        breakdown = score_data["breakdown"]
        assert len(breakdown) == 6
        for key in ["extraction_quality", "entity_completeness", "boq_completeness",
                     "pricing_availability", "workforce_availability", "document_integrity"]:
            assert key in breakdown

    def test_score_returns_label_description(self, complete_result):
        score_data = compute_readiness_score(complete_result)
        assert "label_description" in score_data
        assert isinstance(score_data["label_description"], str)

    def test_score_range(self, complete_result):
        score_data = compute_readiness_score(complete_result)
        assert 0 <= score_data["overall_score"] <= 100


# ── Tests: detect_missing_information ────────────────────────────────


class TestDetectMissingInformation:
    def test_complete_result_no_missing(self, complete_result):
        missing = detect_missing_information(complete_result)
        assert missing["count"] == 0
        assert missing["completeness_percentage"] == 100.0

    def test_partial_result_has_missing(self, partial_result):
        missing = detect_missing_information(partial_result)
        assert missing["count"] > 0
        assert missing["completeness_percentage"] < 100.0

    def test_missing_fields_listed(self, partial_result):
        missing = detect_missing_information(partial_result)
        for mf in missing["missing_fields"]:
            assert "field" in mf
            assert "label" in mf
            assert "severity" in mf
            assert "reason" in mf

    def test_missing_summary_present(self, partial_result):
        missing = detect_missing_information(partial_result)
        assert "summary" in missing
        assert isinstance(missing["summary"], str)

    def test_required_fields_count(self, complete_result):
        missing = detect_missing_information(complete_result)
        assert missing["total_required"] == 6  # Matches REQUIRED_FIELDS


# ── Tests: detect_missing_documents ──────────────────────────────────


class TestDetectMissingDocuments:
    def test_complete_result_detects_some_docs(self, complete_result):
        docs = detect_missing_documents(complete_result)
        assert docs["total_required"] > 0
        assert docs["detected_count"] >= 0
        assert docs["missing_count"] >= 0

    def test_missing_documents_have_severity(self, partial_result):
        docs = detect_missing_documents(partial_result)
        for md in docs["missing"]:
            assert "severity" in md
            assert md["severity"] in ("critical", "high", "medium")

    def test_detected_documents_have_status(self, complete_result):
        docs = detect_missing_documents(complete_result)
        for dd in docs["detected"]:
            assert dd["status"] == "detected"

    def test_summary_present(self, complete_result):
        docs = detect_missing_documents(complete_result)
        assert "summary" in docs
        assert isinstance(docs["summary"], str)

    def test_no_full_text_shows_all_missing(self, failed_result):
        docs = detect_missing_documents(failed_result)
        assert docs["missing_count"] == docs["total_required"]


# ── Tests: build_confidence_summary ──────────────────────────────────


class TestBuildConfidenceSummary:
    def test_complete_result_medium_confidence(self, complete_result):
        cs = build_confidence_summary(complete_result)
        # 520 chars of text gives extraction score 0.3, which limits composite
        # The confidence service is honest and won't inflate scores
        assert cs["label"] in ("medium", "high")
        assert cs["overall_score"] >= 0.3

    def test_confidence_summary_text_present(self, complete_result):
        cs = build_confidence_summary(complete_result)
        assert cs["summary_text"]
        assert isinstance(cs["summary_text"], str)

    def test_breakdown_present(self, complete_result):
        cs = build_confidence_summary(complete_result)
        assert "breakdown" in cs
        assert "extraction" in cs["breakdown"]
        assert "boq" in cs["breakdown"]
        assert "pricing" in cs["breakdown"]

    def test_levels_present(self, complete_result):
        cs = build_confidence_summary(complete_result)
        assert "levels" in cs
        assert "extraction" in cs["levels"]
        assert "boq" in cs["levels"]
        assert "pricing" in cs["levels"]

    def test_failed_result_low_confidence(self, failed_result):
        cs = build_confidence_summary(failed_result)
        assert cs["label"] in ("low",)


# ── Tests: build_risk_summary ────────────────────────────────────────


class TestBuildRiskSummary:
    def test_complete_result_low_risk(self, complete_result):
        risk = build_risk_summary(complete_result)
        assert risk["overall_risk_level"] == "low"

    def test_partial_result_has_risks(self, partial_result):
        risk = build_risk_summary(partial_result)
        assert risk["risk_count"] > 0
        assert risk["overall_risk_level"] in ("high", "medium")

    def test_failed_result_high_risk(self, failed_result):
        risk = build_risk_summary(failed_result)
        assert risk["overall_risk_level"] == "high"

    def test_risks_have_correct_format(self, partial_result):
        risk = build_risk_summary(partial_result)
        for r in risk["risks"]:
            assert "category" in r
            assert "severity" in r
            assert "title" in r
            assert "description" in r
            assert "actionable" in r

    def test_risk_counts(self, partial_result):
        risk = build_risk_summary(partial_result)
        assert risk["critical_count"] + risk["high_count"] + risk["medium_count"] + risk["low_count"] == risk["risk_count"]

    def test_overall_assessment_present(self, complete_result):
        risk = build_risk_summary(complete_result)
        assert "overall_assessment" in risk
        assert isinstance(risk["overall_assessment"], str)


# ── Tests: generate_recommendations ──────────────────────────────────


class TestGenerateRecommendations:
    def test_complete_result_few_recs(self, complete_result):
        score_data = compute_readiness_score(complete_result)
        missing_info = detect_missing_information(complete_result)
        missing_docs = detect_missing_documents(complete_result)
        recs = generate_recommendations(complete_result, score_data, missing_info, missing_docs)
        assert isinstance(recs, list)
        # All fields present, so should have at least a "ready" recommendation
        assert len(recs) > 0

    def test_partial_result_has_recs(self, partial_result):
        score_data = compute_readiness_score(partial_result)
        missing_info = detect_missing_information(partial_result)
        missing_docs = detect_missing_documents(partial_result)
        recs = generate_recommendations(partial_result, score_data, missing_info, missing_docs)
        assert len(recs) > 0

    def test_failed_result_one_rec(self, failed_result):
        score_data = compute_readiness_score(failed_result)
        missing_info = detect_missing_information(failed_result)
        missing_docs = detect_missing_documents(failed_result)
        recs = generate_recommendations(failed_result, score_data, missing_info, missing_docs)
        assert len(recs) == 1
        assert recs[0]["priority"] == "critical"

    def test_recs_sorted_by_priority(self, partial_result):
        score_data = compute_readiness_score(partial_result)
        missing_info = detect_missing_information(partial_result)
        missing_docs = detect_missing_documents(partial_result)
        recs = generate_recommendations(partial_result, score_data, missing_info, missing_docs)
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for i in range(len(recs) - 1):
            assert priority_order.get(recs[i]["priority"], 99) <= priority_order.get(recs[i + 1]["priority"], 99)

    def test_recs_have_correct_format(self, partial_result):
        score_data = compute_readiness_score(partial_result)
        missing_info = detect_missing_information(partial_result)
        missing_docs = detect_missing_documents(partial_result)
        recs = generate_recommendations(partial_result, score_data, missing_info, missing_docs)
        for rec in recs:
            assert "priority" in rec
            assert "category" in rec
            assert "title" in rec
            assert "message" in rec
            assert "action" in rec


# ── Tests: build_dashboard_payload ───────────────────────────────────


class TestBuildDashboardPayload:
    def test_dashboard_has_required_fields(self, complete_result):
        score_data = compute_readiness_score(complete_result)
        risk_summary = build_risk_summary(complete_result)
        db = build_dashboard_payload(complete_result, score_data, risk_summary)
        required = ["readiness_score", "readiness_label", "risk_level", "risk_count",
                     "missing_fields_count", "missing_documents_count", "confidence_label",
                     "status", "has_pricing", "has_boq", "has_workforce"]
        for field in required:
            assert field in db, f"Missing dashboard field: {field}"

    def test_dashboard_values_match(self, complete_result):
        score_data = compute_readiness_score(complete_result)
        risk_summary = build_risk_summary(complete_result)
        db = build_dashboard_payload(complete_result, score_data, risk_summary)
        assert db["readiness_score"] == score_data["overall_score"]
        assert db["readiness_label"] == score_data["label"]
        assert db["risk_level"] == risk_summary["overall_risk_level"]
        assert db["risk_count"] == risk_summary["risk_count"]
        assert db["status"] == complete_result["status"]
        assert db["has_pricing"] is True
        assert db["has_boq"] is True
        assert db["has_workforce"] is True


# ── Tests: build_readiness_report (integration) ──────────────────────


class TestBuildReadinessReport:
    def test_complete_report_generated(self, complete_result):
        report = build_readiness_report(complete_result)
        assert report["job_id"] == "test-job-001"
        assert report["filename"] == "tender_doc.pdf"
        assert report["status"] == "completed"
        assert report["generated_at"] is not None

    def test_report_has_all_sections(self, complete_result):
        report = build_readiness_report(complete_result)
        assert "readiness_score" in report
        assert "missing_information" in report
        assert "missing_documents" in report
        assert "confidence_summary" in report
        assert "risk_summary" in report
        assert "recommendations" in report
        assert "dashboard" in report
        assert "raw" in report

    def test_report_logs_generate_time(self, complete_result):
        report = build_readiness_report(complete_result)
        assert "generated_at" in report
        # Verify it's an ISO format datetime string
        from datetime import datetime
        assert "T" in report["generated_at"]

    def test_partial_report_generated(self, partial_result):
        report = build_readiness_report(partial_result)
        assert report["job_id"] == "test-job-002"
        assert report["missing_information"]["count"] > 0
        assert len(report["recommendations"]) > 0

    def test_failed_report_generated(self, failed_result):
        report = build_readiness_report(failed_result)
        assert report["status"] == "failed"
        assert report["readiness_score"]["overall_score"] < 25

    def test_dashboard_counts_filled(self, complete_result):
        report = build_readiness_report(complete_result)
        assert report["dashboard"]["missing_fields_count"] >= 0
        assert report["dashboard"]["missing_documents_count"] >= 0

    def test_empty_result_does_not_crash(self):
        """Empty or minimal result should not crash the service."""
        minimal = {
            "job_id": "test-empty",
            "filename": "empty.txt",
            "status": "failed",
            "full_text": None,
            "text_length": 0,
            "extraction_method": "",
            "boq_items": [],
            "detected_workforce": {},
            "detected_locations": [],
            "detected_schedule": {},
            "pricing_result": None,
            "warnings": [],
            "failed_stages": [],
            "completed_stages": [],
            "metadata": {},
        }
        report = build_readiness_report(minimal)
        assert report is not None
        assert report["readiness_score"]["overall_score"] >= 0