"""
Lead capture schema for marketing lead intake.
"""
from pydantic import BaseModel, EmailStr


class LeadCreate(BaseModel):
    name: str
    email: str
    company: str = ""
    role: str = ""


class LeadResponse(BaseModel):
    id: int
    name: str
    email: str
    company: str
    role: str
    created_at: str
    message: str = "Thank you — we'll contact you soon."