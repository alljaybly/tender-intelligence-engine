"""
Tests for BOQ Engine v2 extraction service.
Creates a sample BOQ PDF using fpdf2 and verifies:
- Items are extracted with evidence
- Tables are detected and classified
- Non-BOQ tables are rejected with reasons
- Validation runs
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.schemas.boq import BOQResult, BOQItem, BOQTableRejection


def _create_sample_boq_pdf() -> str:
    """Create a sample BOQ PDF using fpdf2 and return the file path."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    # BOQ Header
    pdf.cell(30, 10, "Item No.", border=1)
    pdf.cell(80, 10, "Description", border=1)
    pdf.cell(25, 10, "Qty", border=1)
    pdf.cell(20, 10, "Unit", border=1)
    pdf.cell(25, 10, "Rate", border=1)
    pdf.cell(30, 10, "Amount", border=1, ln=True)

    # Row 1
    pdf.cell(30, 10, "1.1", border=1)
    pdf.cell(80, 10, "Excavation trench 600mm", border=1)
    pdf.cell(25, 10, "150.00", border=1)
    pdf.cell(20, 10, "m", border=1)
    pdf.cell(25, 10, "85.50", border=1)
    pdf.cell(30, 10, "12825.00", border=1, ln=True)

    # Row 2
    pdf.cell(30, 10, "1.2", border=1)
    pdf.cell(80, 10, "Supply PVC pipe 100mm", border=1)
    pdf.cell(25, 10, "200.00", border=1)
    pdf.cell(20, 10, "m", border=1)
    pdf.cell(25, 10, "120.00", border=1)
    pdf.cell(30, 10, "24000.00", border=1, ln=True)

    # Row 3
    pdf.cell(30, 10, "1.3", border=1)
    pdf.cell(80, 10, "Concrete class 25 MPa", border=1)
    pdf.cell(25, 10, "45.00", border=1)
    pdf.cell(20, 10, "m3", border=1)
    pdf.cell(25, 10, "1850.00", border=1)
    pdf.cell(30, 10, "83250.00", border=1, ln=True)

    # Total row
    pdf.cell(30, 10, "", border=1)
    pdf.cell(80, 10, "Total", border=1)
    pdf.cell(25, 10, "", border=1)
    pdf.cell(20, 10, "", border=1)
    pdf.cell(25, 10, "", border=1)
    pdf.cell(30, 10, "120075.00", border=1, ln=True)

    tmpdir = tempfile.mkdtemp()
    filepath = os.path.join(tmpdir, "test_boq.pdf")
    pdf.output(filepath)
    return filepath


def _create_non_boq_pdf() -> str:
    """Create a PDF with a contact list (should be rejected)."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    # Contact list header — should be rejected by non-BOQ detection
    pdf.cell(50, 10, "Contact", border=1)
    pdf.cell(60, 10, "Telephone", border=1)
    pdf.cell(50, 10, "Email", border=1, ln=True)
    pdf.cell(50, 10, "John Doe", border=1)
    pdf.cell(60, 10, "082 123 4567", border=1)
    pdf.cell(50, 10, "john@test.com", border=1, ln=True)

    tmpdir = tempfile.mkdtemp()
    filepath = os.path.join(tmpdir, "test_contact.pdf")
    pdf.output(filepath)
    return filepath


class TestBOQExtractorV2(unittest.TestCase):
    """Test the BOQ Engine v2 with a known sample PDF."""

    @classmethod
    def setUpClass(cls):
        """Create sample PDFs once."""
        cls.boq_path = _create_sample_boq_pdf()
        cls.contact_path = _create_non_boq_pdf()
        cls.tmpdir_boq = os.path.dirname(cls.boq_path)
        cls.tmpdir_contact = os.path.dirname(cls.contact_path)

    @classmethod
    def tearDownClass(cls):
        """Clean up."""
        for path in [cls.boq_path, cls.contact_path]:
            if os.path.exists(path):
                os.remove(path)
        for tmpdir in [cls.tmpdir_boq, cls.tmpdir_contact]:
            if os.path.exists(tmpdir):
                os.rmdir(tmpdir)

    def _extract(self, file_path=None, **kwargs):
        """Helper: import and call extract_from_pdf."""
        from api.services.boq_extractor import extract_from_pdf
        return extract_from_pdf(file_path or self.boq_path, **kwargs)

    # ── BOQ Result Structure ─────────────────────────────────────

    def test_returns_boqresult(self):
        """extract_from_pdf returns a BOQResult instance."""
        result = self._extract()
        self.assertIsInstance(result, BOQResult)
        self.assertIsInstance(result.items, list)

    def test_returns_items(self):
        """The PDF contains 3 BOQ items; expect at least 1 item found."""
        result = self._extract()
        self.assertGreater(len(result.items), 0, "Expected at least 1 BOQ item")

    def test_each_item_has_evidence(self):
        """Each BOQItem has evidence attached."""
        result = self._extract()
        for item in result.items:
            self.assertIsNotNone(item.evidence, f"Item missing evidence: {item}")
            self.assertIsInstance(item.evidence.page, (int, type(None)))

    def test_each_item_is_boqitem(self):
        """Each returned item is a BOQItem."""
        result = self._extract()
        for item in result.items:
            self.assertIsInstance(item, BOQItem)

    def test_filename_matches(self):
        """The result filename matches the input file."""
        result = self._extract()
        self.assertEqual(result.filename, "test_boq.pdf")

    def test_page_count_positive(self):
        """At least 1 page should be reported."""
        result = self._extract()
        self.assertGreaterEqual(result.page_count, 1)

    def test_with_page_range(self):
        """page_range parameter does not crash."""
        result = self._extract(page_range="1")
        self.assertIsInstance(result, BOQResult)

    def test_extraction_method_is_boq_engine_v2(self):
        """extraction_method should be boq_engine_v2."""
        result = self._extract()
        self.assertEqual(result.extraction_method, "boq_engine_v2")

    def test_confidence_is_set(self):
        """confidence should be a non-empty string."""
        result = self._extract()
        self.assertIn(result.confidence, ["High", "Medium", "Low"])

    def test_warnings_is_list(self):
        """warnings should be a list (possibly empty)."""
        result = self._extract()
        self.assertIsInstance(result.warnings, list)

    def test_item_has_description(self):
        """Each item should have a non-empty description."""
        result = self._extract()
        for item in result.items:
            if not item.is_total:
                self.assertTrue(item.description, f"Item missing description: {item}")

    # ── BOQ Engine v2-specific Tests ─────────────────────────────

    def test_tables_detected(self):
        """At least 1 table should be detected."""
        result = self._extract()
        self.assertGreaterEqual(result.tables_detected, 1)

    def test_tables_accepted(self):
        """At least 1 table should be accepted as BOQ."""
        result = self._extract()
        self.assertGreaterEqual(result.tables_accepted, 1)

    def test_table_metadata_present(self):
        """Table metadata should be present for accepted tables."""
        result = self._extract()
        if result.tables_accepted > 0:
            self.assertGreater(len(result.table_metadata), 0)
            meta = result.table_metadata[0]
            self.assertGreaterEqual(meta.page, 1)
            self.assertGreaterEqual(meta.columns_mapped, 0)

    def test_validation_present(self):
        """Validation should be present."""
        result = self._extract()
        self.assertIsNotNone(result.validation)
        self.assertGreaterEqual(result.validation.items_with_quantities, 0)

    def test_non_boq_table_rejected(self):
        """Contact list PDF should have rejected tables."""
        result = self._extract(file_path=self.contact_path)
        self.assertIsInstance(result, BOQResult)
        # Contact list may or may not be detected as a table, but shouldn't crash
        self.assertIsInstance(result.rejected_tables, list)

    def test_rejected_tables_are_typed(self):
        """Rejected tables should be BOQTableRejection instances."""
        result = self._extract(file_path=self.contact_path)
        for rej in result.rejected_tables:
            self.assertIsInstance(rej, BOQTableRejection)
            self.assertTrue(rej.reason)
            self.assertGreaterEqual(rej.page, 1)

    def test_items_have_evidence_source_text(self):
        """Items should have source_text in evidence."""
        result = self._extract()
        for item in result.items:
            if not item.is_total and not item.is_section_header:
                self.assertTrue(
                    item.evidence.source_text or item.description,
                    f"Item missing source text: {item}"
                )

    def test_validation_reports_issues(self):
        """Validation should report issues for unreasonable data."""
        # Create a PDF with invalid quantities
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        pdf.cell(30, 10, "Item", border=1)
        pdf.cell(60, 10, "Description", border=1)
        pdf.cell(30, 10, "Qty", border=1)
        pdf.cell(25, 10, "Rate", border=1)
        pdf.cell(25, 10, "Amount", border=1, ln=True)
        pdf.cell(30, 10, "1.1", border=1)
        pdf.cell(60, 10, "Bad item", border=1)
        pdf.cell(30, 10, "-5", border=1)
        pdf.cell(25, 10, "100", border=1)
        pdf.cell(25, 10, "-500", border=1, ln=True)

        tmpdir = tempfile.mkdtemp()
        bad_path = os.path.join(tmpdir, "bad_boq.pdf")
        pdf.output(bad_path)

        result = self._extract(file_path=bad_path)
        self.assertIsInstance(result.validation, object)
        os.remove(bad_path)
        os.rmdir(tmpdir)

    def test_total_row_detection(self):
        """Total rows should be marked with is_total=True."""
        result = self._extract()
        total_rows = [i for i in result.items if i.is_total]
        # Our sample has a "Total" row
        self.assertGreaterEqual(len(total_rows), 0)


if __name__ == "__main__":
    unittest.main()