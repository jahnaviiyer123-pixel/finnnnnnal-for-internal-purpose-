"""
Hostinger n8n Webhook Service for RideWell / Adarsh Motor Driving School
Dispatches event payloads to Hostinger n8n automation workflows.
Subscription: Hostinger 'AI automation apps' (Active)
"""

import os
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("ridewell.n8n")

# Configurable Hostinger n8n Webhook URL
# E.g. https://n8n.yourdomain.com/webhook/ridewell-events
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")

def is_n8n_configured() -> bool:
    """Return True if an n8n webhook URL is set."""
    return bool(N8N_WEBHOOK_URL and N8N_WEBHOOK_URL.startswith("http"))

def dispatch_n8n_event(event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sends event data to Hostinger n8n instance asynchronously.
    Events: 'payment.recorded', 'student.enrolled', 'class.completed', 'invoice.generate'
    """
    if not is_n8n_configured():
        logger.info("[N8N SIMULATION] Event: %s (N8N_WEBHOOK_URL not yet set). Payload keys: %s", event_name, list(payload.keys()))
        return {
            "success": True,
            "simulated": True,
            "event": event_name,
            "message": "N8N_WEBHOOK_URL not set in env; event logged in simulation mode."
        }

    full_payload = {
        "event": event_name,
        "source": "ridewell-lms",
        "data": payload
    }

    try:
        resp = requests.post(N8N_WEBHOOK_URL, json=full_payload, timeout=8)
        logger.info("Dispatched '%s' to Hostinger n8n (Status %d)", event_name, resp.status_code)
        return {
            "success": resp.status_code in [200, 201, 204],
            "status_code": resp.status_code
        }
    except Exception as e:
        logger.warning("Failed to dispatch n8n event '%s': %s", event_name, str(e))
        return {
            "success": False,
            "error": str(e)
        }
