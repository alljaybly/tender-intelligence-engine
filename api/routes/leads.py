"""
Lead capture route for marketing lead intake.
"""
import logging
from fastapi import APIRouter, HTTPException
from api.schemas.leads import LeadCreate, LeadResponse
from api.services.database import _get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadResponse, status_code=201)
async def create_lead(lead: LeadCreate):
    """
    Capture a marketing lead. Validates email, prevents duplicates.
    """
    name = lead.name.strip()
    email = lead.email.strip().lower()
    company = lead.company.strip()
    role = lead.role.strip()

    # Basic email validation
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=422, detail="Invalid email address")

    if not name:
        raise HTTPException(status_code=422, detail="Name is required")

    conn = _get_connection()
    try:
        cursor = conn.cursor()

        # Check for duplicate email
        cursor.execute(
            "SELECT id FROM marketing_leads WHERE email = ?", (email,)
        )
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="This email has already been registered. We'll be in touch.",
            )

        # Insert lead
        cursor.execute(
            """
            INSERT INTO marketing_leads (name, email, company, role)
            VALUES (?, ?, ?, ?)
            """,
            (name, email, company, role),
        )
        conn.commit()
        lead_id = cursor.lastrowid

        logger.info("[LEADS] New lead captured: %s <%s>", name, email)

        return LeadResponse(
            id=lead_id,
            name=name,
            email=email,
            company=company,
            role=role,
            created_at="",
            message="Thank you — we'll contact you soon.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[LEADS] Failed to create lead: %s", e)
        raise HTTPException(status_code=500, detail="Failed to capture lead")
    finally:
        conn.close()