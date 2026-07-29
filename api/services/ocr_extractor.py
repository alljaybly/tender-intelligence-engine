"""
OCR Fallback Extractor — Extracts text from image-based/scanned PDFs.

Why OCR fallback exists:
  Some tender PDFs are scanned documents (images of pages) rather than
  text-based PDFs. Standard extractors like pdfplumber and camelot
  produce little to no output from these files.

When OCR triggers:
  1. Standard extraction (pdfplumber text) returns no meaningful text
  2. Standard extraction returns very low character count (<100 chars)
  3. Standard extraction returns whitespace-only text
  4. camelot reports image-based pages

How OCR works:
  1. Convert PDF pages to images using pdf2image (requires poppler-utils)
  2. Run Tesseract OCR (pytesseract) on each page image
  3. Combine extracted text with page markers
  4. Return structured result with confidence estimate

Confidence interpretation:
  - "High":   >2000 chars extracted, multiple pages
  - "Medium": 500-2000 chars or single page with good extraction
  - "Low":    <500 chars or significant errors

Dependencies:
  - Python: pytesseract, pdf2image, Pillow (already in requirements.txt)
  - System: tesseract-ocr, poppler-utils (must be installed separately)
    $ sudo apt-get install tesseract-ocr poppler-utils
"""
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Thresholds for triggering and scoring
MIN_TEXT_CHARS = 100          # If standard extraction yields less than this, try OCR
MAX_PAGES_FOR_OCR = 200       # Safety cap: refuse to OCR more than this many pages
OCR_CHUNK_PAGES = 10          # Process pages in chunks to manage memory
MIN_MEANINGFUL_CHARS = 100    # Minimum meaningful chars OCR must return to count as success


# ── Startup dependency checks ──────────────────────────────────────


def check_ocr_dependencies() -> Dict[str, bool]:
    """
    Verify OCR system dependencies are available.

    Returns a dict indicating availability of each dependency:
      {"tesseract": bool, "poppler": bool}
    """
    status: Dict[str, bool] = {"tesseract": False, "poppler": False}

    # Check Tesseract
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        if version:
            logger.info("[OCR] Tesseract available (version %s)", version)
            status["tesseract"] = True
        else:
            logger.warning("[OCR] Tesseract binary not found")
    except ImportError:
        logger.warning("[OCR] pytesseract not installed")
    except Exception as e:
        logger.warning("[OCR] Tesseract check failed: %s", e)

    # Check Poppler (used by pdf2image)
    try:
        from pdf2image import pdfinfo_from_path
        # pdfinfo_from_path will raise if poppler is missing
        # If we can at least import, poppler is likely available
        logger.info("[OCR] Poppler/pdf2image available")
        status["poppler"] = True
    except ImportError:
        logger.warning("[OCR] pdf2image not installed")
    except Exception as e:
        logger.warning("[OCR] Poppler check failed: %s", e)

    return status


# ── Result type ─────────────────────────────────────────────────────


class OCRResult:
    """
    Structured result from OCR extraction.

    Attributes:
        text: The full extracted text (combined from all pages).
        page_count: Number of pages successfully OCR'd.
        total_pages: Total pages in the PDF.
        confidence: "High", "Medium", or "Low".
        method: Always "ocr" for this module.
        errors: List of per-page error messages (if any).
    """
    def __init__(
        self,
        text: str = "",
        page_count: int = 0,
        total_pages: int = 0,
        confidence: str = "Low",
        errors: Optional[List[str]] = None,
    ):
        self.text = text
        self.page_count = page_count
        self.total_pages = total_pages
        self.confidence = confidence
        self.method = "ocr"
        self.errors = errors or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "page_count": self.page_count,
            "total_pages": self.total_pages,
            "confidence": self.confidence,
            "method": self.method,
            "errors": self.errors,
        }


# ── Helper: check if OCR should be attempted ────────────────────────


def should_use_ocr(
    standard_text: Optional[str],
    standard_error: Optional[str] = None,
    is_image_pdf: bool = False,
) -> bool:
    """
    Determine whether OCR fallback should be attempted.

    Args:
        standard_text: Text extracted by standard methods (pdfplumber etc.).
        standard_error: Error message from standard extraction (if any).
        is_image_pdf: Whether camelot/pdfplumber reported image-based pages.

    Returns:
        True if OCR should be attempted, False otherwise.
    """
    logger.info("[OCR] Evaluating OCR fallback conditions:")
    logger.info("[OCR]   standard_text is None: %s", standard_text is None)

    # If standard extraction completely failed (error or None text)
    if standard_text is None:
        logger.info("[OCR]   -> Standard extraction returned None — WILL attempt OCR fallback")
        return True

    # Check text quality thoroughly
    stripped = standard_text.strip()
    logger.info("[OCR]   Extracted text length from pdfplumber: %d chars", len(stripped))
    logger.info("[OCR]   Whitespace-only text: %s", len(stripped) == 0)

    if len(stripped) == 0:
        logger.info("[OCR]   -> Text is whitespace-only — WILL attempt OCR fallback")
        return True

    if len(stripped) < MIN_TEXT_CHARS:
        logger.info("[OCR]   -> Standard text insufficient (%d chars, need %d) — WILL attempt OCR",
                    len(stripped), MIN_TEXT_CHARS)
        return True

    # If camelot reported image-based pages
    if is_image_pdf:
        logger.info("[OCR]   -> PDF reported as image-based — WILL attempt OCR")
        return True

    # Standard extraction produced adequate text — no OCR needed
    logger.info("[OCR]   -> Standard text adequate (%d chars) — skipping OCR", len(stripped))
    return False


def evaluate_ocr_quality(text: str) -> Tuple[str, List[str]]:
    """
    Evaluate whether OCR text has sufficient quality.

    Returns (quality_label, warnings):
      - quality_label: "pass" or "insufficient"
      - warnings: List of warning messages if quality is low
    """
    warnings: List[str] = []
    stripped = text.strip()
    char_count = len(stripped)

    if char_count < MIN_MEANINGFUL_CHARS:
        warnings.append(
            f"OCR extraction produced insufficient usable text "
            f"({char_count} meaningful chars, need {MIN_MEANINGFUL_CHARS})."
        )
        return "insufficient", warnings

    # Check for mostly symbolic/noisy text (less than 40% alphabetic)
    if stripped:
        alpha_count = sum(1 for c in stripped if c.isalpha())
        alpha_ratio = alpha_count / len(stripped)
        if alpha_ratio < 0.4:
            warnings.append(
                f"OCR text appears noisy (only {alpha_ratio:.0%} alphabetic characters). "
                f"Quality may be poor."
            )
            return "insufficient", warnings

    return "pass", warnings


# ── Page-level OCR processing ───────────────────────────────────────


def _ocr_single_page(image_path: str, page_num: int) -> Tuple[str, Optional[str]]:
    """
    Run Tesseract OCR on a single page image.

    Args:
        image_path: Path to the page image file.
        page_num: Page number (for logging).

    Returns:
        (extracted_text, error_message):
          - extracted_text: The OCR'd text (may be empty).
          - error_message: Error string if page failed, else None.
    """
    try:
        from PIL import Image
        import pytesseract

        with Image.open(image_path) as img:
            # Convert to grayscale for better OCR accuracy on scanned docs
            if img.mode != "L":
                img = img.convert("L")

            # Run Tesseract with reasonable defaults
            # --psm 6: Assume a uniform block of text (good for tender pages)
            text = pytesseract.image_to_string(img, config="--psm 6 --oem 3")
            char_count = len(text.strip())

            if char_count > 0:
                logger.info("[OCR] Page %d: %d chars extracted", page_num, char_count)
            else:
                logger.warning("[OCR] Page %d: OCR returned no text (blank page or unreadable)", page_num)

            return text.strip(), None

    except ImportError as e:
        error_msg = f"OCR dependencies not installed: {e}"
        logger.warning("[OCR] Page %d: %s", page_num, error_msg)
        return "", error_msg

    except Exception as e:
        error_msg = f"OCR failed: {e}"
        logger.warning("[OCR] Page %d: %s", page_num, error_msg)
        return "", error_msg


def _ocr_page_batch(
    image_dir: str,
    page_numbers: List[int],
    ext: str = ".jpg",
) -> List[Tuple[str, Optional[str]]]:
    """
    Process a batch of page images through OCR.

    Args:
        image_dir: Directory containing the page images.
        page_numbers: List of 1-based page numbers to process.
        ext: Image file extension (default: .jpg).

    Returns:
        List of (text, error) tuples, one per page.
    """
    results: List[Tuple[str, Optional[str]]] = []

    for page_num in page_numbers:
        image_path = os.path.join(image_dir, f"page_{page_num:04d}{ext}")
        if not os.path.exists(image_path):
            logger.warning("[OCR] Page %d: image file not found at %s", page_num, image_path)
            results.append(("", f"Page {page_num}: image file not found"))
            continue

        text, error = _ocr_single_page(image_path, page_num)
        results.append((text, error))

    return results


# ── Main OCR extraction ─────────────────────────────────────────────


def extract_via_ocr(file_path: str) -> OCRResult:
    """
    Extract text from an image-based PDF using OCR.

    Step-by-step:
      1. Convert PDF pages to images using pdf2image (poppler-utils).
      2. Process images through Tesseract OCR in chunks.
      3. Combine page texts with separators.
      4. Return structured OCRResult.

    Args:
        file_path: Path to the PDF file.

    Returns:
        OCRResult with extracted text, page info, and confidence.
    """
    from pdf2image import convert_from_path

    logger.info("[OCR] === OCR FALLBACK STARTING ===")
    logger.info("[OCR] Starting OCR fallback for %s", os.path.basename(file_path))

    # ── Step 0: Check dependencies first ─────────────────────────────
    deps = check_ocr_dependencies()
    if not deps["tesseract"]:
        logger.error("[OCR] Tesseract not available — OCR fallback cannot run")
        return OCRResult(
            confidence="Low",
            errors=["Tesseract OCR not available (missing system dependency)"],
        )
    if not deps["poppler"]:
        logger.error("[OCR] Poppler not available — OCR fallback cannot run")
        return OCRResult(
            confidence="Low",
            errors=["Poppler/pdf2image not available (missing system dependency)"],
        )

    # ── Step 1: Get page count first (to validate before heavy processing) ──
    try:
        page_count = _get_page_count(file_path)
        if page_count is None:
            logger.error("[OCR] Could not determine page count — PDF may be malformed")
            return OCRResult(
                confidence="Low",
                errors=["Could not determine page count — PDF may be malformed"],
            )

        if page_count > MAX_PAGES_FOR_OCR:
            logger.warning(
                "[OCR] PDF has %d pages (max %d) — refusing OCR to prevent memory issues",
                page_count, MAX_PAGES_FOR_OCR,
            )
            return OCRResult(
                confidence="Low",
                total_pages=page_count,
                errors=[f"PDF too large for OCR ({page_count} pages, max {MAX_PAGES_FOR_OCR})"],
            )

        logger.info("[OCR] PDF has %d pages — proceeding with OCR", page_count)

    except Exception as e:
        logger.error("[OCR] Failed to get page count: %s", e)
        return OCRResult(confidence="Low", errors=[f"Failed to analyze PDF: {e}"])

    # ── Step 2: Convert pages to images (in temp directory) ──────────
    temp_dir: Optional[str] = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="ocr_")
        logger.info("[OCR] Converting %d pages to images in %s", page_count, temp_dir)

        # Convert PDF to images. pdf2image handles poppler integration.
        # dpi=200 is a good balance between speed and OCR accuracy.
        logger.info("[OCR] Starting PDF-to-image conversion (dpi=200, format=jpg)")
        images = convert_from_path(
            file_path,
            dpi=200,
            output_folder=temp_dir,
            fmt="jpg",
            prefix="page_",
            thread_count=2,
        )

        actual_images = len(images)
        logger.info("[OCR] Converted %d/%d pages to images", actual_images, page_count)

        if actual_images == 0:
            logger.error("[OCR] pdf2image produced zero images — PDF may be corrupt")
            return OCRResult(
                confidence="Low",
                total_pages=page_count,
                errors=["pdf2image produced zero images — PDF may be corrupt"],
            )

    except Exception as e:
        logger.error("[OCR] PDF-to-image conversion failed: %s", e)
        return OCRResult(
            confidence="Low",
            total_pages=page_count,
            errors=[f"PDF-to-image conversion failed: {e}"],
        )

    # ── Step 3: Run OCR on each page ─────────────────────────────────
    try:
        all_page_texts: List[str] = []
        all_errors: List[str] = []
        successful_pages = 0

        total_pages_to_process = min(actual_images, page_count)
        page_numbers = list(range(1, total_pages_to_process + 1))

        for chunk_start in range(0, len(page_numbers), OCR_CHUNK_PAGES):
            chunk = page_numbers[chunk_start:chunk_start + OCR_CHUNK_PAGES]
            logger.info(
                "[OCR] Processing pages %d-%d (chunk %d/%d)",
                chunk[0], chunk[-1],
                chunk_start // OCR_CHUNK_PAGES + 1,
                (len(page_numbers) + OCR_CHUNK_PAGES - 1) // OCR_CHUNK_PAGES,
            )

            chunk_results = _ocr_page_batch(temp_dir, chunk)

            for idx, (text, error) in enumerate(chunk_results):
                page_num = chunk[idx]
                if error:
                    all_errors.append(error)
                if text:
                    all_page_texts.append(f"--- PAGE {page_num} ---\n{text}")
                    successful_pages += 1

        # ── Step 4: Combine results ──────────────────────────────────
        combined_text = "\n\n".join(all_page_texts)
        char_count = len(combined_text)

        logger.info("[OCR] === OCR FALLBACK COMPLETE ===")
        logger.info("[OCR] OCR extracted %d total characters from %d pages",
                    char_count, successful_pages)
        logger.info("[OCR] Successfully OCR'd %d/%d pages", successful_pages, total_pages_to_process)

        if all_errors:
            logger.warning("[OCR] OCR encountered %d page-level errors", len(all_errors))
            for err in all_errors[:5]:  # Log first 5 errors
                logger.warning("[OCR]   Error: %s", err)

        if char_count == 0:
            logger.warning("[OCR] OCR returned empty text — no characters extracted")
            return OCRResult(
                text="",
                page_count=0,
                total_pages=page_count,
                confidence="Low",
                errors=all_errors or ["OCR returned no text on any page"],
            )

        # ── Step 5: Determine confidence ─────────────────────────────
        if char_count > 2000 and successful_pages >= total_pages_to_process * 0.7:
            confidence = "High"
            logger.info("[OCR] OCR confidence: High (%d chars, %d/%d pages OK)",
                        char_count, successful_pages, total_pages_to_process)
        elif char_count > 500 and successful_pages > 0:
            confidence = "Medium"
            logger.info("[OCR] OCR confidence: Medium (%d chars from %d pages)",
                        char_count, successful_pages)
        else:
            confidence = "Low"
            logger.warning("[OCR] OCR confidence LOW: only %d chars from %d pages",
                           char_count, successful_pages)

        # ── Step 6: Quality check ────────────────────────────────────
        quality, quality_warnings = evaluate_ocr_quality(combined_text)
        if quality == "insufficient":
            logger.warning("[OCR] OCR quality check: insufficient — %s",
                           quality_warnings[0] if quality_warnings else "unknown")
            return OCRResult(
                text="",
                page_count=0,
                total_pages=page_count,
                confidence="Low",
                errors=quality_warnings,
            )

        return OCRResult(
            text=combined_text,
            page_count=successful_pages,
            total_pages=page_count,
            confidence=confidence,
            errors=all_errors,
        )

    except Exception as e:
        logger.exception("[OCR] OCR processing failed unexpectedly: %s", e)
        return OCRResult(
            confidence="Low",
            total_pages=page_count,
            errors=[f"OCR processing failed: {e}"],
        )

    finally:
        # ── Cleanup: remove temp directory ───────────────────────────
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info("[OCR] Cleaned up temp directory %s", temp_dir)
            except Exception as e:
                logger.warning("[OCR] Failed to clean up temp dir: %s", e)


# ── Internal helper: get PDF page count ─────────────────────────────


def _get_page_count(file_path: str) -> Optional[int]:
    """
    Get the number of pages in a PDF using pdf2image.

    Returns None if the page count cannot be determined.
    """
    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(file_path)
        pages = info.get("Pages")
        logger.info("[OCR] PDF page count via pdf2image: %s", pages)
        return pages or None
    except Exception:
        # Fallback: try pdfplumber
        logger.info("[OCR] pdf2image page count failed, trying pdfplumber fallback")
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                pages = len(pdf.pages)
                logger.info("[OCR] PDF page count via pdfplumber: %d", pages)
                return pages
        except Exception as e:
            logger.warning("[OCR] Could not determine page count: %s", e)
            return None