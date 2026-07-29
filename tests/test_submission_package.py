"""
Tests for the Submission Package Generator Service.

Tests:
  - PDF generation for submission package
  - ZIP generation for submission package
  - All individual sections (BOQ, Pricing, Compliance, Submission)
  - Edge cases with missing data
"""
import pytest
from io import BytesIO
from typing import Any, Dict
from pypdf import PdfReader

from api.services.submission_package_service import (
    generate_submission_package,
    generate_submission_package_zip,
)
from api.services.tender_completion_guide import generate_completion_guide
from api.services.roadmap_audit_generator import generate_roadmap_pdf


def _pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


@pytest.fixture
def sample_result() -> Dict[str, Any]:
    """A typical processing result for testing."""
    return {
        "job_id": "test-job-pkg-001",
        "filename": "construction_tender.pdf",
        "status": "completed",
        "full_text": "This is a tender document for school construction.",
        "text_length": 1000,
        "extraction_method": "pdf_direct",
        "pipeline_version": "2.1.0",
        "detected_sector": "Construction",
        "detected_duration_months": 12,
        "detected_locations": ["Gauteng", "Pretoria"],
        "detected_schedule": {"start_date": "2025-06-01", "end_date": "2026-05-31"},
        "detected_workforce": {
            "total_workers": 50,
            "skilled_workers": 20,
            "unskilled_workers": 25,
            "supervisors": 5,
            "shifts_per_day": 1,
            "hours_per_day": 8,
            "days_per_week": 5,
            "work_categories": ["Construction", "General Labour"],
        },
        "boq_items": [
            {"item_no": "1", "description": "Excavation", "quantity": 100, "unit": "m³", "rate": 150.0, "amount": 15000.0},
            {"item_no": "2", "description": "Concrete", "quantity": 50, "unit": "m³", "rate": 2500.0, "amount": 125000.0},
            {"item_no": "3", "description": "Steel", "quantity": 10, "unit": "ton", "rate": 18000.0, "amount": 180000.0},
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
        "completed_stages": ["metadata", "text_extraction", "entity_extraction", "boq_analysis", "pricing_calculation", "finalisation"],
        "metadata": {"pages": 30, "author": "Test Engineer"},
    }


class TestSubmissionPackage:
    """Tests for the comprehensive Submission Package PDF."""

    def test_package_generates_pdf(self, sample_result):
        """Test that the submission package generates a non-empty PDF."""
        pdf = generate_submission_package("test-job-pkg-001", sample_result)
        assert isinstance(pdf, BytesIO)
        data = pdf.getvalue()
        assert len(data) > 1000  # Should be a meaningful PDF
        assert data[:4] == b"%PDF"  # PDF magic bytes

    def test_package_with_company_overrides(self, sample_result):
        """Test that company name overrides are accepted."""
        pdf = generate_submission_package(
            "test-job-pkg-001", sample_result,
            company_name_override="Acme Construction (Pty) Ltd",
            company_address_override="123 Main Street, Johannesburg",
        )
        assert isinstance(pdf, BytesIO)
        data = pdf.getvalue()
        assert len(data) > 1000
        assert data[:4] == b"%PDF"

    def test_package_with_partial_data(self):
        """Test package generation with partial/missing data."""
        partial = {
            "job_id": "partial-job-001",
            "filename": "partial_tender.pdf",
            "status": "partial_success",
            "full_text": None,
            "text_length": 0,
            "extraction_method": "ocr",
            "detected_sector": None,
            "detected_duration_months": None,
            "detected_locations": [],
            "detected_schedule": {},
            "detected_workforce": {},
            "boq_items": [],
            "boq_confidence": None,
            "pricing_result": None,
            "pricing_status": "failed",
            "warnings": ["OCR fallback used", "Low quality extraction"],
            "failed_stages": ["entity_extraction", "pricing_calculation"],
            "completed_stages": ["metadata", "text_extraction"],
            "metadata": {},
        }
        pdf = generate_submission_package("partial-job-001", partial)
        assert isinstance(pdf, BytesIO)
        data = pdf.getvalue()
        assert len(data) > 500
        assert data[:4] == b"%PDF"

    def test_package_with_empty_data(self):
        """Test that even empty/minimal data doesn't crash."""
        minimal = {
            "job_id": "empty-job",
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
        pdf = generate_submission_package("empty-job", minimal)
        assert isinstance(pdf, BytesIO)
        data = pdf.getvalue()
        assert len(data) > 500
        assert data[:4] == b"%PDF"


class TestSubmissionPackageZip:
    """Tests for the Submission Package ZIP."""

    def test_zip_generates_archive(self, sample_result):
        """Test that the ZIP file is a valid archive."""
        import zipfile
        zip_data = generate_submission_package_zip("test-job-pkg-001", sample_result)
        assert isinstance(zip_data, BytesIO)

        # Read the ZIP and verify contents
        with zipfile.ZipFile(zip_data, "r") as zf:
            names = zf.namelist()
            assert "01 Executive Summary.pdf" in names
            assert "02 Tender Completion Guide.pdf" in names
            assert "03 Tender Readiness Assessment.pdf" in names
            assert "04 Submission Letter.pdf" in names
            assert "05 Bid Response Roadmap.pdf" in names
            assert "06 Tender Integrity Audit.pdf" in names
            assert "07 Processing Audit.pdf" in names
            assert "08 Evidence Report.pdf" in names
            assert "11 Metadata.json" in names
            assert "PACKAGE_MANIFEST.txt" in names

    def test_zip_contents_are_valid_pdfs(self, sample_result):
        """Test that PDFs inside the ZIP are valid."""
        import zipfile
        zip_data = generate_submission_package_zip("test-job-pkg-001", sample_result)

        with zipfile.ZipFile(zip_data, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".pdf"):
                    content = zf.read(name)
                    assert content[:4] == b"%PDF", f"{name} is not a valid PDF"

    def test_completion_guide_is_not_the_roadmap(self, sample_result):
        guide_pdf = generate_completion_guide("test-job-pkg-001", sample_result).getvalue()
        roadmap_pdf = generate_roadmap_pdf("test-job-pkg-001", sample_result).getvalue()

        guide_text = _pdf_text(guide_pdf)
        roadmap_text = _pdf_text(roadmap_pdf)

        assert guide_pdf != roadmap_pdf
        assert "TENDER COMPLETION GUIDE" in guide_text
        assert "Completion Status" in guide_text
        assert "Missing Documents" in guide_text
        assert "Recommended Workflow" in guide_text
        assert "Helpful Tender Tips" in guide_text

        assert "BID RESPONSE ROADMAP" in roadmap_text
        assert "DATA ENTRY SCHEDULE" in roadmap_text
        assert "COMPLIANCE REQUIREMENTS CHECKLIST" in roadmap_text
        assert "MANUAL ENTRY REQUIRED" not in guide_text
        assert "Page References" not in guide_text

    def test_zip_uses_distinct_guide_and_roadmap_pdfs(self, sample_result):
        import zipfile

        zip_data = generate_submission_package_zip("test-job-pkg-001", sample_result)
        with zipfile.ZipFile(zip_data, "r") as zf:
            guide_pdf = zf.read("02 Tender Completion Guide.pdf")
            roadmap_pdf = zf.read("05 Bid Response Roadmap.pdf")

        assert guide_pdf != roadmap_pdf

        guide_text = _pdf_text(guide_pdf)
        roadmap_text = _pdf_text(roadmap_pdf)

        assert "Printable Submission Checklist" in guide_text
        assert "DATA ENTRY SCHEDULE" not in guide_text
        assert "DATA ENTRY SCHEDULE" in roadmap_text
        assert "Helpful Tender Tips" not in roadmap_text

    def test_zip_with_company_overrides(self, sample_result):
        """Test ZIP generation with company overrides."""
        import zipfile
        zip_data = generate_submission_package_zip(
            "test-job-pkg-001", sample_result,
            company_name_override="Test Company",
        )
        with zipfile.ZipFile(zip_data, "r") as zf:
            assert "01 Executive Summary.pdf" in zf.namelist()
            assert "04 Submission Letter.pdf" in zf.namelist()

    def test_zip_with_partial_data(self):
        """Test ZIP generation with partial data doesn't crash."""
        import zipfile
        partial = {
            "job_id": "partial-pkg",
            "filename": "partial.pdf",
            "status": "partial_success",
            "full_text": "Some text",
            "text_length": 10,
            "extraction_method": "pdf_direct",
            "detected_sector": "IT",
            "detected_duration_months": 6,
            "detected_locations": ["Cape Town"],
            "detected_schedule": {},
            "detected_workforce": {},
            "boq_items": [],
            "boq_confidence": None,
            "pricing_result": None,
            "pricing_status": "failed",
            "warnings": ["No BOQ extracted"],
            "failed_stages": ["boq_analysis"],
            "completed_stages": ["metadata", "text_extraction"],
            "metadata": {},
        }
        zip_data = generate_submission_package_zip("partial-pkg", partial)
        with zipfile.ZipFile(zip_data, "r") as zf:
            names = zf.namelist()
            assert "01 Executive Summary.pdf" in names
            assert "PACKAGE_MANIFEST.txt" in names

    def test_manifest_contains_required_sections(self, sample_result):
        """The generated ZIP must always include a populated manifest."""
        import zipfile

        zip_data = generate_submission_package_zip("test-job-pkg-001", sample_result)

        with zipfile.ZipFile(zip_data, "r") as zf:
            manifest = zf.read("PACKAGE_MANIFEST.txt").decode("utf-8")

        assert "Submission Package Manifest" in manifest
        assert "Package Version" in manifest
        assert "Package Size" in manifest
        assert "PACKAGE CONTENTS" in manifest
        assert "PROCESSING SUMMARY" in manifest
        assert "INTEGRITY" in manifest
        assert "Generated by Tender Engine" in manifest
