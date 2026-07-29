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
        print(upload.text)
        upload.raise_for_status()
        job_id = upload.json()["job_id"]
        print("JOB_ID", job_id)

        final_status = None
        status_payload = None
        for _ in range(180):
            resp = client.get(f"/api/process/status/{job_id}")
            print("POLL_STATUS", resp.status_code, resp.text)
            resp.raise_for_status()
            status_payload = resp.json()
            final_status = status_payload.get("status")
            if final_status in ("completed", "partial_success", "failed"):
                break
            time.sleep(2)

        if final_status not in ("completed", "partial_success"):
            print("FINAL_STATUS", final_status)
            return 3

        result_resp = client.get(f"/api/process/result/{job_id}")
        print("RESULT_STATUS", result_resp.status_code)
        print(result_resp.text[:8000])
        result_resp.raise_for_status()
        result_json = result_resp.json()
        (OUTPUT_DIR / f"{job_id}_result.json").write_text(json.dumps(result_json, indent=2), encoding="utf-8")

        readiness_json_resp = client.get(f"/api/process/readiness/{job_id}")
        print("READINESS_JSON_STATUS", readiness_json_resp.status_code)
        print(readiness_json_resp.text[:8000])
        readiness_json_resp.raise_for_status()
        readiness_json = readiness_json_resp.json()
        (OUTPUT_DIR / f"{job_id}_readiness.json").write_text(json.dumps(readiness_json, indent=2), encoding="utf-8")

        readiness_pdf_resp = client.get(f"/api/process/export/readiness/{job_id}")
        print("READINESS_PDF_STATUS", readiness_pdf_resp.status_code)
        readiness_pdf_resp.raise_for_status()
        readiness_pdf = readiness_pdf_resp.content
        (OUTPUT_DIR / f"{job_id}_readiness.pdf").write_bytes(readiness_pdf)
        readiness_text = pdf_text(readiness_pdf)
        (OUTPUT_DIR / f"{job_id}_readiness.txt").write_text(readiness_text, encoding="utf-8")

        package_zip_resp = client.post(f"/api/process/export/package-zip/{job_id}")
        print("PACKAGE_ZIP_STATUS", package_zip_resp.status_code)
        package_zip_resp.raise_for_status()
        package_zip = package_zip_resp.content
        (OUTPUT_DIR / f"{job_id}_package.zip").write_bytes(package_zip)

        extracted = {}
        with zipfile.ZipFile(BytesIO(package_zip), "r") as zf:
            names = zf.namelist()
            print("ZIP_NAMES", names)
            manifest = zf.read("PACKAGE_MANIFEST.txt").decode("utf-8", errors="replace")
            extracted["PACKAGE_MANIFEST.txt"] = manifest
            (OUTPUT_DIR / f"{job_id}_PACKAGE_MANIFEST.txt").write_text(manifest, encoding="utf-8")

            for pdf_name in [
                "02 Tender Completion Guide.pdf",
                "03 Tender Readiness Assessment.pdf",
                "08 Evidence Report.pdf",
            ]:
                if pdf_name in names:
                    content = zf.read(pdf_name)
                    text = pdf_text(content)
                    extracted[pdf_name] = text
                    safe_name = pdf_name.replace(" ", "_").replace("/", "_")
                    (OUTPUT_DIR / f"{job_id}_{safe_name}.txt").write_text(text, encoding="utf-8")

        checks = {
            "readiness_pdf": [
                "Readiness Score",
                "Verified Extraction Evidence",
                "Confidence:",
            ],
            "completion_guide": [
                "Verified Extracted Information",
                "Extraction Confidence Summary",
                "Verified From",
            ],
            "manifest": [
                "EXTRACTION CONFIDENCE SUMMARY",
                "Readiness Score",
            ],
        }

        print("--- CHECKS ---")
        for item in checks["readiness_pdf"]:
            print("READINESS_HAS", item, item in readiness_text)
        guide_text = extracted.get("02 Tender Completion Guide.pdf", "")
        for item in checks["completion_guide"]:
            print("GUIDE_HAS", item, item in guide_text)
        manifest_text = extracted.get("PACKAGE_MANIFEST.txt", "")
        for item in checks["manifest"]:
            print("MANIFEST_HAS", item, item in manifest_text)

        print("--- EVIDENCE SAMPLE ---")
        print(json.dumps(result_json.get("evidence", {}), indent=2)[:8000])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
