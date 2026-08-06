from fastapi import Header, HTTPException
import logging
import os

logger = logging.getLogger(__name__)

# In production this should come from environment variables
API_KEY = os.getenv("TENDER_API_KEY", "development-key")


async def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        logger.warning("[AUTH] 401 reason=Invalid or missing API key")
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )

    return {"authenticated": True}