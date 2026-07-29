import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

CONFIG_ENV_VAR = "TENDER_COST_PER_HOUR_CONFIG"


def get_configured_cost_per_hour(sector: Optional[str]) -> Optional[float]:
    if not sector:
        return None

    raw_config = os.getenv(CONFIG_ENV_VAR)
    if not raw_config:
        return None

    try:
        configured_rates: Dict[str, object] = json.loads(raw_config)
    except json.JSONDecodeError:
        logger.error("[PRICE] Invalid %s JSON", CONFIG_ENV_VAR)
        return None

    configured_value = configured_rates.get(sector)
    if configured_value is None:
        return None

    try:
        rate = float(configured_value)
    except (TypeError, ValueError):
        logger.error("[PRICE] Invalid configured cost_per_hour for sector=%s", sector)
        return None

    if rate <= 0:
        logger.error("[PRICE] Configured cost_per_hour must be greater than 0 for sector=%s", sector)
        return None

    return rate
