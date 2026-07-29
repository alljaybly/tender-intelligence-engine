from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ..services.job_store import get_job
from ..services.user_store import get_user_by_api_key, get_usage, get_plan_config

router = APIRouter()


@router.get('/status/{job_id}')
def status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    # Return full job object
    return JSONResponse({
        'job_id': job['job_id'],
        'status': job['status'],
        'progress': job.get('progress'),
        'result': job.get('result'),
        'error': job.get('error'),
        'created_at': job.get('created_at'),
        'updated_at': job.get('updated_at')
    })


@router.get('/me')
async def get_me(request: Request):
    user = getattr(request.state, "user", {})
    api_key = user.get("api_key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    user_data = get_user_by_api_key(api_key)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    plan = user_data.get("plan")
    payment_status = user_data.get("payment_status", "")
    
    usage = get_usage(api_key)
    plan_config = get_plan_config(plan)
    
    requests_today = usage.get("daily_requests", 0) if usage else 0
    limit = plan_config.get("limit", 0) if plan_config else 0
    
    return JSONResponse({
        "plan": plan,
        "payment_status": payment_status,
        "usage": {
            "requests_today": requests_today,
            "limit": limit
        }
    })
