"""
Regression tests for GET /api/process/status/{job_id}.

Root cause covered:
  The PostgreSQL/asyncpg backend returns TIMESTAMP columns as
  datetime.datetime objects, while the SQLite backend returns them as
  strings. ProcessingJobStatus declares created_at/updated_at as
  Optional[str], so the PostgreSQL rows raised a pydantic ValidationError
  inside the route handler. That produced an unhandled 500 before
  CORSMiddleware could attach the Access-Control-Allow-Origin header,
  which surfaced in the browser as a misleading CORS error.

Tests:
  - PostgreSQL-style datetime rows serialize successfully to ISO strings
  - SQLite-style string rows keep their existing behaviour unchanged
  - a missing job returns HTTP 404 rather than an unhandled exception
"""
import asyncio
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import HTTPException

from api.routes.process import _timestamp_to_iso, process_status


class _FakeCursor:
    """Minimal cursor emulating both database backends."""

    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _FakeConnection:
    """Records executed SQL/parameters and returns a canned row."""

    def __init__(self, row):
        self._row = row
        self.executed = []

    async def execute(self, sql, params=None):
        self.executed.append((sql, params))
        return _FakeCursor(self._row)


def _run_status(row, monkey_target=None):
    """Invoke the real endpoint against a fake database row."""
    from api.routes import process as process_module

    conn = _FakeConnection(row)

    async def fake_get_db():
        return conn

    async def fake_close_db(db):
        return None

    original_get_db = process_module.get_db
    original_close_db = process_module.close_db
    process_module.get_db = fake_get_db
    process_module.close_db = fake_close_db
    try:
        result = asyncio.run(process_status("ca1239a2863d42128a808429354049e4", {"email": "u@x.com"}))
    finally:
        process_module.get_db = original_get_db
        process_module.close_db = original_close_db
    return result, conn


class TestTimestampNormalisation(unittest.TestCase):
    """The helper must normalise both backends without touching writes."""

    def test_naive_datetime_becomes_iso_string(self):
        value = datetime(2026, 8, 8, 10, 0, 0)
        self.assertEqual(_timestamp_to_iso(value), "2026-08-08T10:00:00")

    def test_aware_datetime_becomes_iso_string(self):
        value = datetime(2026, 8, 8, 10, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(_timestamp_to_iso(value), "2026-08-08T10:00:00+00:00")

    def test_string_passes_through_unchanged(self):
        self.assertEqual(_timestamp_to_iso("2026-08-08 10:00:00"), "2026-08-08 10:00:00")

    def test_none_stays_none(self):
        self.assertIsNone(_timestamp_to_iso(None))


class TestProcessStatusEndpoint(unittest.TestCase):
    """The endpoint must succeed on both database backends."""

    def test_postgres_datetime_row_serializes(self):
        """PostgreSQL returns datetime objects — this previously raised a 500."""
        row = {
            "job_id": "ca1239a2863d42128a808429354049e4",
            "status": "completed",
            "progress": "finalisation",
            "created_at": datetime(2026, 8, 8, 10, 0, 0),
            "updated_at": datetime(2026, 8, 8, 10, 5, 0),
            "error_message": None,
        }
        result, _ = _run_status(row)
        self.assertEqual(result.job_id, "ca1239a2863d42128a808429354049e4")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.created_at, "2026-08-08T10:00:00")
        self.assertEqual(result.updated_at, "2026-08-08T10:05:00")
        self.assertIsNone(result.error_message)

    def test_sqlite_string_row_unchanged(self):
        """SQLite returns strings — existing behaviour must be preserved."""
        row = {
            "job_id": "ca1239a2863d42128a808429354049e4",
            "status": "processing",
            "progress": "extracting_document",
            "created_at": "2026-08-08 10:00:00",
            "updated_at": "2026-08-08 10:05:00",
            "error_message": None,
        }
        result, _ = _run_status(row)
        self.assertEqual(result.created_at, "2026-08-08 10:00:00")
        self.assertEqual(result.updated_at, "2026-08-08 10:05:00")
        self.assertEqual(result.status, "processing")

    def test_null_timestamps_allowed(self):
        row = {
            "job_id": "ca1239a2863d42128a808429354049e4",
            "status": "queued",
            "progress": None,
            "created_at": None,
            "updated_at": None,
            "error_message": None,
        }
        result, _ = _run_status(row)
        self.assertIsNone(result.created_at)
        self.assertIsNone(result.updated_at)

    def test_missing_job_returns_404(self):
        """A nonexistent job must raise 404, not an unhandled exception."""
        with self.assertRaises(HTTPException) as ctx:
            _run_status(None)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_postgres_datetime_row_no_longer_raises_validation_error(self):
        """Directly demonstrates the pre-fix failure: pydantic v2 rejects a
        datetime assigned to Optional[str]. The endpoint helper must prevent
        that from reaching the schema."""
        from api.schemas.process import ProcessingJobStatus
        from pydantic import ValidationError

        row = {
            "job_id": "ca1239a2863d42128a808429354049e4",
            "status": "completed",
            "progress": "finalisation",
            "created_at": datetime(2026, 8, 8, 10, 0, 0),
            "updated_at": datetime(2026, 8, 8, 10, 5, 0),
            "error_message": None,
        }
        with self.assertRaises(ValidationError):
            ProcessingJobStatus(**row)

        normalised = {
            **row,
            "created_at": _timestamp_to_iso(row["created_at"]),
            "updated_at": _timestamp_to_iso(row["updated_at"]),
        }
        ProcessingJobStatus(**normalised)

    def test_job_id_passed_as_query_parameter(self):
        """job_id must be bound as a parameter, never string-interpolated."""
        row = {
            "job_id": "ca1239a2863d42128a808429354049e4",
            "status": "completed",
            "progress": "done",
            "created_at": datetime(2026, 8, 8, 10, 0, 0),
            "updated_at": datetime(2026, 8, 8, 10, 5, 0),
            "error_message": None,
        }
        _, conn = _run_status(row)
        sql, params = conn.executed[0]
        self.assertIn("WHERE job_id = ?", sql)
        self.assertEqual(params, ("ca1239a2863d42128a808429354049e4",))


if __name__ == "__main__":
    unittest.main(verbosity=2)
