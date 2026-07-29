"""
Tests for backend hardening features:
- File hashing and duplicate detection
- MIME type validation
- Pricing mode selection
- Processing event creation
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.services.pipeline import _run_pricing, PIPELINE_VERSION
from api.routes.process import _detect_mime_from_bytes, _mime_matches_extension, _sanitise_filename


class TestMimeDetection(unittest.TestCase):
    """Test MIME type detection from magic bytes."""

    def test_pdf_magic_bytes(self):
        """%PDF at start should detect as application/pdf."""
        data = b"%PDF-1.4\n..."
        self.assertEqual(_detect_mime_from_bytes(data, ".pdf"), "application/pdf")

    def test_docx_magic_bytes(self):
        """PK (ZIP) at start should detect as DOCX."""
        data = b"PK\x03\x04..."
        self.assertEqual(
            _detect_mime_from_bytes(data, ".docx"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def test_txt_mime(self):
        """Plain text should detect as text/plain."""
        data = b"Hello World"
        self.assertEqual(_detect_mime_from_bytes(data, ".txt"), "text/plain")

    def test_pdf_mime_match(self):
        """PDF extension and PDF magic bytes should match."""
        self.assertTrue(_mime_matches_extension("application/pdf", ".pdf"))

    def test_mime_mismatch(self):
        """Extension mismatch should return False."""
        self.assertFalse(_mime_matches_extension("text/plain", ".pdf"))


class TestFilenameSanitisation(unittest.TestCase):
    """Test filename sanitisation and path traversal protection."""

    def test_removes_slashes(self):
        """Slashes should be removed from filenames."""
        safe = _sanitise_filename("../../../etc/passwd.txt")
        self.assertNotIn("/", safe)

    def test_preserves_alphanumeric(self):
        """Alphanumeric chars should pass through."""
        safe = _sanitise_filename("tender_document_2026.pdf")
        self.assertIn("tender", safe)

    def test_empty_fallback(self):
        """Empty name should get a fallback."""
        safe = _sanitise_filename("")
        self.assertTrue(safe.startswith("file"))

    def test_long_name_truncated(self):
        """Very long names should be truncated."""
        long_name = "a" * 200 + ".pdf"
        safe = _sanitise_filename(long_name)
        self.assertLess(len(safe), 150)

    # ── Bug-fix tests: extension preservation ───────────────────────

    def test_txt_extension_preserved(self):
        """test_cleaning.txt must remain test_cleaning.txt (not test_cleaningtxt)."""
        safe = _sanitise_filename("test_cleaning.txt")
        self.assertEqual(safe, "test_cleaning.txt")

    def test_pdf_extension_preserved(self):
        """document.pdf must preserve its .pdf extension."""
        safe = _sanitise_filename("document.pdf")
        self.assertEqual(safe, "document.pdf")

    def test_docx_extension_preserved(self):
        """report.docx must preserve its .docx extension."""
        safe = _sanitise_filename("report.docx")
        self.assertEqual(safe, "report.docx")

    def test_filename_with_underscores_and_hyphens(self):
        """Filename with underscores and hyphens must be preserved."""
        safe = _sanitise_filename("test_cleaning_v2-final.txt")
        self.assertEqual(safe, "test_cleaning_v2-final.txt")

    def test_extension_parsing_still_works(self):
        """os.path.splitext must correctly extract extension after sanitisation."""
        safe = _sanitise_filename("test_cleaning.txt")
        name, ext = os.path.splitext(safe)
        self.assertEqual(name, "test_cleaning")
        self.assertEqual(ext, ".txt")

    # ── Path traversal protection ───────────────────────────────────

    def test_path_traversal_dotdot_blocked(self):
        """Double-dot path traversal should be replaced with safe fallback."""
        safe = _sanitise_filename("../../malware.exe.pdf")
        self.assertNotIn("..", safe)
        self.assertTrue(safe.endswith(".txt"))

    def test_backslash_removed(self):
        """Backslashes should be stripped."""
        safe = _sanitise_filename("..\\..\\evil.txt")
        self.assertNotIn("\\", safe)
        self.assertNotIn("..", safe)

    def test_null_byte_removed(self):
        """Null bytes should be stripped."""
        safe = _sanitise_filename("test\\x00file.txt")
        self.assertNotIn("\x00", safe)

    # ── Dangerous character handling ────────────────────────────────

    def test_control_characters_removed(self):
        """Control characters should be stripped."""
        safe = _sanitise_filename("test\x01\x02file.txt")
        self.assertNotIn("\x01", safe)
        self.assertNotIn("\x02", safe)

    def test_special_chars_removed(self):
        """Special characters like $ % @ should be removed."""
        safe = _sanitise_filename("file$%^&*.txt")
        self.assertIn("file", safe)
        # Extension should still be .txt
        _, ext = os.path.splitext(safe)
        self.assertEqual(ext, ".txt")

    def test_multiple_extensions_blocked(self):
        """Multiple extensions like .exe.pdf should be handled.
        os.path.splitext splits on the LAST dot, so .pdf is the real extension.
        The .exe part is safe text in the basename.
        """
        safe = _sanitise_filename("virus.exe.pdf")
        name, ext = os.path.splitext(safe)
        self.assertEqual(ext, ".pdf")
        self.assertEqual(name, "virus.exe")

    # ── Edge cases ──────────────────────────────────────────────────

    def test_filename_no_extension(self):
        """Filename without extension should get a fallback."""
        safe = _sanitise_filename("README")
        _, ext = os.path.splitext(safe)
        self.assertEqual(ext, ".txt")

    def test_dot_only_name(self):
        """Name consisting of only dots should be handled safely."""
        safe = _sanitise_filename("....")
        self.assertTrue(safe.startswith("file"))
        _, ext = os.path.splitext(safe)
        self.assertEqual(ext, ".txt")

    def test_spaces_in_filename(self):
        """Spaces in filename should be preserved."""
        safe = _sanitise_filename("my tender document.pdf")
        self.assertIn(" ", safe)
        self.assertTrue(safe.endswith(".pdf"))


class TestPricingIntegration(unittest.TestCase):
    """Test pricing integration via the adapter (PricingEngine.calculate)."""

    def test_no_sector_returns_failure(self):
        """No sector should return None pricing and failure reason."""
        result, mode, reason = _run_pricing({}, [], None)
        self.assertIsNone(result)
        self.assertEqual(mode, "estimated")
        self.assertIsNotNone(reason)
        self.assertIn("No sector", reason)

    def test_sector_no_boq_returns_estimated_mode(self):
        """Sector present but no BOQ should return estimated mode."""
        entities = {"detected_sector": "cleaning"}
        result, mode, reason = _run_pricing(entities, [], None)
        self.assertEqual(mode, "estimated")

    def test_sector_with_boq_high_confidence_boq_based(self):
        """Sector + BOQ with High confidence should return boq_based mode."""
        entities = {"detected_sector": "cleaning"}
        boq_items = [
            {"item_no": "1", "description": "Cleaning", "quantity": 10, "unit": "hrs", "rate": 85.0, "amount": 850.0},
        ]
        result, mode, reason = _run_pricing(entities, boq_items, "High")
        self.assertEqual(mode, "boq_based")

    def test_sector_with_boq_low_confidence_estimated(self):
        """Sector + BOQ with Low confidence should return estimated mode."""
        entities = {"detected_sector": "cleaning"}
        boq_items = [
            {"item_no": "1", "description": "Cleaning", "quantity": 10, "unit": "hrs", "rate": 85.0, "amount": 850.0},
        ]
        result, mode, reason = _run_pricing(entities, boq_items, "Low")
        self.assertEqual(mode, "estimated")

    def test_pricing_failure_propagates_reason(self):
        """When pricing engine fails, reason should explain why."""
        entities = {"detected_sector": "cleaning"}
        result, mode, reason = _run_pricing(entities, [], None)
        # Pricing engine requires duration, area_sqm, shifts, hours for cleaning.
        # Since those are missing, it fails with a clear reason.
        self.assertIsNone(result)
        self.assertIsNotNone(reason)
        self.assertIn("Missing required pricing inputs", reason)
        self.assertIn("duration_months", reason.lower())


class TestPipelineVersion(unittest.TestCase):
    """Test pipeline versioning."""

    def test_pipeline_version_is_set(self):
        """PIPELINE_VERSION should be a non-empty string."""
        self.assertTrue(PIPELINE_VERSION)
        self.assertIsInstance(PIPELINE_VERSION, str)


if __name__ == "__main__":
    unittest.main()