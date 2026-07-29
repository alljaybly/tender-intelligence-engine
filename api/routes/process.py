"""
Tender upload and processing pipeline routes.

Routes:
  POST /api/process/upload        — Upload a tender document and start async processing
  POST /api/process-tender        — Legacy endpoint (preserved)
  GET  /api/process/status/{id}   — Check processing job status
  GET  /api/process/result/{id}   — Retrieve processing job result
  GET  /api/process/history       — Get user's processing history
  POST /api/process/retry/{job_id} — Retry failed pipeline stages
"""
import asyncio
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from ..schemas.process import (
    ProcessUploadResponse,
    ProcessingJobStatus,
    ProcessingResult,
    ProcessingHistoryItem,
    RetryRequest,
    RetryResponse,
)
from ..routes.auth import get_current_user
from ..services.database import get_db, close_db
from ..services.pipeline import (
    run_pipeline, _create_job, _update_job,
    _create_tender_record, _check_duplicate,
)
from ..services.job_store import create_job, update_job
from ..services.worker import process_job
from ..services.user_store import record_job_failure
from ..utils import error_response
from ..services.export_service import generate_export
from ..services.pdf_report_service import generate_pdf_report
from ..services.roadmap_audit_generator import generate_bid_response_roadmap, generate_tender_integrity_audit
from ..services.submission_letter_service import generate_submission_letter
from ..services.submission_package_service import (
    generate_submission_package,
    generate_submission_package_zip,
)
from ..services.tender_readiness_service import build_readiness_report, generate_readiness_pdf

logger = logging.getLogger(__name__)

# Main router (legacy / process-tender stays here)
router = APIRouter()

# Sub-router for new pipeline endpoints under /process
process_pipeline_router = APIRouter(prefix="/process")

# ── Storage directories ─────────────────────────────────────────────
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "storage" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file extensions for the new pipeline
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# ── Binary/executable magic bytes ────────────────────────────────
# ELF (Linux/Unix executables)
ELF_MAGIC = b"\x7fELF"
# PE (Windows executables - PE header starts with "PE\x00\x00" at offset 0x3C)
PE_MAGIC = b"MZ"
# Mach-O (macOS executables)
MACHO_MAGIC_32 = b"\xfe\xed\xface"
MACHO_MAGIC_64 = b"\xfe\xed\xfacf"
MACHO_MAGIC_CIGAM_32 = b"\xce\xfa\xed\xfe"
MACHO_MAGIC_CIGAM_64 = b"\xcf\xfa\xed\xfe"
EXECUTABLE_MAGICS = {ELF_MAGIC, PE_MAGIC, MACHO_MAGIC_32, MACHO_MAGIC_64,
                     MACHO_MAGIC_CIGAM_32, MACHO_MAGIC_CIGAM_64}

PDF_MAGIC = b"%PDF"
DOCX_MAGIC = b"PK\x03\x04"
BOM_MAGIC = b"\xef\xbb\xbf"


def _sanitise_filename(filename: str) -> str:
    """Remove dangerous characters from a filename while preserving extension.

    Permitted characters in base name: a-z, A-Z, 0-9, underscore (_),
    hyphen (-), period (.), space ( ).
    Permitted in extension: a-z, A-Z, 0-9, and the leading period (.).
    Blocks: path traversal (..), slashes, null bytes, control characters.
    """
    # Remove path separators, null bytes, control characters upfront
    filename = re.sub(r"[/\\\x00-\x1f]", "", filename)

    name, ext = os.path.splitext(filename)

    # Keep only safe chars in the base name
    safe_name = re.sub(r"[^a-zA-Z0-9\-_\. ]", "", name)[:128]

    # Keep only safe chars in extension: letters, digits, and the leading dot
    safe_ext = re.sub(r"[^a-zA-Z0-9\.]", "", ext)[:10]

    # Block path traversal (..) in the cleaned result
    if ".." in safe_name or ".." in safe_ext:
        safe_name = "file"
        safe_ext = ".txt"

    # Block multiple dangerous extensions (e.g. .exe.pdf)
    ext_count = safe_ext.count(".")
    if ext_count > 1:
        safe_name = "file"
        safe_ext = ".txt"

    # Preserve at most one dot for extension separator
    if safe_ext and safe_ext[0] != ".":
        safe_ext = f".{safe_ext}"

    if not safe_name:
        safe_name = "file"
    if not safe_ext:
        safe_ext = ".txt"

    return f"{safe_name}{safe_ext}"


# ── File signature validation ─────────────────────────────────────`


def _is_executable(data: bytes) -> bool:
    """Check if file content matches known executable/binary magic bytes."""
    if len(data) < 4:
        return False
    # Check ELF
    if data[:4] == ELF_MAGIC:
        return True
    # Check PE (MZ header)
    if data[:2] == PE_MAGIC:
        return True
    # Check Mach-O
    header = data[:4]
    if header in (MACHO_MAGIC_32, MACHO_MAGIC_64, MACHO_MAGIC_CIGAM_32, MACHO_MAGIC_CIGAM_64):
        return True
    return False


def _is_binary_content(data: bytes, sample_size: int = 512) -> bool:
    """Detect if content is binary (non-text) by checking for null bytes
    and a high ratio of non-printable characters in the first sample_size bytes.

    This is used to reject binary files renamed as .txt.
    """
    sample = data[:sample_size]
    if not sample:
        return False

    # Null bytes are a strong indicator of binary content
    null_count = sample.count(b"\x00")

    # Count non-printable, non-whitespace control characters
    control_count = 0
    for byte in sample:
        if byte < 0x20 and byte not in (0x09, 0x0a, 0x0d):  # non-tab, non-newline, non-CR
            control_count += 1

    # Heuristic: null bytes present OR >10% control chars → likely binary
    if null_count > 0:
        return True
    if control_count > len(sample) * 0.10:
        return True
    return False


def _validate_file_signature(data: bytes, ext: str) -> tuple[bool, str]:
    """Strict file signature validation.

    Returns (is_valid, error_message).
    Rejects executable/binary files renamed to look like documents.
    """
    # Step 1: Reject executables regardless of extension
    if _is_executable(data):
        return False, "Executable files are not allowed."

    # Step 2: Validate by extension
    if ext == ".pdf":
        if data[:4] != PDF_MAGIC:
            return False, "File does not have a valid PDF signature."
        return True, ""

    if ext == ".docx":
        if data[:4] != DOCX_MAGIC:
            return False, "File does not have a valid DOCX (ZIP) signature."
        return True, ""

    if ext == ".txt":
        # Reject binary files renamed as .txt
        if _is_binary_content(data):
            return False, "Binary files are not allowed as .txt."
        return True, ""

    # Unknown extension (should not happen if called after extension check)
    return False, f"Unsupported file extension: {ext}"


# ── MIME detection helpers ─────────────────────────────────────────


def _detect_mime_from_bytes(data: bytes, ext: str) -> str:
    """Detect MIME type from file magic bytes, with extension fallback."""
    if data[:4] == PDF_MAGIC:
        return "application/pdf"
    if data[:4] == DOCX_MAGIC:
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if data[:3] == BOM_MAGIC or ext == ".txt":
        return "text/plain"
    # Generic fallback
    mime_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
    }
    return mime_map.get(ext, "application/octet-stream")


def _mime_matches_extension(mime: str, ext: str) -> bool:
    """Check if detected MIME type is consistent with file extension."""
    ext_to_mime = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
    }
    expected = ext_to_mime.get(ext)
    if expected and mime != expected:
        # Allow ZIP container for DOCX (PK magic bytes)
        if ext == ".docx" and mime.startswith("application/"):
            return True
        return False
    return True


# ── Legacy endpoint (preserved) ────────────────────────────────────


@router.post('/process-tender')
async def process_tender(request: Request, file: UploadFile = File(...), cost_per_hour: Optional[float] = Form(None)):
    if cost_per_hour is not None and cost_per_hour <= 0:
        return error_response("validation_error", "cost_per_hour must be greater than 0", 422)

    job_id = uuid.uuid4().hex
    user = getattr(request.state, 'user', {})
    logger.info("[PROCESS] Received file for job %s user=%s filename=%s", job_id, user.get('user_id'), file.filename)

    # save file
    suffix = Path(file.filename).suffix or ''
    out_path = UPLOAD_DIR / f"{job_id}{suffix}"
    try:
        contents = await file.read()
        with open(out_path, 'wb') as f:
            f.write(contents)
    except Exception as e:
        logger.exception("[PROCESS] Failed to save uploaded file: %s", e)
        record_job_failure(user.get('api_key'))
        raise HTTPException(status_code=500, detail='Failed to save uploaded file')

    create_job(job_id)
    update_job(
        job_id,
        api_key=user.get('api_key'),
        user={'user_id': user.get('user_id'), 'email': user.get('email')}
    )

    # Use default cost_per_hour if not provided
    final_cost_per_hour = cost_per_hour if cost_per_hour is not None else 100.0

    # Launch background task
    asyncio.create_task(process_job(job_id, str(out_path), final_cost_per_hour))

    return {
        "job_id": job_id,
        "status": "queued"
    }


# ── New pipeline endpoints (under sub-router with /process prefix) ─


@process_pipeline_router.post(
    "/upload",
    response_model=ProcessUploadResponse,
    summary="Upload a tender document for processing",
    description=(
        "Upload a tender document (PDF, DOCX, or TXT). "
        "The file is validated, stored, and a background processing pipeline is started. "
        "Returns a job_id that can be used to poll status and retrieve results. "
        "Authentication is required."
    ),
)
async def process_upload(
    file: UploadFile = File(..., description="Tender document file (PDF, DOCX, or TXT)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a tender document for async processing.

    - **file**: PDF, DOCX, or TXT file (required)
    - **current_user**: Authenticated user
    - **Returns**: `job_id` for status polling and result retrieval
    """
    # ── Step 1: Basic validation ────────────────────────────────────
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided.",
        )

    # ── Step 2: Sanitise filename ───────────────────────────────────
    original_name = _sanitise_filename(file.filename)
    if original_name != file.filename:
        logger.info("[UPLOAD] Sanitised filename: %s -> %s", file.filename, original_name)

    # ── Step 3: Path traversal check ────────────────────────────────
    if ".." in file.filename or "/" in file.filename.replace("\\", "/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    # ── Step 4: Extension validation ────────────────────────────────
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # ── Read file contents ──────────────────────────────────────────
    job_id = uuid.uuid4().hex
    safe_filename = f"{job_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    user_email = current_user.get("email", "unknown")

    try:
        contents = await file.read()

        # ── Step 5: File size check ─────────────────────────────────
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB.",
            )

        # ── Step 6: Executable detection (before any signature check) ──
        if _is_executable(contents):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Executable files are not allowed.",
            )

        # ── Step 7: File signature validation ───────────────────────
        sig_valid, sig_error = _validate_file_signature(contents, ext)
        if not sig_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=sig_error,
            )

        # ── Step 8: MIME type detection & cross-check ───────────────
        mime_type = _detect_mime_from_bytes(contents, ext)
        if not _mime_matches_extension(mime_type, ext):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"MIME type mismatch: declared extension '{ext}' "
                       f"does not match detected content type '{mime_type}'.",
            )

        # ── Step 9: Binary content detection for TXT ────────────────
        if ext == ".txt" and _is_binary_content(contents):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Binary files are not allowed as .txt.",
            )

        # ── Compute SHA256 hash ─────────────────────────────────────
        import hashlib
        file_hash = hashlib.sha256(contents).hexdigest()

        # ── Duplicate detection ─────────────────────────────────────
        existing_job = await _check_duplicate(file_hash)
        if existing_job:
            logger.info(
                "[UPLOAD] Duplicate detected: hash=%s existing=%s new=%s",
                file_hash, existing_job, job_id,
            )

        with open(file_path, "wb") as f:
            f.write(contents)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[UPLOAD] Failed to save file: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file.",
        )

    # ── Create DB job record ────────────────────────────────────────
    try:
        await _create_job(
            job_id=job_id,
            user_id=user_email,
            filename=safe_filename,
            original_name=original_name,
        )
        await _create_tender_record(
            job_id=job_id,
            user_id=user_email,
            filename=safe_filename,
            original_filename=original_name,
            file_hash=file_hash,
            mime_type=mime_type,
            file_size=len(contents),
        )
    except Exception as e:
        logger.exception("[UPLOAD] Failed to create DB records: %s", e)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job record.",
        )

    # ── Log duplicate warning ───────────────────────────────────────
    warnings_list = []
    if existing_job:
        warnings_list.append(f"Duplicate file detected. Previously uploaded as job {existing_job}")

    # ── Launch background pipeline ──────────────────────────────────
    asyncio.create_task(
        run_pipeline(
            job_id, file_path, original_name, user_email,
            file_hash=file_hash, mime_type=mime_type, file_size=len(contents),
        )
    )

    response = ProcessUploadResponse(
        job_id=job_id,
        status="queued",
        filename=original_name,
        message="File uploaded and queued for processing",
    )
    if warnings_list:
        response.message += f" Warnings: {'; '.join(warnings_list)}"

    return response


@process_pipeline_router.get(
    "/status/{job_id}",
    response_model=ProcessingJobStatus,
    summary="Get processing job status",
    description="Check the current status of a processing job by its job_id. Supports both authenticated and anonymous access.",
)
async def process_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Poll job status by job_id.

    - **job_id**: UUID4 hex string returned from POST /api/process/upload
    - **current_user**: Authenticated user
    - **Returns**: Current status (queued, processing, extracting, boq_analysis, pricing, completed, failed)
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, progress, created_at, updated_at, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        return ProcessingJobStatus(
            job_id=job["job_id"],
            status=job["status"],
            progress=job["progress"],
            created_at=job["created_at"],
            updated_at=job["updated_at"],
            error_message=job["error_message"],
        )
    finally:
        await close_db(db)


@process_pipeline_router.get(
    "/audit/{job_id}",
    summary="Get Processing Audit Log",
    description=(
        "Retrieve the complete permanent audit log for a processing job. "
        "Returns every stage with timestamp, status, duration, confidence, "
        "warnings, and errors. Failures are NEVER hidden — they are recorded "
        "with explicit reasons. This is a core transparency feature."
    ),
)
async def process_audit_log(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve the complete Processing Audit Log for a job.

    The audit log is a permanent record of every processing stage:
      - upload_received
      - pdf_fingerprint
      - ocr_completed
      - document_classification
      - jurisdiction_detection
      - language_detection
      - currency_detection
      - tender_metadata_extraction
      - boq_extraction
      - pricing_completed
      - workforce_estimation
      - schedule_extraction
      - submission_letter_generation
      - readiness_assessment
      - audit_report_generation
      - result_committed
      - processing_complete

    Each stage includes:
      - timestamp, status (success/warning/failed)
      - duration_ms, confidence, source_module
      - warnings, errors, details

    Returns 404 if the job doesn't exist.
    Returns 200 with audit log (may be empty if job just started).
    """
    from ..services.audit_log_service import get_audit_summary

    # Verify job exists
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )
    finally:
        await close_db(db)

    # Get audit log
    try:
        audit_data = await get_audit_summary(job_id)
        logger.info(
            "[AUDIT] Audit log retrieved for job %s: %d stages, %d failed",
            job_id, audit_data["total_stages"], audit_data["failed"],
        )
        return audit_data
    except Exception as e:
        logger.exception("[AUDIT] Failed to retrieve audit log for job %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve audit log: {e}",
        )


@process_pipeline_router.post(
    "/export/package/{job_id}",
    summary="Generate Submission Package PDF",
    description=(
        "Generate a comprehensive Submission Package PDF containing all sections: "
        "Cover Page, Executive Summary, BOQ Summary, Pricing Summary, "
        "Compliance Checklist, and Submission Checklist. "
        "Accepts optional company_name and company_address overrides in the request body. "
        "The individual submission letter endpoint still works independently."
    ),
)
async def process_export_package(
    job_id: str,
    body: Optional[dict] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a comprehensive Submission Package PDF.

    Sections:
      1. Cover Page
      2. Executive Summary
      3. BOQ Summary
      4. Pricing Summary
      5. Compliance Checklist
      6. Submission Checklist

    Request body (optional JSON):
      - **company_name**: Optional override for company name
      - **company_address**: Optional override for company address

    Returns a streaming .pdf file download.
    Returns 404 if the job doesn't exist or has no result data.
    Returns 400 if the job is still processing.
    """
    from fastapi.responses import StreamingResponse

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, original_name, result_json, "
            "retry_count, retry_data_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        # ── Blocked: still processing ──────────────────────────────
        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot generate submission package while job is {job_status}. "
                       f"Wait for processing to complete.",
            )

        # ── Load result data ───────────────────────────────────────
        result_json = job.get("result_json")
        if not result_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result data available for job '{job_id}'.",
            )

        try:
            result_dict = json.loads(result_json)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Corrupt result data: {e}",
            )

        # ── Inject metadata ────────────────────────────────────────
        result_dict["job_id"] = job_id
        result_dict["filename"] = job.get("original_name") or job.get("filename")
        result_dict["status"] = job_status

        # ── Extract optional overrides from request body ───────────
        company_name_override = None
        company_address_override = None
        if body:
            company_name_override = body.get("company_name")
            company_address_override = body.get("company_address")

        # ── Generate submission package PDF ────────────────────────
        try:
            output = generate_submission_package(
                job_id,
                result_dict,
                company_name_override=company_name_override,
                company_address_override=company_address_override,
            )
        except Exception as e:
            logger.exception("[PACKAGE] Failed to generate submission package for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate submission package: {e}",
            )

        # ── Determine filename ─────────────────────────────────────
        filename = job.get("original_name") or job.get("filename") or job_id
        base_name = os.path.splitext(filename)[0]
        safe_base = re.sub(r"[^a-zA-Z0-9\-_]", "_", base_name)[:80]
        export_filename = f"Submission_Package_{safe_base}.pdf"

        logger.info(
            "[PACKAGE] Submission package generated for job %s — filename=%s",
            job_id, export_filename,
        )

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Content-Type": "application/pdf",
            },
        )

    finally:
        await close_db(db)


@process_pipeline_router.post(
    "/export/package-zip/{job_id}",
    summary="Generate Submission Package ZIP",
    description=(
        "Generate a ZIP file containing the complete Submission Package and "
        "all individual documents: Submission_Package.pdf, Submission_Letter.pdf, "
        "BOQ_Summary.pdf, Pricing_Summary.pdf, Compliance_Checklist.pdf, "
        "and Submission_Checklist.pdf. "
        "Accepts optional company_name and company_address overrides in the request body."
    ),
)
async def process_export_package_zip(
    job_id: str,
    body: Optional[dict] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a ZIP file with all submission package documents.

    Contents:
      - Submission_Package.pdf   (comprehensive package with all sections)
      - Submission_Letter.pdf    (individual submission letter)
      - BOQ_Summary.pdf          (BOQ summary document)
      - Pricing_Summary.pdf      (pricing breakdown document)
      - Compliance_Checklist.pdf (compliance checklist document)
      - Submission_Checklist.pdf (submission checklist document)
      - README.txt               (package contents description)

    Request body (optional JSON):
      - **company_name**: Optional override for company name
      - **company_address**: Optional override for company address

    Returns a streaming .zip file download.
    Returns 404 if the job doesn't exist or has no result data.
    Returns 400 if the job is still processing.
    """
    from fastapi.responses import StreamingResponse

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, original_name, result_json, "
            "retry_count, retry_data_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        # ── Blocked: still processing ──────────────────────────────
        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot generate submission package while job is {job_status}. "
                       f"Wait for processing to complete.",
            )

        # ── Load result data ───────────────────────────────────────
        result_json = job.get("result_json")
        if not result_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result data available for job '{job_id}'.",
            )

        try:
            result_dict = json.loads(result_json)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Corrupt result data: {e}",
            )

        # ── Inject metadata ────────────────────────────────────────
        result_dict["job_id"] = job_id
        result_dict["filename"] = job.get("original_name") or job.get("filename")
        result_dict["status"] = job_status

        # ── Extract optional overrides from request body ───────────
        company_name_override = None
        company_address_override = None
        if body:
            company_name_override = body.get("company_name")
            company_address_override = body.get("company_address")

        # ── Generate submission package ZIP ────────────────────────
        try:
            output = generate_submission_package_zip(
                job_id,
                result_dict,
                company_name_override=company_name_override,
                company_address_override=company_address_override,
            )
        except Exception as e:
            logger.exception("[PACKAGE] Failed to generate submission package ZIP for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate submission package ZIP: {e}",
            )

        # ── Determine filename ─────────────────────────────────────
        filename = job.get("original_name") or job.get("filename") or job_id
        base_name = os.path.splitext(filename)[0]
        safe_base = re.sub(r"[^a-zA-Z0-9\-_]", "_", base_name)[:80]
        export_filename = f"Submission_Package_{safe_base}.zip"

        logger.info(
            "[PACKAGE] Submission package ZIP generated for job %s — filename=%s",
            job_id, export_filename,
        )

        return StreamingResponse(
            output,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Content-Type": "application/zip",
            },
        )

    finally:
        await close_db(db)


@process_pipeline_router.get(
    "/readiness/{job_id}",
    summary="Get Tender Readiness Report",
    description=(
        "Generate a comprehensive Tender Readiness Report from a processing result. "
        "Includes readiness score (0–100), missing information detection, "
        "missing documents detection, confidence summary, risk summary, "
        "actionable recommendations, and dashboard integration payload. "
        "Supports both authenticated and anonymous access."
    ),
)
async def process_readiness(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a Tender Readiness Report for a completed processing job.

    Report sections:
      1. Readiness Score (0–100) with category breakdown
      2. Missing Information Detection
      3. Missing Documents Detection
      4. Confidence Summary
      5. Risk Summary
      6. Actionable Recommendations
      7. Dashboard Integration Payload

    Returns a JSON readiness report.
    Returns 404 if the job doesn't exist or has no result data.
    Returns 400 if the job is still processing.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, original_name, result_json, "
            "retry_count, retry_data_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        # ── Blocked: still processing ──────────────────────────────
        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot generate readiness report while job is {job_status}. "
                       f"Wait for processing to complete.",
            )

        # ── Load result data ───────────────────────────────────────
        result_json = job.get("result_json")
        if not result_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result data available for job '{job_id}'.",
            )

        try:
            result_dict = json.loads(result_json)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Corrupt result data: {e}",
            )

        # ── Inject metadata ────────────────────────────────────────
        result_dict["job_id"] = job_id
        result_dict["filename"] = job.get("original_name") or job.get("filename")
        result_dict["status"] = job_status

        # Add retry metadata
        retry_count = job.get("retry_count") or 0
        retry_data_json = job.get("retry_data_json")
        retry_metadata = {}
        if retry_data_json:
            try:
                retry_metadata = json.loads(retry_data_json)
            except (json.JSONDecodeError, TypeError):
                pass
        retry_metadata["retry_count"] = retry_count
        result_dict["retry_metadata"] = retry_metadata

        # ── Generate readiness report ──────────────────────────────
        try:
            report = build_readiness_report(result_dict)
        except Exception as e:
            logger.exception("[READINESS] Failed to generate report for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate readiness report: {e}",
            )

        # ── Inject missing counts into dashboard payload ───────────
        missing_info = report.get("missing_information", {})
        missing_docs = report.get("missing_documents", {})
        if "dashboard" in report:
            report["dashboard"]["missing_fields_count"] = missing_info.get("count", 0)
            report["dashboard"]["missing_documents_count"] = missing_docs.get("missing_count", 0)

        logger.info(
            "[READINESS] Report generated for job %s — score=%.1f",
            job_id, report.get("readiness_score", {}).get("overall_score", 0),
        )

        return report

    finally:
        await close_db(db)


@process_pipeline_router.get(
    "/export/readiness/{job_id}",
    summary="Export Tender Readiness Assessment PDF",
    description=(
        "Generate a professional Tender Readiness Assessment PDF from a processing result. "
        "Includes Overall Status, Verification Summary, Manual Review Required, "
        "Missing Supporting Documents checklist, Risk Assessment, and Recommendations. "
        "Every status, recommendation and assessment is derived only from verified "
        "extraction results and deterministic business rules. "
        "Supports both authenticated and anonymous access."
    ),
)
async def process_export_readiness(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Export a Tender Readiness Assessment as a professional PDF.

    Sections:
      1. Overall Status — Ready for Submission / Ready with Minor Actions /
         Manual Review Required / Submission Not Ready
      2. Verification Summary — ✓/✗ for Project, Tender Ref, BOQ, Pricing, etc.
      3. Manual Review Required — Fields requiring user attention
      4. Missing Supporting Documents — Checklist of common tender docs
      5. Risk Assessment — Low / Medium / High with deterministic explanations
      6. Recommendations — Practical actions based on verified findings

    Returns a streaming .pdf file download.
    Returns 404 if the job doesn't exist or has no result data.
    Returns 400 if the job is still processing.
    """
    from fastapi.responses import StreamingResponse

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, original_name, result_json, "
            "retry_count, retry_data_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        # ── Blocked: still processing ──────────────────────────────
        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot generate readiness assessment while job is {job_status}. "
                       f"Wait for processing to complete.",
            )

        # ── Load result data ───────────────────────────────────────
        result_json = job.get("result_json")
        if not result_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result data available for job '{job_id}'.",
            )

        try:
            result_dict = json.loads(result_json)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Corrupt result data: {e}",
            )

        # ── Inject metadata ────────────────────────────────────────
        result_dict["job_id"] = job_id
        result_dict["filename"] = job.get("original_name") or job.get("filename")
        result_dict["status"] = job_status

        # ── Generate readiness PDF ─────────────────────────────────
        try:
            output = generate_readiness_pdf(job_id, result_dict)
        except Exception as e:
            logger.exception("[READINESS] Failed to generate PDF for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate readiness assessment PDF: {e}",
            )

        # ── Determine filename ─────────────────────────────────────
        filename = job.get("original_name") or job.get("filename") or job_id
        base_name = os.path.splitext(filename)[0]
        safe_base = re.sub(r"[^a-zA-Z0-9\-_]", "_", base_name)[:80]
        export_filename = f"Tender_Readiness_Assessment_{safe_base}.pdf"

        logger.info(
            "[READINESS] PDF assessment generated for job %s — filename=%s",
            job_id, export_filename,
        )

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Content-Type": "application/pdf",
            },
        )

    finally:
        await close_db(db)


@process_pipeline_router.post(
    "/{job_id}/upload-missing-document",
    summary="Upload a missing document for a job",
    description="Upload a missing supporting document (e.g. SBD form, tax clearance) directly to the job's uploads folder and trigger a re-readiness check.",
)
async def upload_missing_document(
    job_id: str,
    file: UploadFile = File(..., description="The missing document file (PDF, DOCX, or TXT)"),
    document_id: str = Form(..., description="The document type ID (e.g. 'sbd2', 'tax_clearance')"),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a missing supporting document for a given processing job.

    The document is saved to storage/uploads/{job_id}/ and the readiness
    check can be re-run to update the report.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    try:
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large (max 50 MB).")
        if _is_executable(contents):
            raise HTTPException(status_code=400, detail="Executable files are not allowed.")
        sig_valid, sig_error = _validate_file_signature(contents, ext)
        if not sig_valid:
            raise HTTPException(status_code=400, detail=sig_error)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

    job_upload_dir = UPLOAD_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"{document_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = job_upload_dir / safe_filename
    try:
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    logger.info(
        "[UPLOAD-MISSING] Document uploaded for job %s: doc_id=%s, filename=%s",
        job_id, document_id, safe_filename,
    )

    return {
        "status": "uploaded",
        "job_id": job_id,
        "document_id": document_id,
        "filename": safe_filename,
        "message": f"'{file.filename}' uploaded as {document_id}. Re-run readiness check to update report.",
    }


@process_pipeline_router.post(
    "/export/letter/{job_id}",
    summary="Generate Submission Letter",
    description=(
        "Generate a professional submission letter PDF for a completed processing job. "
        "Extracts project name, tender number, and company details from the result data. "
        "Accepts optional company_name and company_address overrides in the request body. "
        "Template identifier: submission_v1."
    ),
)
async def process_export_letter(
    job_id: str,
    body: Optional[dict] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a Submission Letter PDF for a processing job.

    Request body (optional JSON):
      - **template**: Template identifier (default: "submission_v1")
      - **company_name**: Optional override for company name
      - **company_address**: Optional override for company address

    Returns a streaming .pdf file download.
    Returns 404 if the job doesn't exist or has no result data.
    Returns 400 if the job is still processing.
    """
    from fastapi.responses import StreamingResponse

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, original_name, result_json, "
            "retry_count, retry_data_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        # ── Blocked: still processing ──────────────────────────────
        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot generate submission letter while job is {job_status}. "
                       f"Wait for processing to complete.",
            )

        # ── Load result data ───────────────────────────────────────
        result_json = job.get("result_json")
        if not result_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result data available for job '{job_id}'.",
            )

        try:
            result_dict = json.loads(result_json)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Corrupt result data: {e}",
            )

        # ── Extract optional overrides from request body ───────────
        company_name_override = None
        company_address_override = None
        if body:
            company_name_override = body.get("company_name")
            company_address_override = body.get("company_address")

        # ── Generate submission letter PDF ─────────────────────────
        try:
            output = generate_submission_letter(
                job_id,
                result_dict,
                company_name_override=company_name_override,
                company_address_override=company_address_override,
            )
        except Exception as e:
            logger.exception("[EXPORT] Failed to generate submission letter for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate submission letter: {e}",
            )

        # ── Determine filename ─────────────────────────────────────
        filename = job.get("original_name") or job.get("filename") or job_id
        base_name = os.path.splitext(filename)[0]
        safe_base = re.sub(r"[^a-zA-Z0-9\-_]", "_", base_name)[:80]
        export_filename = f"Submission_Letter_{safe_base}.pdf"

        logger.info(
            "[EXPORT] Submission letter generated for job %s — filename=%s",
            job_id, export_filename,
        )

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Content-Type": "application/pdf",
            },
        )

    finally:
        await close_db(db)


@process_pipeline_router.get(
    "/export/pdf/{job_id}",
    summary="Export processing result as PDF report",
    description=(
        "Generate a professional client-ready PDF report from a processing result. "
        "Includes cover page, executive summary, key insights, pricing breakdown, "
        "workforce analysis, and risks/warnings.  All confidence levels, "
        "warnings, and data gaps are honestly presented. Supports both authenticated and anonymous access."
    ),
)
async def process_export_pdf(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Export processing result as a professional PDF report.

    Sections:
      1. Cover Page — Tender filename, job ID, sector, location, date
      2. Executive Summary — Total value, duration, workforce, confidence
      3. Key Insights — BOQ count, categories, OCR usage, missing data
      4. Pricing Summary — Full pricing breakdown with method & assumptions
      5. Workforce Summary — Workers by category with confidence
      6. Risks & Warnings — Warnings, failed stages, retry info

    Returns a streaming .pdf file download.
    Returns 404 if the job doesn't exist or has no result data.
    Returns 400 if the job is still processing.
    """
    from fastapi.responses import StreamingResponse

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, original_name, result_json, "
            "retry_count, retry_data_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        # ── Blocked: still processing ──────────────────────────────
        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot export PDF while job is {job_status}. "
                       f"Wait for processing to complete.",
            )

        # ── Load result data ───────────────────────────────────────
        result_json = job.get("result_json")
        if not result_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result data available for job '{job_id}'.",
            )

        try:
            result_dict = json.loads(result_json)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Corrupt result data: {e}",
            )

        # ── Inject retry metadata into result dict for report ──────
        retry_count = job.get("retry_count") or 0
        retry_data_json = job.get("retry_data_json")
        retry_metadata = {}
        if retry_data_json:
            try:
                retry_metadata = json.loads(retry_data_json)
            except (json.JSONDecodeError, TypeError):
                pass
        retry_metadata["retry_count"] = retry_count
        result_dict["retry_metadata"] = retry_metadata

        # ── Generate PDF report ─────────────────────────────────────
        try:
            output = generate_pdf_report(job_id, result_dict)
        except Exception as e:
            logger.exception("[EXPORT] Failed to generate PDF for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate PDF report: {e}",
            )

        # ── Determine filename ─────────────────────────────────────
        filename = job.get("original_name") or job.get("filename") or job_id
        base_name = os.path.splitext(filename)[0]
        safe_base = re.sub(r"[^a-zA-Z0-9\-_]", "_", base_name)[:80]
        export_filename = f"{safe_base}_tender_report.pdf"

        logger.info(
            "[EXPORT] PDF report generated for job %s — filename=%s",
            job_id, export_filename,
        )

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Content-Type": "application/pdf",
            },
        )

    finally:
        await close_db(db)


@process_pipeline_router.get(
    "/history",
    response_model=list[ProcessingHistoryItem],
    summary="Get processing history",
    description=(
        "Return all processing jobs for the current user (or all anonymous jobs if not authenticated). "
        "Ordered newest first. Enriches each job with lightweight summary "
        "data (sector, confidence, warnings count, pricing availability) "
        "from the tender_results table. Gracefully handles missing or "
        "partial records — never crashes. Supports both authenticated and anonymous access."
    ),
)
async def process_history(
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve processing history.

    For authenticated users: Returns their processing history.
    For anonymous users: Returns history for jobs submitted anonymously.

    Returns a list of ProcessingHistoryItem objects sorted by
    created_at descending (newest first).  Each item includes:
      - job_id, filename, status
      - created_at, updated_at
      - sector, confidence (from tender_results if available)
      - warnings_count, has_pricing (enriched from results)

    Resilience:
      - Never crashes on partial/corrupt records
      - Missing fields get safe defaults
      - Statuses preserved honestly (partial_success, failed, etc.)
    """
    user_email = current_user.get("email", current_user.get("user_id", "")) if current_user else "anonymous"
    start_time = __import__("time").time()

    db = await get_db()
    try:
        # Query processing_jobs for history, left join with tender_results for enrichment
        cursor = await db.execute(
            """SELECT
                pj.job_id,
                pj.filename,
                pj.original_name,
                pj.status,
                pj.created_at,
                pj.updated_at,
                pj.error_message,
                tr.sector,
                tr.sector_confidence,
                tr.warnings_json,
                tr.pricing_json
               FROM processing_jobs pj
               LEFT JOIN tender_results tr ON tr.tender_id = pj.job_id
               WHERE pj.user_id = ?
               ORDER BY pj.created_at DESC""",
            (user_email,),
        )
        rows = await cursor.fetchall()

        history_items: list[ProcessingHistoryItem] = []
        for row in rows:
            job = dict(row)
            try:
                # Parse warnings count from warnings_json
                warnings_count = 0
                warnings_raw = job.get("warnings_json")
                if warnings_raw:
                    try:
                        parsed_warnings = json.loads(warnings_raw)
                        if isinstance(parsed_warnings, list):
                            warnings_count = len(parsed_warnings)
                        elif isinstance(parsed_warnings, dict):
                            warnings_count = len(parsed_warnings)
                    except (json.JSONDecodeError, TypeError):
                        # Gracefully handle corrupt warning data
                        logger.warning("[HISTORY] Job %s has unparseable warnings_json", job.get("job_id"))

                # Determine if pricing data exists
                has_pricing = False
                pricing_raw = job.get("pricing_json")
                if pricing_raw:
                    try:
                        parsed_pricing = json.loads(pricing_raw)
                        has_pricing = parsed_pricing is not None and bool(parsed_pricing)
                    except (json.JSONDecodeError, TypeError):
                        # Gracefully handle corrupt pricing data
                        logger.warning("[HISTORY] Job %s has unparseable pricing_json", job.get("job_id"))

                # Log missing sector as a debug hint
                sector = job.get("sector")
                if not sector:
                    logger.debug("[HISTORY] Job %s missing sector field", job.get("job_id"))

                # Use original_name if available, fallback to filename
                filename = job.get("original_name") or job.get("filename")

                item = ProcessingHistoryItem(
                    job_id=job.get("job_id", ""),
                    filename=filename,
                    status=job.get("status", "unknown"),
                    created_at=job.get("created_at"),
                    updated_at=job.get("updated_at"),
                    sector=sector,
                    confidence=job.get("sector_confidence"),
                    warnings_count=warnings_count,
                    has_pricing=has_pricing,
                    error_message=job.get("error_message"),
                )
                history_items.append(item)
            except Exception as e:
                # Never crash on a single corrupt record — log and skip it
                logger.warning("[HISTORY] Skipping corrupt job record %s: %s",
                               job.get("job_id", "unknown"), e)
                continue

        elapsed_ms = int((__import__("time").time() - start_time) * 1000)
        logger.info("[HISTORY] Returning %d jobs for user %s in %d ms",
                    len(history_items), user_email, elapsed_ms)

        return history_items

    finally:
        await close_db(db)


@process_pipeline_router.get(
    "/result/{job_id}",
    response_model=ProcessingResult,
    summary="Get processing job result",
    description=(
        "Retrieve the full processing result for a completed or partial_success job. "
        "Returns all successfully extracted data (sector, duration, workforce, "
        "locations, BOQ items, etc.) even if some stages failed. "
        "Failed jobs return a structured failure response with error details. "
        "Supports both authenticated and anonymous access."
    ),
)
async def process_result(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve the full processing result by job_id.

    Allowed statuses:
      - `completed`:      Return full result with all stages
      - `partial_success`: Return partial result with completed/failed stage lists
      - `failed`:          Return structured failure response

    Blocked statuses:
      - `queued`, `processing` → 200 with status detail message
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, result_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        # ── Blocked: still processing ──────────────────────────────
        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_200_OK,
                detail=f"Job is still {job_status}. Poll GET /api/process/status/{job_id} for updates.",
            )

        # ── Failed: structured failure response ─────────────────────
        if job_status == "failed":
            error_msg = job.get("error_message", "Unknown pipeline error")
            if error_msg:
                logger.warning("[RESULT] Returning failed result for %s: %s",
                               job_id, error_msg)
            return ProcessingResult(
                job_id=job["job_id"],
                status="failed",
                filename=job.get("filename"),
                warnings=[error_msg] if error_msg else [],
            )

        # ── Allowed: completed / partial_success ───────────────────
        if job_status not in ("completed", "partial_success"):
            raise HTTPException(
                status_code=status.HTTP_200_OK,
                detail=f"Job is in unexpected state '{job_status}'.",
            )

        if not job.get("result_json"):
            logger.error("[RESULT] %s job '%s' has no result_json stored",
                         job_status, job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Job is marked {job_status} but no result data was stored.",
            )

        # ── Parse stored JSON result ───────────────────────────────
        try:
            result_dict = json.loads(job["result_json"])
        except (json.JSONDecodeError, TypeError) as e:
            logger.exception("[RESULT] Failed to parse result_json for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse stored result: {e}",
            )

        # ── Override stored status with actual DB job status ────────
        # The pipeline may have stored "completed" in result_json before
        # it determined the final status was "partial_success".  The DB
        # job status is the source of truth.
        result_dict["status"] = job_status

        # ── Ensure evidence shape is always present ────────────────
        if not isinstance(result_dict.get("evidence"), dict):
            result_dict["evidence"] = {
                "fields": {},
                "generated_from_existing_extractions": True,
                "version": "v1",
            }

        # ── Inject pricing_status from pricing_result ─────────────
        if job_status == "partial_success" and result_dict.get("pricing_result") is None:
            result_dict["pricing_status"] = "failed"
            result_dict["pricing_unavailable_reason"] = (
                "Pricing could not be calculated due to missing or insufficient data."
            )
        elif result_dict.get("pricing_result") is not None:
            result_dict["pricing_status"] = "completed"
        else:
            result_dict["pricing_status"] = result_dict.get("pricing_status", None)

        # ── Build completed_stages / failed_stages ─────────────────
        result_dict["completed_stages"] = result_dict.get("completed_stages", [])
        result_dict["failed_stages"] = result_dict.get("failed_stages", [])

        if not result_dict["completed_stages"]:
            inferred_completed = []
            inferred_failed = []
            stage_map = [
                ("metadata", lambda r: bool(r.get("metadata"))),
                ("text_extraction", lambda r: r.get("full_text") is not None),
                ("entity_extraction", lambda r: r.get("detected_sector") is not None),
                ("boq_analysis", lambda r: bool(r.get("boq_items"))),
                ("pricing_calculation", lambda r: r.get("pricing_result") is not None),
            ]
            for stage_name, checker in stage_map:
                if checker(result_dict):
                    inferred_completed.append(stage_name)
                else:
                    inferred_failed.append(stage_name)
            inferred_completed.append("finalisation")
            result_dict["completed_stages"] = inferred_completed
            result_dict["failed_stages"] = inferred_failed

        # ── Validation guard: status MUST match stage results ───────
        # If failed_stages is non-empty, status cannot be "completed"
        if result_dict["failed_stages"] and result_dict["status"] == "completed":
            logger.warning("[STATUS] Corrected inconsistent completed state "
                           "to partial_success for job %s: failed_stages=%s",
                           job_id, result_dict["failed_stages"])
            result_dict["status"] = "partial_success"

        # ── Log explicit return type ───────────────────────────────
        if job_status == "partial_success":
            logger.info("[RESULT] Returning partial_success result for job_id=%s: "
                        "pricing_result=%s, completed=%s, failed=%s",
                        job_id,
                        "present" if result_dict.get("pricing_result") else "absent",
                        result_dict.get("completed_stages"),
                        result_dict.get("failed_stages"))

        logger.info("[RESULT] Returning %s result for job %s: "
                    "completed_stages=%s, failed_stages=%s",
                    result_dict["status"], job_id,
                    result_dict.get("completed_stages"),
                    result_dict.get("failed_stages"))

        return ProcessingResult(**result_dict)

    finally:
        await close_db(db)


@process_pipeline_router.get(
    "/export/csv/{job_id}",
    summary="Export processing result as CSV",
    description=(
        "Generate a downloadable .csv file from a processing result. "
        "Includes BOQ items, pricing summary, workforce analysis, and warnings. "
        "Supports both authenticated and anonymous access."
    ),
)
async def process_export_csv(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Export processing result as a CSV file.

    Sections:
      1. Header — Job ID, filename, status
      2. BOQ Items — Extracted line items with quantities, rates, amounts
      3. Pricing Summary — Pricing breakdown (labour, materials, VAT, etc.)
      4. Workforce — Workforce requirements with categories
      5. Warnings — Pipeline warnings, failed stages

    Returns a streaming .csv file download.
    Returns 404 if the job doesn't exist or has no result data.
    Returns 400 if the job is still processing.
    """
    from fastapi.responses import StreamingResponse

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, original_name, result_json, "
            "retry_count, retry_data_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        # ── Blocked: still processing ──────────────────────────────
        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot export CSV while job is {job_status}. "
                       f"Wait for processing to complete.",
            )

        # ── Load result data ───────────────────────────────────────
        result_json = job.get("result_json")
        if not result_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result data available for job '{job_id}'.",
            )

        try:
            result_dict = json.loads(result_json)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Corrupt result data: {e}",
            )

        # ── Inject retry metadata into result dict for export ──────
        retry_count = job.get("retry_count") or 0
        retry_data_json = job.get("retry_data_json")
        retry_metadata = {}
        if retry_data_json:
            try:
                retry_metadata = json.loads(retry_data_json)
            except (json.JSONDecodeError, TypeError):
                pass
        retry_metadata["retry_count"] = retry_count
        result_dict["retry_metadata"] = retry_metadata

        # ── Generate CSV file ──────────────────────────────────────
        try:
            from ..services.export_service import generate_csv_export
            output = generate_csv_export(job_id, result_dict)
        except Exception as e:
            logger.exception("[EXPORT] Failed to generate CSV for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate CSV export: {e}",
            )

        # ── Determine filename ─────────────────────────────────────
        filename = job.get("original_name") or job.get("filename") or job_id
        base_name = os.path.splitext(filename)[0]
        safe_base = re.sub(r"[^a-zA-Z0-9\-_]", "_", base_name)[:80]
        export_filename = f"{safe_base}_tender_export.csv"

        logger.info(
            "[EXPORT] CSV export generated for job %s — filename=%s",
            job_id, export_filename,
        )

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Content-Type": "text/csv",
            },
        )

    finally:
        await close_db(db)


@process_pipeline_router.post(
    "/retry/{job_id}",
    response_model=RetryResponse,
    summary="Retry failed pipeline stages",
    description=(
        "Retry specific recoverable pipeline stages for a job WITHOUT "
        "requiring full document re-upload.  Reuses the existing uploaded "
        "file and preserves successful stages.  Dependencies are resolved "
        "automatically (e.g. retrying pricing_calculation will also retry "
        "boq_analysis and entity_extraction if needed)."
    ),
)
async def process_retry(
    job_id: str,
    body: RetryRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Retry specific recoverable pipeline stages for an existing job.

    Request body:
      - **stages**: List of stage names to retry.
        Valid: metadata_extraction, text_extraction, entity_extraction,
        boq_analysis, pricing_calculation.

    Rules:
      - Only works for jobs in 'partial_success', 'failed', or 'completed' status
      - Dependencies are resolved automatically
      - Original uploaded file is reused (no re-upload needed)
      - Successful stages are preserved (not re-executed unless required as deps)
      - Retry count and retried stages are tracked in the database
      - Original job history is preserved — retry creates a new result overlay

    Logging:
      [RETRY] Retrying <stage> for job <id>
      [RETRY] Dependency <stage> included automatically
      [RETRY] Retry completed: <status>
      [RETRY] Retry rejected: <reason>
    """
    from ..services.retry_pipeline import run_retry_pipeline

    # ── Validate requested stages ─────────────────────────────────────
    if not body.stages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No stages provided for retry. At least one stage is required.",
        )

    invalid_stages = [
        s for s in body.stages
        if s not in ("metadata_extraction", "text_extraction", "entity_extraction",
                     "boq_analysis", "pricing_calculation")
    ]
    if invalid_stages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage(s): {', '.join(invalid_stages)}. "
                   f"Valid stages: metadata_extraction, text_extraction, "
                   f"entity_extraction, boq_analysis, pricing_calculation.",
        )

    # ── Execute retry pipeline in background task ─────────────────────
    # The retry is run synchronously within the request because it's fast
    # (reuses existing data).  For long-running retries (text_extraction
    # with OCR), this could be moved to a background task if needed.
    try:
        logger.info("[RETRY] Retrying stages %s for job %s (user=%s)",
                     body.stages, job_id, current_user.get("email", "unknown"))

        result = await run_retry_pipeline(job_id, body.stages)

        logger.info("[RETRY] Retry completed for job %s: status=%s, retry_count=%d",
                     job_id, result.get("status"), result.get("retry_count"))

        return RetryResponse(
            job_id=result["job_id"],
            status=result["status"],
            retry_count=result["retry_count"],
            retried_stages=result["retried_stages"],
            last_retry_at=result.get("last_retry_at"),
            stage_failures=result.get("stage_failures", []),
        )

    except ValueError as e:
        logger.warning("[RETRY] Retry rejected for job %s: %s", job_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except FileNotFoundError as e:
        logger.warning("[RETRY] Retry rejected for job %s: %s", job_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("[RETRY] Retry failed for job %s: %s", job_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retry failed: {str(e)}",
        )


@process_pipeline_router.get(
    "/export/excel/{job_id}",
    summary="Export processing result as Excel",
    description=(
        "Generate a downloadable .xlsx workbook from a processing result. "
        "Includes BOQ items, pricing summary, workforce analysis, and warnings. "
        "Unavailable data is clearly marked — no fabricated values. Supports both authenticated and anonymous access."
    ),
)
async def process_export_excel(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Export processing result as a structured Excel workbook.

    Sheets:
      1. BOQ Items — Extracted line items with quantities, rates, amounts
      2. Pricing Summary — Pricing breakdown (labour, materials, VAT, etc.)
      3. Workforce — Workforce requirements with categories
      4. Warnings — Pipeline warnings, failed stages, retry metadata

    Returns a streaming .xlsx file download.
    Returns 404 if the job doesn't exist or has no result data.
    Returns 400 if the job is still processing.
    """
    from fastapi.responses import StreamingResponse

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, original_name, result_json, "
            "retry_count, retry_data_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        # ── Blocked: still processing ──────────────────────────────
        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot export while job is {job_status}. "
                       f"Wait for processing to complete.",
            )

        # ── Load result data ───────────────────────────────────────
        result_json = job.get("result_json")
        if not result_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result data available for job '{job_id}'.",
            )

        try:
            result_dict = json.loads(result_json)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Corrupt result data: {e}",
            )

        # ── Inject retry metadata into result dict for export ──────
        retry_count = job.get("retry_count") or 0
        retry_data_json = job.get("retry_data_json")
        retry_metadata = {}
        if retry_data_json:
            try:
                retry_metadata = json.loads(retry_data_json)
            except (json.JSONDecodeError, TypeError):
                pass
        retry_metadata["retry_count"] = retry_count
        result_dict["retry_metadata"] = retry_metadata

        # ── Generate Excel workbook ────────────────────────────────
        try:
            output = generate_export(job_id, result_dict)
        except Exception as e:
            logger.exception("[EXPORT] Failed to generate Excel for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate Excel export: {e}",
            )

        # ── Determine filename ─────────────────────────────────────
        filename = job.get("original_name") or job.get("filename") or job_id
        base_name = os.path.splitext(filename)[0]
        safe_base = re.sub(r"[^a-zA-Z0-9\-_]", "_", base_name)[:80]
        export_filename = f"{safe_base}_tender_export.xlsx"

        logger.info(
            "[EXPORT] Excel export generated for job %s — filename=%s",
            job_id, export_filename,
        )

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        )

    finally:
        await close_db(db)


@process_pipeline_router.get(
    "/export/roadmap/{job_id}",
    summary="Export Bid Response Roadmap",
    description=(
        "Generate a clean, structured Bid Response Roadmap PDF that maps directly to the original tender. "
        "Includes Data Entry Schedule with manual entry placeholders for missing data. Clearly marked to be used with original tender documentation."
    ),
)
async def process_export_roadmap(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Export Bid Response Roadmap as a PDF document.

    Returns a streaming .pdf file download.
    Returns 404 if the job doesn't exist or has no result data.
    Returns 400 if the job is still processing.
    """
    from fastapi.responses import StreamingResponse

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, original_name, result_json, "
            "retry_count, retry_data_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot export while job is {job_status}. "
                       f"Wait for processing to complete.",
            )

        result_json = job.get("result_json")
        if not result_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result data available for job '{job_id}'.",
            )

        try:
            result_dict = json.loads(result_json)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Corrupt result data: {e}",
            )

        retry_count = job.get("retry_count") or 0
        retry_data_json = job.get("retry_data_json")
        retry_metadata = {}
        if retry_data_json:
            try:
                retry_metadata = json.loads(retry_data_json)
            except (json.JSONDecodeError, TypeError):
                pass
        retry_metadata["retry_count"] = retry_count
        result_dict["retry_metadata"] = retry_metadata

        try:
            output = generate_bid_response_roadmap(job_id, result_dict)
        except Exception as e:
            logger.exception("[EXPORT] Failed to generate Bid Response Roadmap for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate Bid Response Roadmap: {e}",
            )

        filename = job.get("original_name") or job.get("filename") or job_id
        base_name = os.path.splitext(filename)[0]
        safe_base = re.sub(r"[^a-zA-Z0-9\-_]", "_", base_name)[:80]
        export_filename = f"{safe_base}_bid_response_roadmap.pdf"

        logger.info(
            "[EXPORT] Bid Response Roadmap generated for job %s — filename=%s",
            job_id, export_filename,
        )

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Content-Type": "application/pdf",
            },
        )

    finally:
        await close_db(db)


@process_pipeline_router.get(
    "/export/audit/{job_id}",
    summary="Export Tender Integrity Audit",
    description=(
        "Generate an automated Tender Integrity Audit report that explains why reconstruction was necessary. "
        "Explicitly flags areas where the original document structure failed, links to confidence scores, and includes a risk assessment."
    ),
)
async def process_export_audit(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Export Tender Integrity Audit as a PDF document.

    Returns a streaming .pdf file download.
    Returns 404 if the job doesn't exist or has no result data.
    Returns 400 if the job is still processing.
    """
    from fastapi.responses import StreamingResponse

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT job_id, status, filename, original_name, result_json, "
            "retry_count, retry_data_json, error_message "
            "FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )

        job = dict(row)
        job_status = job["status"]

        if job_status in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot export while job is {job_status}. "
                       f"Wait for processing to complete.",
            )

        result_json = job.get("result_json")
        if not result_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No result data available for job '{job_id}'.",
            )

        try:
            result_dict = json.loads(result_json)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Corrupt result data: {e}",
            )

        retry_count = job.get("retry_count") or 0
        retry_data_json = job.get("retry_data_json")
        retry_metadata = {}
        if retry_data_json:
            try:
                retry_metadata = json.loads(retry_data_json)
            except (json.JSONDecodeError, TypeError):
                pass
        retry_metadata["retry_count"] = retry_count
        result_dict["retry_metadata"] = retry_metadata

        try:
            output = generate_tender_integrity_audit(job_id, result_dict)
        except Exception as e:
            logger.exception("[EXPORT] Failed to generate Tender Integrity Audit for job %s", job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate Tender Integrity Audit: {e}",
            )

        filename = job.get("original_name") or job.get("filename") or job_id
        base_name = os.path.splitext(filename)[0]
        safe_base = re.sub(r"[^a-zA-Z0-9\-_]", "_", base_name)[:80]
        export_filename = f"{safe_base}_tender_integrity_audit.pdf"

        logger.info(
            "[EXPORT] Tender Integrity Audit generated for job %s — filename=%s",
            job_id, export_filename,
        )

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{export_filename}"',
                "Content-Type": "application/pdf",
            },
        )

    finally:
        await close_db(db)
