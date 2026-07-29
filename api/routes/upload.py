from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from tempfile import NamedTemporaryFile
import shutil
import os
import json

# Existing services
from api.services.ai_engine.parser import extract_text_from_pdf
from api.services.ai_engine.summarizer import summarize_text
from api.services.ai_engine.scorer import score_tender
from api.services.ai_engine.matcher import compute_match

# Optional auth

router = APIRouter()


@router.post("/upload")
async def upload_tender(
    file: UploadFile = File(...),
    company_profile: str = Form(...),
):
    # ✅ Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    try:
        # ✅ Parse company profile JSON (real user input)
        try:
            company_profile_dict = json.loads(company_profile)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid company_profile JSON")

        # ✅ Validate required fields (NO guessing)
        if "keywords" not in company_profile_dict or "min_years_experience" not in company_profile_dict:
            raise HTTPException(
                status_code=400,
                detail="company_profile must include 'keywords' and 'min_years_experience'"
            )

        # ✅ Save file temporarily
        with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name

        # ✅ Extract text
        extracted_text = extract_text_from_pdf(temp_file_path)

        if not extracted_text or len(extracted_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Failed to extract meaningful text")

        # ✅ Run pipeline
        summary = summarize_text(extracted_text)
        score_result = score_tender(extracted_text)

        tender_data = {
            "text": extracted_text
        }

        match_result = compute_match(tender_data, company_profile_dict)

        # ✅ Cleanup
        os.remove(temp_file_path)

        # ✅ Return ONLY real results
        return {
            "status": "success",
            "filename": file.filename,
            "summary": summary,
            "score": score_result,
            "match": match_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))