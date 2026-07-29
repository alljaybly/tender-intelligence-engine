"""
BOQ extraction route: POST /api/extract/boq
Accepts a PDF file upload and returns structured BOQ line items.
"""
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from ..schemas.boq import BOQResult
from ..services.boq_engine_v2 import extract_from_pdf
from ..routes.auth import get_current_user

router = APIRouter(prefix="/extract", tags=["BOQ Extraction"])
logger = logging.getLogger(__name__)

# Temporary upload directory for BOQ PDFs
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf"}


@router.post(
    "/boq",
    response_model=BOQResult,
    summary="Extract Bill of Quantities (BOQ) from a PDF tender document",
    description=(
        "Upload a South African tender BOQ PDF and extract structured line items "
        "(item_no, description, quantity, unit, rate, amount). "
        "Uses pdfplumber first, then camelot as fallback, then heuristic text parsing. "
        "Returns extracted items, totals, extraction method, confidence level, and warnings."
    ),
)
async def extract_boq(
    file: UploadFile = File(..., description="PDF file containing the Bill of Quantities"),
    extract_totals: bool = Query(True, description="Whether to attempt extracting grand totals"),
    page_range: Optional[str] = Query(None, description="Page range, e.g. '1-3' or '1,3,5'"),
    current_user: dict = Depends(get_current_user),
):
    """
    Extract BOQ from uploaded PDF.

    - **file**: PDF file (required)
    - **extract_totals**: Whether to attempt extracting grand totals (default: true)
    - **page_range**: Optional page range, e.g. "1-3" or "1,3,5" (default: all pages)
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided.",
        )

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Only PDF files are accepted.",
        )

    logger.info(
        "[BOQ] Extraction request: file=%s, extract_totals=%s, page_range=%s, user=%s",
        file.filename, extract_totals, page_range,
        current_user.get("email", "unknown"),
    )

    # Save uploaded file to temporary location
    safe_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Run extraction
        result = extract_from_pdf(
            file_path=file_path,
            extract_totals=extract_totals,
            page_range=page_range,
        )

        logger.info(
            "[BOQ] Extraction complete: %d items, method=%s, confidence=%s",
            len(result.items), result.extraction_method, result.confidence,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[BOQ] Extraction error for %s: %s", file.filename, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract BOQ: {str(e)}",
        )
    finally:
        # Clean up uploaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.debug("[BOQ] Cleaned up temp file: %s", file_path)
            except OSError:
                logger.warning("[BOQ] Could not remove temp file: %s", file_path)