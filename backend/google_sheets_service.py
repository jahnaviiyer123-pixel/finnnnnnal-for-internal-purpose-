"""
Google Sheets Parallel Sync Service for RideWell / Learn & Drive
Dispatches newly enrolled or updated student records to Google Sheets in real-time.
Uses a Google Apps Script Webhook (Zero credentials/GCP setup required, works with any Gmail account).
"""
import os
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("ridewell.sheets")

GOOGLE_SHEET_WEBHOOK_URL = os.environ.get("GOOGLE_SHEET_WEBHOOK_URL", "")

def is_sheets_sync_enabled() -> bool:
    return bool(GOOGLE_SHEET_WEBHOOK_URL and GOOGLE_SHEET_WEBHOOK_URL.startswith("http"))

def sync_student_to_google_sheet(student_data: Dict[str, Any], trainer_name: str = "Unassigned") -> bool:
    """
    Sends student details to Google Sheet webhook asynchronously in parallel.
    Appends a new row or updates the existing student in the Google Sheet.
    """
    webhook_url = os.environ.get("GOOGLE_SHEET_WEBHOOK_URL", GOOGLE_SHEET_WEBHOOK_URL)
    if not webhook_url or not webhook_url.startswith("http"):
        logger.info(
            "[GOOGLE SHEETS SIMULATION] Student '%s' ready for sheet sync. Webhook URL not configured yet.",
            student_data.get("name")
        )
        return False

    fees_total = float(student_data.get("fees_total") or 0)
    fees_paid = float(student_data.get("fees_paid") or 0)
    balance = max(0.0, fees_total - fees_paid)

    payload = {
        "action": "sync_student",
        "student_id": student_data.get("id", ""),
        "name": student_data.get("name", ""),
        "phone": student_data.get("phone", ""),
        "email": student_data.get("email") or "",
        "branch": student_data.get("location") or "Khajaguda",
        "slot_time": student_data.get("slot_time") or "",
        "joining_date": student_data.get("joining_date") or "",
        "trainer": trainer_name,
        "total_classes": student_data.get("total_classes", 12),
        "fees_total": fees_total,
        "fees_paid": fees_paid,
        "balance_due": balance,
        "license_type": student_data.get("license_type", "4W"),
        "needs_pickup": "Yes" if student_data.get("needs_pickup") else "No",
        "pickup_address": student_data.get("pickup_address") or "",
        "status": student_data.get("status", "active"),
        "notes": student_data.get("notes") or "",
        "timestamp": student_data.get("created_at") or ""
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=8)
        logger.info("Successfully synced student '%s' to Google Sheet (HTTP %d)", student_data.get("name"), resp.status_code)
        return resp.status_code in [200, 201, 204]
    except Exception as e:
        logger.warning("Error syncing student '%s' to Google Sheet: %s", student_data.get("name"), str(e))
        return False
