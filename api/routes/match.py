from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List, Dict

from ..services.ai_engine.matcher import compute_match

router = APIRouter()


class MatchRequest(BaseModel):
    tender_text: str
    company_profile: Dict


@router.post("/match")
async def match_tender(data: MatchRequest, request: Request):
    result = compute_match(
        {"text": data.tender_text},
        data.company_profile
    )

    return {
        "status": "success",
        "data": result
    }