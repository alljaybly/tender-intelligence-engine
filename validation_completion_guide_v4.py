import json
import time
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from api.main import app

ROOT = Path(__file__).resolve().parent
PDF_PATH = ROOT / "REQ00529 ELECTRICAL SERVICES.pdf"
OUTPUT_DIR = ROOT / "validation_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


def pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def main() -> int:
    if not PDF_PATH.exists():
        print(f"ERROR: Missing tender file: {PDF_PATH}")
        return 2

    with TestClient(app) as client:
        with open(PDF_PATH, "rb") as f:
            upload = client.post(
                "/api/process/upload",
                files={"file": (PDF_PATH.name, f, "application/pdf")},
            )
        print("UPLOAD_STATUS", upload.status_code)
        upload.raise_for_status()
        job_id = upload.json()["job_id"]
        print("JOB_ID", job_id)

        final_status = None
        for _ in range(180):
            resp = client.get(f"/api/process/status/{job_id}")
            resp.raise_for_status()
            payload = resp.json()
            final_status = payload.get("status")
            print("POLL", final_status)
            if final_status in ("completed", "partial_success", "failed"):
                break
            time.sleep(2)

        if final_status not in ("completed", "partial_success"):
            print("FINAL_STATUS", final_status)
            return 3

        package_zip_resp = client.post(f"/api/process/export/package-zip/{job_id}")
        print("PACKAGE_ZIP_STATUS", package_zip_resp.status_code)
        package_zip_resp.raise_for_status()
        package_zip = package_zip_resp.content
        (OUTPUT_DIR / f"{job_id}_package_v4.zip").write_bytes(package_zip)

        with zipfile.ZipFile(BytesIO(package_zip), "r") as zf:
            names = zf.namelist()
            print("ZIP_NAMES", names)
            if "02 Tender Completion Guide.pdf" not in names:
                print("ERROR: completion guide missing from package")
                return 4
            guide_pdf = zf.read("02 Tender Completion Guide.pdf")
            guide_text = pdf_text(guide_pdf)
            (OUTPUT_DIR / f"{job_id}_completion_guide_v4.txt").write_text(guide_text, encoding="utf-8")

        required_markers = [
            "EXECUTIVE SUMMARY",
            "Tender Health Score",
            "Submission Recommendation",
            "Document Status Dashboard",
            "Overall Extraction Status",
            "Estimated Completion Plan",
            "Critical Items",
            "Tender Documents",
            "Company Documents",
            "Final Decision",
            "Director Approval",
        ]

        print("--- COMPLETION GUIDE MARKERS ---")
        all_found = True
        for marker in required_markers:
            found = marker in guide_text
            print(marker, found)
            all_found = all_found and found

        if not all_found:
            print("ERROR: one or more expected completion guide markers were not found")
            return 5

        print("--- GUIDE TEXT SAMPLE ---")
        print(guide_text[:12000])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
