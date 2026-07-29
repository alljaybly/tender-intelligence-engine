"""
Tests for the tender processing pipeline service.
Tests extractors and pipeline stages in isolation.
"""
import os
import sys
import tempfile
import unittest
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.services.extractors.sector_detector import detect_sector
from api.services.extractors.duration_extractor import detect_duration
from api.services.extractors.location_extractor import detect_locations
from api.services.extractors.workforce_extractor import detect_workforce
from api.services.extractors.schedule_extractor import detect_schedule
from api.services.pipeline import _extract_metadata, _extract_text


class TestSectorDetector(unittest.TestCase):
    """Test sector detection from document text."""

    def test_detect_cleaning(self):
        """Cleaning keywords should return 'cleaning'."""
        text = "The scope includes daily cleaning services, janitorial work, and floor care."
        self.assertEqual(detect_sector(text), "cleaning")

    def test_detect_construction(self):
        """Construction keywords should return 'construction'."""
        text = "Tender for road construction, earthworks, and concrete structures."
        self.assertEqual(detect_sector(text), "construction")

    def test_detect_electrical(self):
        """Electrical keywords should return 'electrical'."""
        text = "Electrical installation including cabling, wiring, and solar panels."
        self.assertEqual(detect_sector(text), "electrical")

    def test_detect_security(self):
        """Security keywords should return 'security'."""
        text = "Provide security guards, CCTV surveillance, and access control."
        self.assertEqual(detect_sector(text), "security")

    def test_detect_gardening(self):
        """Gardening keywords should return 'gardening'."""
        text = "Landscaping and gardening services including lawn mowing and tree pruning."
        self.assertEqual(detect_sector(text), "gardening")

    def test_detect_it_services(self):
        """IT keywords should return 'it_services'."""
        text = "IT services including software development, network support, and cloud."
        self.assertEqual(detect_sector(text), "it_services")

    def test_detect_supply(self):
        """Supply keywords should return 'supply'."""
        text = "Supply and delivery of furniture and PPE equipment."
        self.assertEqual(detect_sector(text), "supply")

    def test_empty_text_returns_none(self):
        """Empty text should return None."""
        self.assertIsNone(detect_sector(""))


class TestDurationDetector(unittest.TestCase):
    """Test contract duration extraction."""

    def test_period_of_months(self):
        """Period of X months should be detected."""
        self.assertEqual(detect_duration("period of 36 months"), 36)

    def test_duration_years(self):
        """X-year contract should be detected and converted to months."""
        self.assertEqual(detect_duration("5-year contract"), 60)

    def test_contract_period_months(self):
        """Contract period of X months should be detected."""
        self.assertEqual(detect_duration("contract period of 24 months"), 24)

    def test_no_duration_returns_none(self):
        """Text without duration should return None."""
        self.assertIsNone(detect_duration("This is a tender for general services."))


class TestLocationDetector(unittest.TestCase):
    """Test geographic location extraction."""

    def test_detect_gauteng(self):
        """Johannesburg should return gauteng."""
        locs = detect_locations("Work to be performed in Johannesburg, Gauteng.")
        self.assertIn("gauteng", locs)

    def test_detect_western_cape(self):
        """Cape Town should return western_cape."""
        locs = detect_locations("Site is located in Cape Town, Western Cape.")
        self.assertIn("western_cape", locs)

    def test_detect_national(self):
        """Nationwide should include national."""
        locs = detect_locations("This contract is nationwide across South Africa.")
        self.assertIn("national", locs)

    def test_no_location_returns_empty(self):
        """Text without locations should return empty list."""
        locs = detect_locations("Some random text without any place names.")
        self.assertEqual(locs, [])


class TestWorkforceDetector(unittest.TestCase):
    """Test workforce requirement extraction."""

    def test_detect_total_workers(self):
        """N workers should be detected."""
        result = detect_workforce("Requires 15 workers and 2 supervisors.")
        self.assertEqual(result.get("total_workers"), 15)
        self.assertEqual(result.get("supervisors"), 2)

    def test_detect_shifts_and_hours(self):
        """Shifts per day and hours should be detected."""
        result = detect_workforce("2 shifts per day, 8 hours per day.")
        self.assertEqual(result.get("shifts_per_day"), 2)
        self.assertEqual(result.get("hours_per_day"), 8.0)

    def test_no_workforce_returns_empty(self):
        """Returns empty dict when no workforce info."""
        self.assertEqual(detect_workforce("Just a simple description."), {})


class TestScheduleDetector(unittest.TestCase):
    """Test schedule/timeline extraction."""

    def test_detect_milestones(self):
        """Milestone keywords should be detected."""
        result = detect_schedule("Phase 1: Foundation. Phase 2: Structure. Milestone delivery.")
        self.assertTrue(result.get("has_milestones"))
        self.assertGreater(result.get("milestone_count", 0), 0)

    def test_detect_phases(self):
        """Phase N patterns should be counted."""
        result = detect_schedule("Phase 1 excavation, Phase 2 foundation, Phase 3 finishing.")
        self.assertGreater(result.get("phases_detected", 0), 0)


class TestPipelineMetadata(unittest.TestCase):
    """Test pipeline stage 1: metadata extraction."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.file_path = os.path.join(self.tmpdir, "test_doc.pdf")
        with open(self.file_path, "w") as f:
            f.write("dummy content")

    def tearDown(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        if os.path.exists(self.tmpdir):
            os.rmdir(self.tmpdir)

    def test_extract_metadata_basic(self):
        """Metadata should include size_bytes and file_type."""
        meta = _extract_metadata(self.file_path, "test_doc.pdf")
        self.assertIn("size_bytes", meta)
        self.assertIn("file_type", meta)
        self.assertEqual(meta["file_type"], "pdf")


if __name__ == "__main__":
    unittest.main()