"""
Hostinger Reach Service for RideWell / Adarsh Motor Driving School
Integrates with Hostinger Reach Email Marketing API.
Profile UUID: 4cea6ddb-210f-4765-9e5c-69c69d2678d9
Limits: 500 Subscribers, 3,500 Monthly Emails
"""

import os
import re
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ridewell.reach")

HOSTINGER_API_BASE = os.environ.get("HOSTINGER_API_BASE", "https://api.hostinger.com")
HOSTINGER_API_TOKEN = os.environ.get("HOSTINGER_API_TOKEN", "")
REACH_PROFILE_UUID = os.environ.get("HOSTINGER_REACH_PROFILE_UUID", "4cea6ddb-210f-4765-9e5c-69c69d2678d9")

# Pre-created Tag UUIDs on Hostinger Reach
TAG_STUDENT_UUID = "e1650a0c-5d5b-4516-9bcf-9d6f1751693a"
TAG_PROSPECT_UUID = "5bfc650d-d96b-49a7-8e0c-15466a9fe91b"
TAG_COMPLETED_UUID = "25f193a7-e2aa-4ed2-bf51-e261ca091a61"

def format_phone_e164(phone: Optional[str]) -> Optional[str]:
    """Ensure phone number conforms to E.164 format (+91XXXXXXXXXX)."""
    if not phone:
        return None
    # Strip spaces, hyphens, parentheses
    clean = re.sub(r"[^\d+]", "", str(phone).strip())
    if not clean:
        return None
    if clean.startswith("+"):
        return clean if len(clean) >= 10 else None
    if len(clean) == 10:
        return f"+91{clean}"
    if len(clean) == 12 and clean.startswith("91"):
        return f"+{clean}"
    return None

def _get_headers() -> Dict[str, str]:
    token = HOSTINGER_API_TOKEN
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "RideWell-LMS/1.0"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def is_reach_configured() -> bool:
    """Return whether the API token and profile UUID are available."""
    return bool(HOSTINGER_API_TOKEN and REACH_PROFILE_UUID)

def sync_contacts_to_reach(contacts: List[Dict[str, Any]], tag_name: str = "Student") -> Dict[str, Any]:
    """
    Sync a list of contacts to Hostinger Reach profile in bulk.
    Each contact should have 'email', and optionally 'name', 'phone'.
    """
    if not contacts:
        return {"success": True, "count": 0, "message": "No contacts to sync"}

    tag_uuid = TAG_STUDENT_UUID
    if tag_name.lower() == "prospect":
        tag_uuid = TAG_PROSPECT_UUID
    elif tag_name.lower() == "completed":
        tag_uuid = TAG_COMPLETED_UUID

    payload_contacts = []
    for c in contacts:
        email = c.get("email")
        if not email or "@" not in email:
            continue
        item = {
            "email": email.strip().lower(),
            "name": c.get("name", "").strip() or "Student"
        }
        phone = format_phone_e164(c.get("phone"))
        if phone:
            item["phone"] = phone
        payload_contacts.append(item)

    if not payload_contacts:
        return {"success": True, "count": 0, "message": "No valid email contacts found"}

    if not HOSTINGER_API_TOKEN:
        logger.info("[SIMULATION] Hostinger Reach sync of %d contacts: %s", len(payload_contacts), [x['email'] for x in payload_contacts])
        return {
            "success": True,
            "simulated": True,
            "count": len(payload_contacts),
            "message": f"Simulated sync of {len(payload_contacts)} contacts to Reach profile {REACH_PROFILE_UUID}"
        }

    url = f"{HOSTINGER_API_BASE}/api/reach/v1/profiles/{REACH_PROFILE_UUID}/contacts/bulk"
    payload = {
        "contacts": payload_contacts,
        "tag_uuids": [tag_uuid],
        "note": f"Synced from RideWell LMS ({tag_name})"
    }

    try:
        resp = requests.post(url, json=payload, headers=_get_headers(), timeout=15)
        if resp.status_code in [200, 201, 202]:
            logger.info("Successfully synced %d contacts to Hostinger Reach", len(payload_contacts))
            return {"success": True, "count": len(payload_contacts), "response": resp.json() if resp.text else {}}
        else:
            logger.error("Hostinger Reach API returned %d: %s", resp.status_code, resp.text)
            return {"success": False, "status_code": resp.status_code, "error": resp.text}
    except Exception as e:
        logger.error("Failed to call Hostinger Reach API: %s", str(e), exc_info=True)
        return {"success": False, "error": str(e)}

def get_reach_summary() -> Dict[str, Any]:
    """Get active profile metadata and limits."""
    return {
        "profile_uuid": REACH_PROFILE_UUID,
        "limits": {
            "subscribers_limit": 500,
            "emails_monthly_limit": 3500,
            "ai_messages_limit": 10
        },
        "tags": {
            "Student": TAG_STUDENT_UUID,
            "Prospect": TAG_PROSPECT_UUID,
            "Completed": TAG_COMPLETED_UUID
        },
        "configured": is_reach_configured(),
        "brand_name": "Adarsh Driving School"
    }
