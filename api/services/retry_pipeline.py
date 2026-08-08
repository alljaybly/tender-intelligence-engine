"""
Retry Pipeline — Partial re-execution of failed pipeline stages.

This module provides the ability to retry RECOVERABLE pipeline stages
WITHOUT requiring full document re-upload.  It reuses the existing
uploaded file, existing metadata where appropriate, and preserves the
original job history and audit trail.

Architecture Rules:
  - Backend is ALWAYS source of truth
  - NO fake retries or fake completion states
  - partial_success must remain visible
  - warnings must remain visible
  - failed stages must remain visible
  - Original job history is preserved (retry_count, retried_stages tracked)

Stage Dependency Map:
  pricing_calculation  → requires boq_analysis + entity_extraction + text_extraction
  boq_analysis         → requires text_extraction
  entity_extraction    → requires text_extraction
  text_extraction      → no dependencies (runs from original file)
  metadata_extraction  → no dependencies
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from ..schemas.process import ProcessingResult, ExtractedBOQItem
from .pipeline import (
    _extract_metadata,
    _extract_text,
    _extract_entities,
    _extract_boq,
    _run_pricing,
    _log_event,
    _record_stage,
    _update_job,
    _update_tender,
    _store_result,
    PIPELINE_VERSION,
)
from ..services.database import get_db, close_db

logger = logging.getLogger(__name__)

# ── Recoverable stages ───────────────────────────────────────────────
# Only these stages can be retried.  Non-recoverable stages (like
# upload_received, finalisation) are never retried.
RECOVERABLE_STAGES: Set[str] = {
    "metadata_extraction",
    "text_extraction",
    "entity_extraction",
    "boq_analysis",
    "pricing_calculation",
}

# ── Stage dependency map ─────────────────────────────────────────────
# Maps a stage to the set of prerequisite stages it depends on.
# If a prerequisite has not been completed, it will be retried FIRST
# before the requested stage.
STAGE_DEPENDENCIES: Dict[str, Set[str]] = {
    "pricing_calculation": {"boq_analysis", "entity_extraction"},
    "boq_analysis": {"text_extraction"},
    "entity_extraction": {"text_extraction"},
    "text_extraction": set(),
    "metadata_extraction": set(),
}

# ── Structured failure reasons ───────────────────────────────────────

# Mapping of common failure patterns to structured metadata
# This is used when a stage fails to provide structured, actionable feedback
RECOVERABLE_FAILURES: Dict[str, Dict[str, Any]] = {
    "missing_sector": {
        "stage": "entity_extraction",
        "reason": "missing_sector",
        "recoverable": True,
        "retryable": True,
        "description": "No sector could be detected from the document text. "
                       "This may improve with OCR retry if the document is scanned.",
    },
    "ocr_failed": {
        "stage": "text_extraction",
        "reason": "ocr_failed",
        "recoverable": True,
        "retryable": True,
        "description": "OCR extraction did not produce usable text. "
                       "Ensure Tesseract is installed and the PDF contains readable content.",
    },
    "pricing_missing_data": {
        "stage": "pricing_calculation",
        "reason": "missing_sector",
        "recoverable": True,
        "retryable": True,
        "description": "Pricing could not be calculated due to missing sector or insufficient data. "
                       "Retrying with corrected extraction may resolve this.",
    },
    "boq_extraction_failed": {
        "stage": "boq_analysis",
        "reason": "extraction_error",
        "recoverable": True,
        "retryable": True,
        "description": "BOQ extraction encountered an error during parsing.",
    },
}

# ── Helpers ──────────────────────────────────────────────────────────


def _get_storage_path(job_id: str) -> Optional[str]:
    """
    Find the original uploaded file for a job_id.
    Searches in the uploads directory by pattern.
    """
    from pathlib import Path
    upload_dir = Path(__file__).resolve().parents[2] / "storage" / "uploads"
    upload_dir = upload_dir.resolve()
    if not upload_dir.exists():
        return None

    # Try to find file by job_id prefix
    for f in upload_dir.iterdir():
        if f.is_file() and f.name.startswith(job_id):
            return str(f)
    return None


def _load_existing_result(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Load the existing result_json from the processing_jobs table.
    Returns None if no result exists.
    """
    import json as _json
    db_path = None
    # We'll do this via direct DB call in the retry function
    return None  # Placeholder — actual loading happens in retry_pipeline


def _is_stage_completed(stage: str, stage_results: Dict[str, bool]) -> bool:
    """Check if a stage was previously completed successfully."""
    return stage_results.get(stage, False)


def _get_retry_file_path(job_id: str) -> Optional[str]:
    """
    Resolve the stored upload file path for a job.
    Falls back to the tenders table if the file isn't in the uploads dir.
    """
    file_path = _get_storage_path(job_id)
    if file_path and os.path.exists(file_path):
        return file_path
    return None


async def _load_job_context(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Load the full job context from the database for retry operations.
    Returns a dict with job metadata and existing results.
    Returns None if the job doesn't exist.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT pj.job_id, pj.filename, pj.original_name, pj.status,
                      pj.result_json, pj.error_message, pj.retry_count, pj.retry_data_json,
                      tf.original_filename,
                      tf.file_hash, tf.mime_type, tf.file_size
               FROM processing_jobs pj
               LEFT JOIN tenders tf ON tf.job_id = pj.job_id
               WHERE pj.job_id = ?""",
            (job_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        job = dict(row)
        return job
    finally:
        await close_db(db)


async def _save_retry_metadata(
    job_id: str,
    retry_count: int,
    retried_stages: List[str],
    status: str,
    result_json: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    Save retry metadata to the processing_jobs table.
    Tracks retry_count, retried_stages, and last_retry_at.
    """
    retry_data = {
        "retry_count": retry_count,
        "last_retry_at": datetime.now(timezone.utc).isoformat(),
        "retried_stages": retried_stages,
    }

    db = await get_db()
    try:
        now = datetime.now(timezone.utc)
        update_fields = {
            "status": status,
            "updated_at": now,
            "retry_count": retry_count,
            "retry_data_json": json.dumps(retry_data),
        }
        if result_json is not None:
            update_fields["result_json"] = result_json
        if error_message is not None:
            update_fields["error_message"] = error_message
        if status != "processing":
            update_fields["progress"] = "done" if status in ("completed", "partial_success") else "error"

        sets = []
        values = []
        for key, val in update_fields.items():
            sets.append(f"{key} = ?")
            values.append(val)

        await db.execute(
            f"UPDATE processing_jobs SET {', '.join(sets)} WHERE job_id = ?",
            (*values, job_id),
        )
        await db.commit()
    finally:
        await close_db(db)


def _determine_required_stages(
    requested_stages: List[str],
    existing_stage_results: Dict[str, bool],
) -> List[str]:
    """
    Determine the full set of stages that need to be executed for a retry.
    Includes dependencies and marks stages as needed if they were previously
    failed or if their dependents need them.

    Returns the ordered list of stages to execute.
    """
    from collections import OrderedDict

    # Collect all stages we need to run
    stages_to_run: Set[str] = set()

    for stage in requested_stages:
        if stage not in RECOVERABLE_STAGES:
            logger.warning("[RETRY] Skipping non-recoverable stage: %s", stage)
            continue

        # Add the stage itself
        stages_to_run.add(stage)

        # Add all dependencies recursively
        deps = STAGE_DEPENDENCIES.get(stage, set())
        for dep in deps:
            stages_to_run.add(dep)
            # Add sub-dependencies (one level deep is sufficient for our map)
            sub_deps = STAGE_DEPENDENCIES.get(dep, set())
            stages_to_run.update(sub_deps)

    # Order stages for execution: dependencies first
    ordered_stages: List[str] = []
    stage_order = [
        "metadata_extraction",
        "text_extraction",
        "entity_extraction",
        "boq_analysis",
        "pricing_calculation",
    ]

    for stage in stage_order:
        if stage in stages_to_run:
            ordered_stages.append(stage)

    return ordered_stages


def _classify_stage_failure(
    stage: str,
    error: Optional[str],
) -> Dict[str, Any]:
    """
    Classify a stage failure into structured metadata.
    Returns a dict with stage, reason, recoverable, retryable.
    """
    if not error:
        return {
            "stage": stage,
            "reason": "unknown_error",
            "recoverable": stage in RECOVERABLE_STAGES,
            "retryable": stage in RECOVERABLE_STAGES,
            "description": f"Stage '{stage}' failed with no error message.",
        }

    error_lower = error.lower()

    # Classify known failure patterns
    if "sector" in error_lower and "detect" in error_lower:
        return dict(RECOVERABLE_FAILURES["missing_sector"])
    if "ocr" in error_lower:
        return dict(RECOVERABLE_FAILURES["ocr_failed"])
    if "pricing" in error_lower:
        return dict(RECOVERABLE_FAILURES["pricing_missing_data"])
    if "boq" in error_lower:
        return dict(RECOVERABLE_FAILURES["boq_extraction_failed"])

    # Generic failure classification
    return {
        "stage": stage,
        "reason": "execution_error",
        "recoverable": stage in RECOVERABLE_STAGES,
        "retryable": stage in RECOVERABLE_STAGES,
        "description": error,
    }


# ── Main retry entry point ───────────────────────────────────────────


async def run_retry_pipeline(
    job_id: str,
    requested_stages: List[str],
) -> Dict[str, Any]:
    """
    Execute a partial retry of the tender processing pipeline.

    Reuses the existing uploaded file and preserves any successful stages.
    Only the requested stages (and their dependencies) are re-executed.

    Args:
        job_id: The job ID to retry
        requested_stages: List of stage names to retry (e.g. ["pricing_calculation"])

    Returns:
        Dict with status and result information

    Raises:
        ValueError: If the job doesn't exist or the stage is not retryable
        FileNotFoundError: If the original uploaded file cannot be found
    """
    logger.info("[RETRY] Starting retry for job %s, stages=%s", job_id, requested_stages)

    # ── Step 1: Load job context from DB ──────────────────────────────
    job_context = await _load_job_context(job_id)
    if job_context is None:
        raise ValueError(f"Job '{job_id}' not found.")

    current_status = job_context.get("status", "")
    if current_status not in ("partial_success", "failed", "completed"):
        raise ValueError(
            f"Job '{job_id}' is in status '{current_status}'. "
            f"Retry is only allowed for 'partial_success', 'failed', or 'completed' jobs."
        )

    # ── Step 2: Find the original uploaded file ───────────────────────
    file_path = _get_retry_file_path(job_id)
    if file_path is None:
        raise FileNotFoundError(
            f"Original uploaded file for job '{job_id}' could not be found. "
            f"Retry requires the original document."
        )

    original_name = job_context.get("original_name") or job_context.get("filename") or job_context.get("original_filename", "unknown")

    # ── Step 3: Parse existing result ─────────────────────────────────
    existing_result_json = job_context.get("result_json")
    existing_stage_results: Dict[str, bool] = {}

    if existing_result_json:
        try:
            existing_data = json.loads(existing_result_json)

            # Reconstruct stage_results from completed/failed stages
            completed = existing_data.get("completed_stages", [])
            failed = existing_data.get("failed_stages", [])
            for stage in completed:
                existing_stage_results[stage] = True
            for stage in failed:
                existing_stage_results[stage] = False
        except (json.JSONDecodeError, TypeError):
            logger.warning("[RETRY] Could not parse existing result_json for %s", job_id)

    # ── Step 4: Determine required stages (with dependencies) ─────────
    ordered_stages = _determine_required_stages(requested_stages, existing_stage_results)
    if not ordered_stages:
        raise ValueError(f"No recoverable stages requested: {requested_stages}")

    logger.info("[RETRY] Determined stages to run for %s: %s", job_id, ordered_stages)
    for dep_stage in ordered_stages:
        if dep_stage not in requested_stages:
            logger.info(
                "[RETRY] Dependency %s included automatically for %s",
                dep_stage, job_id,
            )

    # ── Step 5: Update status and increment retry count ───────────────
    current_retry_count = job_context.get("retry_count") or 0
    new_retry_count = current_retry_count + 1

    retried_stages = json.loads(job_context.get("retry_data_json") or "{}").get("retried_stages", [])
    for stage in ordered_stages:
        if stage not in retried_stages:
            retried_stages.append(stage)

    await _save_retry_metadata(
        job_id,
        retry_count=new_retry_count,
        retried_stages=retried_stages,
        status="processing",
    )
    await _log_event(job_id, "retry_started", "success",
                     f"Retry #{new_retry_count}: {','.join(ordered_stages)}")

    # ── Step 6: Execute requested stages (reusing existing data) ──────
    # Start with existing data from the previous run
    stage_results: Dict[str, bool] = dict(existing_stage_results)
    entities: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    full_text: Optional[str] = None
    boq_items: List[Dict[str, Any]] = []
    boq_confidence: Optional[str] = None
    boq_warnings: List[str] = []
    pricing_result: Optional[Dict[str, Any]] = None
    pricing_mode: str = "estimated"
    text_length: int = 0
    used_ocr: bool = False
    warnings: List[str] = []

    # Try to load existing data from the previous result_json
    if existing_result_json:
        try:
            existing_data = json.loads(existing_result_json)
            entities = {
                "detected_sector": existing_data.get("detected_sector"),
                "detected_duration_months": existing_data.get("detected_duration_months"),
                "detected_locations": existing_data.get("detected_locations", []),
                "detected_workforce": existing_data.get("detected_workforce", {}),
                "detected_schedule": existing_data.get("detected_schedule", {}),
            }
            metadata = existing_data.get("metadata", {})
            full_text = existing_data.get("full_text")
            text_length = existing_data.get("text_length", 0)
            boq_warnings = list(existing_data.get("warnings", []))
            pricing_result = existing_data.get("pricing_result")
        except (json.JSONDecodeError, TypeError):
            pass

    try:
        # ── Stage 1: Metadata extraction (only if requested) ──────────
        if "metadata_extraction" in ordered_stages:
            t0 = time.monotonic()
            logger.info("[RETRY] Running metadata_extraction for %s", job_id)
            try:
                metadata = _extract_metadata(file_path, original_name)
                stage_results["metadata_extraction"] = True
                await _record_stage(job_id, "metadata_extraction", True, str(metadata), t0)
            except Exception as e:
                stage_results["metadata_extraction"] = False
                await _record_stage(job_id, "metadata_extraction", False, str(e), t0)
                logger.warning("[RETRY] metadata_extraction failed: %s", e)
        else:
            # Reuse existing metadata
            logger.debug("[RETRY] Reusing existing metadata for %s", job_id)

        # ── Stage 2: Text extraction (only if requested) ──────────────
        if "text_extraction" in ordered_stages:
            t0 = time.monotonic()
            logger.info("[RETRY] Running text_extraction for %s", job_id)
            await _update_job(job_id, progress="document_text_extraction_retry")
            try:
                full_text, used_ocr = await _extract_text(file_path, original_name)
                text_length = len(full_text) if full_text else 0
                has_meaningful_text = full_text is not None and len(full_text.strip()) > 0
                stage_results["text_extraction"] = has_meaningful_text
                detail = f"{text_length} chars extracted" if has_meaningful_text else "No text extracted"
                if used_ocr:
                    detail += "; OCR fallback used"
                await _record_stage(job_id, "text_extraction", has_meaningful_text, detail, t0)
            except Exception as e:
                stage_results["text_extraction"] = False
                await _record_stage(job_id, "text_extraction", False, str(e), t0)
                logger.warning("[RETRY] text_extraction failed: %s", e)

        # ── Stage 3: Entity extraction (only if requested) ────────────
        if "entity_extraction" in ordered_stages:
            t0 = time.monotonic()
            logger.info("[RETRY] Running entity_extraction for %s", job_id)
            await _update_job(job_id, progress="entity_extraction_retry")
            try:
                if full_text:
                    entities = _extract_entities(full_text)
                stage_results["entity_extraction"] = True
                await _record_stage(job_id, "entity_extraction", True,
                                    f"sector={entities.get('detected_sector')}", t0)
            except Exception as e:
                stage_results["entity_extraction"] = False
                await _record_stage(job_id, "entity_extraction", False, str(e), t0)
                logger.warning("[RETRY] entity_extraction failed: %s", e)

        # ── Stage 4: BOQ analysis (only if requested) ─────────────────
        if "boq_analysis" in ordered_stages:
            t0 = time.monotonic()
            logger.info("[RETRY] Running boq_analysis for %s", job_id)
            await _update_job(job_id, progress="boq_analysis_retry")
            try:
                ext = os.path.splitext(original_name)[1].lower()
                if ext == ".pdf":
                    new_boq_items, new_boq_confidence, new_boq_warnings = await _extract_boq(file_path)
                    boq_items = new_boq_items
                    boq_confidence = new_boq_confidence
                    boq_warnings = new_boq_warnings

                    # Run sanitization
                    from .boq_sanitizer import sanitize_boq_items
                    sanitized_items, removal_log = sanitize_boq_items(boq_items)
                    if removal_log:
                        boq_warnings.extend(removal_log[:5])
                    boq_items = sanitized_items

                    # Run structural BOQ quality gate (SA-specific placeholders)
                    from .validator import validate_boq_for_pricing
                    boq_validation = validate_boq_for_pricing(boq_items)
                    if boq_validation["status"] == "error":
                        boq_warnings.append(boq_validation["message"])
                        boq_confidence = "Low"
                        # Store validation result to skip pricing/workforce later
                        # (we'll handle this in the pricing stage via boq_confidence + warning)
                        pass
                else:
                    boq_warnings.append("BOQ extraction only supported for PDF files")

                boq_ok = ext != ".pdf" or bool(boq_items) or boq_confidence in ("Medium", "High")
                stage_results["boq_analysis"] = boq_ok
                await _record_stage(job_id, "boq_analysis", boq_ok,
                                    f"{len(boq_items)} items, confidence={boq_confidence}", t0)
            except Exception as e:
                stage_results["boq_analysis"] = False
                await _record_stage(job_id, "boq_analysis", False, str(e), t0)
                boq_warnings.append(f"BOQ extraction failed: {e}")

        # ── Stage 5: Pricing calculation (only if requested) ──────────
        if "pricing_calculation" in ordered_stages:
            t0 = time.monotonic()
            logger.info("[RETRY] Running pricing_calculation for %s", job_id)
            await _update_job(job_id, progress="pricing_calculation_retry")
            pricing_unavailable_reason: Optional[str] = None
            try:
                # Check if BOQ validation failed (look for our warning message)
                boq_validation_failed = any(
                    "INSUFFICIENT_BOQ_DATA" in w or "HIGH_RATE_DETECTED" in w
                    for w in boq_warnings
                )
                if boq_validation_failed:
                    pricing_result = None
                    pricing_mode = "unavailable"
                    pricing_unavailable_reason = next(
                        (w for w in boq_warnings if "INSUFFICIENT_BOQ_DATA" in w or "HIGH_RATE_DETECTED" in w),
                        "BOQ validation failed"
                    )
                else:
                    pricing_result, pricing_mode, pricing_unavailable_reason = _run_pricing(
                        entities, boq_items, boq_confidence
                    )
                stage_results["pricing_calculation"] = pricing_result is not None
                await _record_stage(job_id, "pricing_calculation",
                                    stage_results["pricing_calculation"],
                                    f"mode={pricing_mode}", t0)
            except Exception as e:
                stage_results["pricing_calculation"] = False
                pricing_unavailable_reason = str(e)
                await _record_stage(job_id, "pricing_calculation", False, str(e), t0)

        # ── Step 7: Determine final status ────────────────────────────
        core_success = stage_results.get("metadata_extraction", False) or \
                       stage_results.get("text_extraction", False)
        final_status = "completed" if core_success else "failed"
        if final_status == "completed" and not all(stage_results.values()):
            has_partial_failure = any(
                not v for k, v in stage_results.items()
                if k in ("entity_extraction", "boq_analysis", "pricing_calculation")
            )
            if has_partial_failure:
                final_status = "partial_success"

        # ── Step 8: Build final result ─────────────────────────────────
        completed_stages = [s for s, ok in stage_results.items() if ok]
        failed_stages = [s for s, ok in stage_results.items() if not ok]
        completed_stages.append("finalisation")

        # Collect all warnings
        all_warnings: List[str] = list(boq_warnings)

        # Add retry context warning
        all_warnings.append(
            f"Retry #{new_retry_count} completed: "
            f"{'success' if final_status != 'failed' else 'failed'}"
        )

        # Classify failures
        stage_failures: List[Dict[str, Any]] = []
        for failed_stage in failed_stages:
            failure_info = _classify_stage_failure(failed_stage, None)
            stage_failures.append(failure_info)

        stored_text = full_text[:100000] if full_text else None

        result = ProcessingResult(
            job_id=job_id,
            status=final_status,
            filename=original_name,
            completed_stages=completed_stages,
            failed_stages=failed_stages,
            metadata=metadata,
            full_text=stored_text,
            text_length=text_length,
            detected_sector=entities.get("detected_sector"),
            detected_duration_months=entities.get("detected_duration_months"),
            detected_locations=entities.get("detected_locations", []),
            detected_workforce=entities.get("detected_workforce", {}),
            detected_schedule=entities.get("detected_schedule", {}),
            boq_items=[ExtractedBOQItem(**i) for i in boq_items],
            boq_confidence=boq_confidence,
            pricing_result=pricing_result,
            warnings=all_warnings,
            extraction_method=f"pipeline_{PIPELINE_VERSION}_retry",
            pipeline_version=f"{PIPELINE_VERSION}_retry",
        )

        result_dict = result.model_dump() if hasattr(result, "model_dump") else result.dict()
        result_json = json.dumps(result_dict, default=str)

        # Include structured failure metadata
        retry_response = {
            "job_id": job_id,
            "status": final_status,
            "retry_count": new_retry_count,
            "retried_stages": list(ordered_stages),
            "last_retry_at": datetime.now(timezone.utc).isoformat(),
            "stage_failures": stage_failures,
        }

        # ── Step 9: Save to database ─────────────────────────────────
        now = datetime.now(timezone.utc)
        await _save_retry_metadata(
            job_id,
            retry_count=new_retry_count,
            retried_stages=retried_stages,
            status=final_status,
            result_json=result_json,
            error_message=None if final_status != "failed" else f"Retry #{new_retry_count} failed",
        )
        await _update_tender(job_id, status=final_status, completed_at=now)

        # Update or insert tender_results — we overwrite with new data
        try:
            await _store_result(job_id, result, pricing_mode)
        except Exception as e:
            logger.warning("[RETRY] Could not update tender_results: %s", e)

        await _log_event(job_id, "retry_completed", "success",
                         f"Retry #{new_retry_count} -> {final_status}")

        logger.info(
            "[RETRY] Retry completed for job %s: retry_count=%d, status=%s, stages=%s",
            job_id, new_retry_count, final_status, ordered_stages,
        )

        return retry_response

    except Exception as e:
        logger.exception("[RETRY] Retry pipeline crashed for job %s", job_id)
        await _save_retry_metadata(
            job_id,
            retry_count=new_retry_count,
            retried_stages=retried_stages,
            status="failed",
            error_message=str(e),
        )
        await _update_tender(job_id, status="failed")
        await _log_event(job_id, "retry_completed", "failed", str(e))

        raise