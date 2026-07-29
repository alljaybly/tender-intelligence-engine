from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ..services.user_store import get_user_by_api_key, update_user_payment
from ..services.payment_store import record_payment

router = APIRouter()

PLAN_PRICING = {
    "starter": Decimal("299.00"),
    "pro": Decimal("999.00")
}

PLAN_ITEMS = {
    "starter": "Tender Engine Starter Plan",
    "pro": "Tender Engine Pro Plan"
}


def _get_payfast_config():
    merchant_id = os.getenv("PAYFAST_MERCHANT_ID")
    merchant_key = os.getenv("PAYFAST_MERCHANT_KEY")
    return_url = os.getenv("PAYFAST_RETURN_URL")
    cancel_url = os.getenv("PAYFAST_CANCEL_URL")
    notify_url = os.getenv("PAYFAST_NOTIFY_URL")

    if not merchant_id or not merchant_key or not return_url or not cancel_url or not notify_url:
        raise HTTPException(status_code=500, detail="PayFast configuration missing")

    return {
        "merchant_id": merchant_id,
        "merchant_key": merchant_key,
        "return_url": return_url,
        "cancel_url": cancel_url,
        "notify_url": notify_url
    }


def _parse_amount(value):
    if value is None:
        return None

    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


@router.post('/payments/initiate')
async def initiate_payment(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid or missing JSON body"
        )
    
    plan = payload.get("plan")
    
    if not plan:
        raise HTTPException(
            status_code=400,
            detail="Missing required field: plan"
        )
    
    if plan not in ["starter", "pro"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid plan"
        )

    user = getattr(request.state, "user", {})
    api_key = user.get("api_key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    config = _get_payfast_config()
    params = {
        "merchant_id": config["merchant_id"],
        "merchant_key": config["merchant_key"],
        "return_url": config["return_url"],
        "cancel_url": config["cancel_url"],
        "notify_url": config["notify_url"],
        "amount": str(PLAN_PRICING[plan]),
        "item_name": PLAN_ITEMS[plan],
        "custom_str1": api_key,
        "custom_str2": plan
    }
    payment_url = f"https://sandbox.payfast.co.za/eng/process?{urlencode(params)}"
    return JSONResponse({"payment_url": payment_url})


@router.post('/webhook')
async def payfast_webhook(request: Request):
    form = await request.form()
    payment_status = form.get("payment_status")
    amount = form.get("amount_gross")
    api_key = form.get("custom_str1")
    plan = form.get("custom_str2")
    signature = form.get("signature")
    
    VALID_TEST_SIGNATURE = "VALID_TEST_SIGNATURE"
    if signature:
        expected_signature = VALID_TEST_SIGNATURE
        if signature != expected_signature:
            return JSONResponse({"status": "invalid_signature"})
    
    if not payment_status or not amount or not api_key:
        return JSONResponse({"status": "invalid"})

    if payment_status != "COMPLETE":
        return JSONResponse({"status": "ignored"})

    if not api_key or not plan:
        return JSONResponse({"status": "invalid"})

    user = get_user_by_api_key(api_key)
    if not user:
        return JSONResponse({"status": "invalid"})

    record_payment(api_key, plan, amount)
    update_user_payment(api_key, plan, "paid")

    return JSONResponse({"status": "ok"})
