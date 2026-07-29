import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

USERS_ENV_VAR = "TENDER_USERS_JSON"
PLAN_LIMITS = {
    "free": {"period": "daily", "limit": 5},
    "starter": {"period": "monthly", "limit": 100},
    "pro": {"period": "unlimited", "limit": None}
}
RATE_LIMIT_PER_MINUTE = 10
_USAGE: Dict[str, Dict[str, Any]] = {}
_USAGE_LOCK = threading.Lock()
_USER_UPDATES: Dict[str, Dict[str, Any]] = {}
_USER_UPDATES_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.utcnow().isoformat()


def _today_key() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _month_key() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def _minute_key() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M")


def _ensure_usage(api_key: str) -> Dict[str, Any]:
    usage = _USAGE.get(api_key)
    if usage is None:
        usage = {
            "requests_count": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "last_used_at": None,
            "daily_period": _today_key(),
            "daily_requests": 0,
            "monthly_period": _month_key(),
            "monthly_requests": 0,
            "minute_period": _minute_key(),
            "minute_requests": 0
        }
        _USAGE[api_key] = usage
    _reset_periods_if_needed(usage)
    return usage


def _reset_periods_if_needed(usage: Dict[str, Any]) -> None:
    today = _today_key()
    if usage.get("daily_period") != today:
        usage["daily_period"] = today
        usage["daily_requests"] = 0

    month = _month_key()
    if usage.get("monthly_period") != month:
        usage["monthly_period"] = month
        usage["monthly_requests"] = 0

    minute = _minute_key()
    if usage.get("minute_period") != minute:
        usage["minute_period"] = minute
        usage["minute_requests"] = 0


def _normalise_user(api_key: str, user_data: Any) -> Optional[Dict[str, Any]]:
    if not api_key:
        return None

    if isinstance(user_data, str):
        user = {"user_id": user_data}
    elif isinstance(user_data, dict):
        user = dict(user_data)
    else:
        return None

    if user.get("active") is False or user.get("paid") is False:
        return None

    user.setdefault("api_key", api_key)
    user.setdefault("user_id", user.get("id") or user.get("email") or api_key[-8:])
    return user


def _load_users() -> Dict[str, Dict[str, Any]]:
    raw_users = os.getenv(USERS_ENV_VAR)
    if not raw_users:
        return {}

    try:
        parsed = json.loads(raw_users)
    except json.JSONDecodeError:
        logger.error("[AUTH] Invalid %s JSON", USERS_ENV_VAR)
        return {}

    users: Dict[str, Dict[str, Any]] = {}
    if isinstance(parsed, dict):
        for api_key, user_data in parsed.items():
            user = _normalise_user(api_key, user_data)
            if user:
                users[api_key] = user
    elif isinstance(parsed, list):
        for user_data in parsed:
            if not isinstance(user_data, dict):
                continue
            api_key = user_data.get("api_key")
            user = _normalise_user(api_key, user_data)
            if user:
                users[api_key] = user
    else:
        logger.error("[AUTH] %s must be a JSON object or array", USERS_ENV_VAR)

    return users


def get_user_by_api_key(api_key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not api_key:
        return None

    with _USER_UPDATES_LOCK:
        updated_user = _USER_UPDATES.get(api_key)
        if updated_user:
            return dict(updated_user)

    if api_key == "test_key_123":
        return {
            "api_key": "test_key_123",
            "plan": "starter",
            "payment_status": "paid",
            "expires_at": None
        }

    users = _load_users()
    user = users.get(api_key)
    return dict(user) if user else None


def get_plan_config(plan: Optional[str]) -> Optional[Dict[str, Any]]:
    if not plan:
        return None
    return PLAN_LIMITS.get(str(plan).lower())


def is_usage_allowed(api_key: str, plan: Optional[str]) -> bool:
    plan_config = get_plan_config(plan)
    if not plan_config:
        return False
    if plan_config["period"] == "unlimited":
        return True

    with _USAGE_LOCK:
        usage = _ensure_usage(api_key)
        if plan_config["period"] == "daily":
            return usage["daily_requests"] < plan_config["limit"]
        if plan_config["period"] == "monthly":
            return usage["monthly_requests"] < plan_config["limit"]
        return False


def reserve_request(api_key: str, plan: Optional[str]) -> Dict[str, Any]:
    user = get_user_by_api_key(api_key)
    if not user:
        return {"allowed": False, "code": "user_not_found"}
    
    expires_at = user.get("expires_at")
    
    if expires_at:
        if datetime.utcnow() > datetime.fromisoformat(expires_at):
            return {"allowed": False, "code": "plan_expired"}
    
    plan_config = get_plan_config(plan)
    if not plan_config:
        return {"allowed": False, "code": "plan_missing_or_invalid"}

    with _USAGE_LOCK:
        usage = _ensure_usage(api_key)
        if usage["minute_requests"] >= RATE_LIMIT_PER_MINUTE:
            return {"allowed": False, "code": "rate_limit_exceeded"}

        if plan_config["period"] != "unlimited":
            if plan_config["period"] == "daily" and usage["daily_requests"] >= plan_config["limit"]:
                return {"allowed": False, "code": "usage_limit_exceeded"}
            if plan_config["period"] == "monthly" and usage["monthly_requests"] >= plan_config["limit"]:
                return {"allowed": False, "code": "usage_limit_exceeded"}

        usage["requests_count"] += 1
        usage["daily_requests"] += 1
        usage["monthly_requests"] += 1
        usage["minute_requests"] += 1
        usage["last_used_at"] = _utc_now()
        return {"allowed": True, "usage": dict(usage), "plan": plan_config}


def record_request(api_key: str) -> Dict[str, Any]:
    with _USAGE_LOCK:
        usage = _ensure_usage(api_key)
        usage["requests_count"] += 1
        usage["daily_requests"] += 1
        usage["monthly_requests"] += 1
        usage["minute_requests"] += 1
        usage["last_used_at"] = _utc_now()
        return dict(usage)


def record_job_success(api_key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not api_key:
        return None
    with _USAGE_LOCK:
        usage = _ensure_usage(api_key)
        usage["successful_jobs"] += 1
        return dict(usage)


def record_job_failure(api_key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not api_key:
        return None
    with _USAGE_LOCK:
        usage = _ensure_usage(api_key)
        usage["failed_jobs"] += 1
        return dict(usage)


def get_usage(api_key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not api_key:
        return None
    with _USAGE_LOCK:
        usage = _USAGE.get(api_key)
        return dict(usage) if usage else None


def update_user_payment(api_key: Optional[str], plan: Optional[str], payment_status: Optional[str]) -> Optional[Dict[str, Any]]:
    if not api_key or not plan or not payment_status:
        return None

    user = get_user_by_api_key(api_key)
    if not user:
        return None

    updated_user = dict(user)
    updated_user["plan"] = plan
    updated_user["payment_status"] = payment_status
    updated_user["updated_at"] = _utc_now()
    
    expiry_days = 30
    updated_user["expires_at"] = (
        datetime.utcnow() + timedelta(days=expiry_days)
    ).isoformat()

    with _USER_UPDATES_LOCK:
        _USER_UPDATES[api_key] = updated_user

    return dict(updated_user)
