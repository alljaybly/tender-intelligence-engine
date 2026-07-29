from fastapi import APIRouter
from pydantic import BaseModel

from ..services.ai_engine.parser import extract_text_from_pdf
from ..services.ai_engine.summarizer import summarize_text
from ..services.ai_engine.scorer import score_tender
from ..services.ai_engine.matcher import compute_match

router = APIRouter()


class AnalyzeRequest(BaseModel):
    file_path: str
    company_profile: dict = {}


@router.post("/analyze")
def analyze_tender(data: AnalyzeRequest):
    text = extract_text_from_pdf(data.file_path)

    summary = summarize_text(text)
    score = score_tender(text)
    match = compute_match({"text": text}, data.company_profile)

    return {
        "status": "success",
        "data": {
            "summary": summary,
            "score": score,
            "match": match
        }
    }