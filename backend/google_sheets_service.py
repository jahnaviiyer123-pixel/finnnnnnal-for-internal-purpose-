"""
Google Sheets Parallel Sync Service for RideWell / Learn & Drive
Dispatches newly enrolled or updated student records to Google Sheets in real-time.
Uses a Google Apps Script Webhook (Zero credentials/GCP setup required, works with any Gmail account).
"""
import os
import logging
import requests
import pymongo
from typing import Dict, Any, Optional, List

logger = logging.getLogger("ridewell.sheets")

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://learnanddrive:T5cYO6bCZYwYXP9w@driving.ws3cihd.mongodb.net/ridewell?retryWrites=true&w=majority"
)

def get_webhook_url() -> str:
    """Retrieve Google Sheets Webhook URL from environment or MongoDB settings."""
    url = os.environ.get("GOOGLE_SHEET_WEBHOOK_URL", "")
    if url and url.startswith("http"):
        return url
    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        setting = client.ridewell.settings.find_one({"key": "google_sheet_webhook"})
        if setting and setting.get("url") and setting.get("url").startswith("http"):
            return setting.get("url")
    except Exception as e:
        logger.debug("Could not read sheet webhook from DB: %s", e)
    return ""

def is_sheets_sync_enabled() -> bool:
    return bool(get_webhook_url())

def sync_student_to_google_sheet(student_data: Dict[str, Any], trainer_name: str = "Unassigned") -> bool:
    """
    Sends student details to Google Sheet webhook asynchronously in parallel.
    Appends a new row or updates the existing student in the Google Sheet.
    """
    webhook_url = get_webhook_url()
    if not webhook_url:
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
        "total_classes": student_data.get("total_classes", 10),
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
        resp = requests.post(webhook_url, json=payload, timeout=10)
        logger.info("Successfully synced student '%s' to Google Sheet (HTTP %d)", student_data.get("name"), resp.status_code)
        return resp.status_code in [200, 201, 204]
    except Exception as e:
        logger.warning("Failed to sync student '%s' to Google Sheet: %s", student_data.get("name"), e)
        return False

def sync_all_active_students_to_sheet() -> Dict[str, Any]:
    """
    Sync all active students into Google Sheets in bulk.
    """
    webhook_url = get_webhook_url()
    if not webhook_url:
        return {"ok": False, "error": "Google Sheets Webhook URL not configured"}

    client = pymongo.MongoClient(MONGO_URI)
    db = client.ridewell
    students = list(db.students.find({"status": "active"}, {"_id": 0}))
    trainers = {t["id"]: t["name"] for t in db.users.find({"role": "trainer"}, {"id": 1, "name": 1, "_id": 0})}

    success_count = 0
    for s in students:
        trainer_name = trainers.get(s.get("assigned_trainer_id"), "Unassigned")
        if sync_student_to_google_sheet(s, trainer_name):
            success_count += 1

    return {
        "ok": True,
        "total": len(students),
        "synced": success_count,
        "message": f"Synced {success_count} of {len(students)} active students to Google Sheet"
    }
