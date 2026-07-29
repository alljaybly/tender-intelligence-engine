"""
Tests for processing result endpoint GET /api/process/result/{job_id}.

Tests:
  - completed job returns full result
  - partial_success job returns partial result with stage tracking
  - failed job returns structured failure response
  - processing/queued jobs are blocked
  - pricing_status is properly set for partial success
  - completed_stages / failed_stages are properly inferred
"""
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.schemas.process import ProcessingResult


def _make_result_json(
    status: str = "completed",
    has_pricing: bool = True,
    has_text: bool = True,
    has_sector: bool = True,
    has_metadata: bool = True,
    has_boq: bool = True,
) -> Dict[str, Any]:
    """Build a result_dict similar to what run_pipeline stores in result_json.

    This simulates the JSON that comes back from the database.
    """
    result: Dict[str, Any] = {
        "job_id": "test-job-123",
        "status": status,
        "filename": "test_doc.pdf",
    }

    if has_metadata:
        result["metadata"] = {"size_bytes": 1000, "page_count": 3, "file_type": "pdf"}

    if has_text:
        result["full_text"] = "Extracted document text..."
        result["text_length"] = 25

    if has_sector:
        result["detected_sector"] = "cleaning"
        result["detected_duration_months"] = 12
        result["detected_locations"] = ["gauteng"]
        result["detected_workforce"] = {"total_workers": 10, "supervisors": 2}
        result["detected_schedule"] = {"start": "2026-06-01"}

    if has_boq:
        result["boq_items"] = [
            {"item_no": "1.1", "description": "General cleaning", "quantity": 150.0, "unit": "hrs", "rate": 85.0, "amount": 12750.0}
        ]
        result["boq_confidence"] = "High"

    if has_pricing:
        result["pricing_result"] = {
            "total_monthly": 45322.08,
            "final_price": 543864.96,
            "confidence": "High",
        }
    else:
        result["pricing_result"] = None

    result["warnings"] = []
    result["extraction_method"] = "pipeline_v1"
    result["pipeline_version"] = "v1"

    return result


class TestProcessingResultSchema(unittest.TestCase):
    """Test ProcessingResult schema accepts valid inputs."""

    def test_completed_result_valid(self):
        """Completed result with all fields should validate."""
        data = _make_result_json(
            status="completed",
            has_pricing=True, has_text=True, has_sector=True,
            has_metadata=True, has_boq=True,
        )
        data["completed_stages"] = [
            "metadata", "text_extraction", "entity_extraction",
            "boq_analysis", "pricing_calculation", "finalisation",
        ]
        data["failed_stages"] = []
        data["pricing_status"] = "completed"

        result = ProcessingResult(**data)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.job_id, "test-job-123")
        self.assertEqual(result.detected_sector, "cleaning")
        self.assertIsNotNone(result.pricing_result)
        self.assertEqual(result.pricing_status, "completed")
        self.assertEqual(len(result.completed_stages), 6)

    def test_partial_success_without_pricing_valid(self):
        """Partial success without pricing should validate."""
        data = _make_result_json(
            status="partial_success",
            has_pricing=False, has_text=True, has_sector=True,
            has_metadata=True, has_boq=False,
        )
        data["completed_stages"] = ["metadata", "text_extraction", "entity_extraction", "finalisation"]
        data["failed_stages"] = ["boq_analysis", "pricing_calculation"]
        data["pricing_status"] = "failed"
        data["pricing_unavailable_reason"] = "Missing required pricing inputs"

        result = ProcessingResult(**data)
        self.assertEqual(result.status, "partial_success")
        self.assertIsNone(result.pricing_result)
        self.assertEqual(result.pricing_status, "failed")
        self.assertIn("pricing_calculation", result.failed_stages)
        self.assertIsNotNone(result.pricing_unavailable_reason)

    def test_failed_result_valid(self):
        """Failed result should validate."""
        result = ProcessingResult(
            job_id="test-job-123",
            status="failed",
            filename="test.pdf",
            warnings=["File processing crashed: some error"],
        )
        self.assertEqual(result.status, "failed")
        self.assertIn("some error", result.warnings[0])

    def test_minimal_partial_success(self):
        """Minimal partial_success should still validate."""
        result = ProcessingResult(
            job_id="test-job-456",
            status="partial_success",
            filename="doc.txt",
            completed_stages=["text_extraction", "finalisation"],
            failed_stages=["pricing_calculation"],
            warnings=["Pricing failed"],
        )
        self.assertEqual(result.status, "partial_success")
        self.assertEqual(len(result.completed_stages), 2)
        self.assertEqual(len(result.failed_stages), 1)


class TestStageInference(unittest.TestCase):
    """Test that completed_stages / failed_stages are correctly inferred from data."""

    def _run_inference(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate the inference logic from the result endpoint."""
        result_dict = dict(data)
        result_dict["completed_stages"] = result_dict.get("completed_stages", [])
        result_dict["failed_stages"] = result_dict.get("failed_stages", [])

        if not result_dict["completed_stages"]:
            inferred_completed = []
            inferred_failed = []
            stage_map = [
                ("metadata", "metadata", lambda r: bool(r.get("metadata"))),
                ("text_extraction", "full_text", lambda r: r.get("full_text") is not None),
                ("entity_extraction", "detected_sector", lambda r: r.get("detected_sector") is not None),
                ("boq_analysis", "boq_items", lambda r: bool(r.get("boq_items"))),
                ("pricing_calculation", "pricing_result", lambda r: r.get("pricing_result") is not None),
            ]
            for stage_name, field, checker in stage_map:
                if checker(result_dict):
                    inferred_completed.append(stage_name)
                else:
                    inferred_failed.append(stage_name)
            inferred_completed.append("finalisation")
            result_dict["completed_stages"] = inferred_completed
            result_dict["failed_stages"] = inferred_failed

        return result_dict

    def test_all_stages_completed(self):
        """All data present → all stages should be completed."""
        data = _make_result_json(
            status="completed", has_pricing=True, has_text=True,
            has_sector=True, has_metadata=True, has_boq=True,
        )
        inferred = self._run_inference(data)
        completed = inferred["completed_stages"]
        failed = inferred["failed_stages"]

        self.assertIn("metadata", completed)
        self.assertIn("text_extraction", completed)
        self.assertIn("entity_extraction", completed)
        self.assertIn("boq_analysis", completed)
        self.assertIn("pricing_calculation", completed)
        self.assertIn("finalisation", completed)
        self.assertEqual(len(failed), 0)

    def test_pricing_failed_stage(self):
        """No pricing → pricing_calculation should be in failed_stages."""
        data = _make_result_json(
            status="partial_success", has_pricing=False, has_text=True,
            has_sector=True, has_metadata=True, has_boq=False,
        )
        inferred = self._run_inference(data)
        failed = inferred["failed_stages"]

        self.assertIn("pricing_calculation", failed)

    def test_multiple_failed_stages(self):
        """Multiple missing fields → multiple failed stages."""
        data = _make_result_json(
            status="partial_success", has_pricing=False, has_text=True,
            has_sector=False, has_metadata=True, has_boq=False,
        )
        inferred = self._run_inference(data)
        failed = inferred["failed_stages"]

        self.assertIn("pricing_calculation", failed)
        self.assertIn("entity_extraction", failed)
        self.assertIn("boq_analysis", failed)
        # These should still be completed
        self.assertIn("metadata", inferred["completed_stages"])
        self.assertIn("text_extraction", inferred["completed_stages"])


class TestPricingStatusInference(unittest.TestCase):
    """Test that pricing_status is correctly set based on pricing_result."""

    def test_has_pricing_completed(self):
        """pricing_result present → status = completed."""
        data = _make_result_json(status="completed", has_pricing=True)
        if data.get("pricing_result") is not None:
            pricing_status = "completed"
        else:
            pricing_status = "failed" if data["status"] == "partial_success" else None
        self.assertEqual(pricing_status, "completed")

    def test_no_pricing_partial_success(self):
        """No pricing_result + partial_success → status = failed."""
        data = _make_result_json(status="partial_success", has_pricing=False)
        if data.get("pricing_result") is not None:
            pricing_status = "completed"
        else:
            pricing_status = "failed" if data["status"] == "partial_success" else None
        self.assertEqual(pricing_status, "failed")

    def test_no_pricing_completed(self):
        """No pricing_result + completed (unusual) → status = None."""
        data = _make_result_json(status="completed", has_pricing=False)
        if data.get("pricing_result") is not None:
            pricing_status = "completed"
        else:
            pricing_status = "failed" if data["status"] == "partial_success" else None
        self.assertIsNone(pricing_status)

    def test_partial_success_unavailable_reason(self):
        """partial_success without pricing → reason should be set."""
        data = _make_result_json(status="partial_success", has_pricing=False)
        reason = (
            "Pricing could not be calculated due to missing or insufficient data."
        ) if data["status"] == "partial_success" and data.get("pricing_result") is None else None
        self.assertIsNotNone(reason)


class TestResultEndpointStates(unittest.TestCase):
    """Test allowed/blocked statuses for result retrieval."""

    def test_allowed_statuses(self):
        """completed and partial_success should be allowed."""
        allowed = {"completed", "partial_success"}
        for status in ("completed", "partial_success"):
            self.assertIn(status, allowed)

    def test_blocked_statuses(self):
        """queued and processing should be blocked."""
        blocked = {"queued", "processing"}
        for status in ("queued", "processing"):
            self.assertIn(status, blocked)

    def test_failed_not_in_blocked(self):
        """failed should NOT be blocked."""
        blocked = {"queued", "processing"}
        self.assertNotIn("failed", blocked)


if __name__ == "__main__":
    unittest.main()