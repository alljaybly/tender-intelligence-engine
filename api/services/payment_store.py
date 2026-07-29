import threading
from datetime import datetime
from typing import Dict, Any, Optional

_PAYMENTS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


def record_payment(api_key: str, plan: str, amount: str) -> Dict[str, Any]:
    with _LOCK:
        payment_id = f"{api_key}_{datetime.utcnow().isoformat()}"
        entry = {
            "payment_id": payment_id,
            "api_key": api_key,
            "plan": plan,
            "amount": amount,
            "timestamp": datetime.utcnow().isoformat()
        }
        _PAYMENTS[payment_id] = entry
        return entry
