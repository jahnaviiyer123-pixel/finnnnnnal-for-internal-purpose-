"""
Notion Integration Service for RideWell / Learn & Drive
Syncs active and historical student records directly into a Notion Database.
"""
import os
import re
import logging
import requests
import pymongo
from typing import Dict, Any, Optional, List

logger = logging.getLogger("ridewell.notion")

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://learnanddrive:T5cYO6bCZYwYXP9w@driving.ws3cihd.mongodb.net/ridewell?retryWrites=true&w=majority"
)

NOTION_VERSION = "2022-06-28"

def clean_database_id(raw_id: str) -> str:
    """Extract clean 32-char UUID from a Notion URL or raw ID."""
    if not raw_id:
        return ""
    # Strip URL params and query strings
    cleaned = raw_id.split("?")[0].strip()
    # Match the last 32 hex characters in the URL/ID
    match = re.search(r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", cleaned, re.IGNORECASE)
    if match:
        val = match.group(1).replace("-", "")
        # Format as 8-4-4-4-12 UUID
        return f"{val[:8]}-{val[8:12]}-{val[12:16]}-{val[16:20]}-{val[20:]}"
    return raw_id.strip()

def get_notion_config() -> Dict[str, str]:
    """Retrieve Notion API token and Database ID from env or MongoDB settings."""
    api_key = os.environ.get("NOTION_API_KEY", "").strip()
    database_id = os.environ.get("NOTION_DATABASE_ID", "").strip()

    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        setting = client.ridewell.settings.find_one({"key": "notion_sync"})
        if setting:
            if not api_key:
                api_key = setting.get("api_key", "").strip()
            if not database_id:
                database_id = setting.get("database_id", "").strip()
    except Exception as e:
        logger.debug("Could not read notion settings from DB: %s", e)

    return {
        "api_key": api_key,
        "database_id": clean_database_id(database_id),
    }

def is_notion_configured() -> bool:
    cfg = get_notion_config()
    return bool(cfg.get("api_key") and cfg.get("database_id"))

def get_database_properties(api_key: str, database_id: str) -> Optional[Dict[str, Any]]:
    """Inspects the schema of the target Notion database."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    try:
        resp = requests.get(f"https://api.notion.com/v1/databases/{database_id}", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("properties", {})
        logger.warning("Could not fetch Notion database schema (HTTP %d): %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Error fetching Notion database schema: %s", e)
    return None

def build_notion_properties(student_data: Dict[str, Any], trainer_name: str, schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Intelligently builds Notion page properties conforming to the target Notion database schema.
    """
    name = student_data.get("name") or "Unnamed Student"
    phone = student_data.get("phone") or ""
    branch = student_data.get("location") or "Khajaguda"
    status = (student_data.get("status") or "active").capitalize()
    slot_time = student_data.get("slot_time") or ""
    total_classes = student_data.get("total_classes") or 12
    completed_classes = student_data.get("classes_completed") or 0
    fees_total = float(student_data.get("fees_total") or 0)
    fees_paid = float(student_data.get("fees_paid") or 0)
    balance = max(0.0, fees_total - fees_paid)
    joining_date = student_data.get("joining_date") or (student_data.get("created_at") or "")[:10]
    pickup_address = student_data.get("pickup_address") or ""
    notes = student_data.get("notes") or ""

    properties: Dict[str, Any] = {}

    if schema:
        # Schema-aware matching
        for prop_name, prop_meta in schema.items():
            p_type = prop_meta.get("type")
            p_lower = prop_name.lower()

            if p_type == "title":
                properties[prop_name] = {"title": [{"text": {"content": name}}]}
            elif "phone" in p_lower or "mobile" in p_lower:
                if p_type == "phone_number":
                    properties[prop_name] = {"phone_number": phone}
                elif p_type in ["rich_text", "text"]:
                    properties[prop_name] = {"rich_text": [{"text": {"content": phone}}]}
            elif "branch" in p_lower or "location" in p_lower:
                if p_type == "select":
                    properties[prop_name] = {"select": {"name": branch}}
                elif p_type in ["rich_text", "text"]:
                    properties[prop_name] = {"rich_text": [{"text": {"content": branch}}]}
            elif "status" in p_lower:
                if p_type == "select":
                    properties[prop_name] = {"select": {"name": status}}
                elif p_type == "status":
                    properties[prop_name] = {"status": {"name": status}}
                elif p_type in ["rich_text", "text"]:
                    properties[prop_name] = {"rich_text": [{"text": {"content": status}}]}
            elif "slot" in p_lower or "time" in p_lower:
                if p_type in ["rich_text", "text"]:
                    properties[prop_name] = {"rich_text": [{"text": {"content": slot_time}}]}
            elif "trainer" in p_lower:
                if p_type in ["rich_text", "text"]:
                    properties[prop_name] = {"rich_text": [{"text": {"content": trainer_name}}]}
            elif "total fee" in p_lower or p_lower == "fees" or p_lower == "fee":
                if p_type == "number":
                    properties[prop_name] = {"number": fees_total}
            elif "paid" in p_lower:
                if p_type == "number":
                    properties[prop_name] = {"number": fees_paid}
            elif "due" in p_lower or "balance" in p_lower or "pending" in p_lower:
                if p_type == "number":
                    properties[prop_name] = {"number": balance}
            elif "class" in p_lower:
                if p_type == "number":
                    properties[prop_name] = {"number": total_classes}
            elif ("join" in p_lower or "date" in p_lower) and p_type == "date":
                if joining_date and len(joining_date) == 10:
                    properties[prop_name] = {"date": {"start": joining_date}}
            elif "pickup" in p_lower or "address" in p_lower:
                if p_type in ["rich_text", "text"] and pickup_address:
                    properties[prop_name] = {"rich_text": [{"text": {"content": pickup_address}}]}
            elif "note" in p_lower:
                if p_type in ["rich_text", "text"] and notes:
                    properties[prop_name] = {"rich_text": [{"text": {"content": notes}}]}
    else:
        # Generic default matching
        properties["Name"] = {"title": [{"text": {"content": name}}]}

    # Ensure at least one title property exists
    if not any("title" in v for v in properties.values()):
        properties["Name"] = {"title": [{"text": {"content": name}}]}

    return properties

def sync_student_to_notion(student_data: Dict[str, Any], trainer_name: str = "Unassigned") -> bool:
    """
    Creates a new Page in the Notion Database for this student.
    """
    cfg = get_notion_config()
    api_key = cfg.get("api_key")
    database_id = cfg.get("database_id")

    if not api_key or not database_id:
        logger.info("[NOTION SIMULATION] Student '%s' ready for Notion sync. Integration not configured.", student_data.get("name"))
        return False

    schema = get_database_properties(api_key, database_id)
    properties = build_notion_properties(student_data, trainer_name, schema)

    # Detailed page body blocks so all data is accessible inside the Notion page
    fees_total = float(student_data.get("fees_total") or 0)
    fees_paid = float(student_data.get("fees_paid") or 0)
    balance = max(0.0, fees_total - fees_paid)
    phone = student_data.get("phone") or "N/A"
    branch = student_data.get("location") or "Khajaguda"
    slot_time = student_data.get("slot_time") or "N/A"

    children = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"🚗 Learn & Drive Student Profile\nBranch: {branch} | Phone: {phone} | Slot: {slot_time}\nTrainer: {trainer_name} | Status: {student_data.get('status', 'active').upper()}"
                        }
                    }
                ],
                "icon": {"emoji": "🚗"}
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"💰 Financial Details:\nTotal Fees: ₹{fees_total:,.2f}\nFees Paid: ₹{fees_paid:,.2f}\nBalance Due: ₹{balance:,.2f}\n\n📍 Pickup Address: {student_data.get('pickup_address') or 'Self pickup'}\n📝 Notes: {student_data.get('notes') or 'None'}"
                        }
                    }
                ]
            }
        }
    ]

    payload = {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": children,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post("https://api.notion.com/v1/pages", json=payload, headers=headers, timeout=12)
        if resp.status_code in [200, 201]:
            logger.info("Successfully synced student '%s' to Notion page %s", student_data.get("name"), resp.json().get("id"))
            return True
        logger.warning("Notion API error (HTTP %d): %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.warning("Failed to sync student '%s' to Notion: %s", student_data.get("name"), e)
        return False

def sync_all_students_to_notion(include_old: bool = False) -> Dict[str, Any]:
    """Bulk syncs students into the Notion database."""
    cfg = get_notion_config()
    if not cfg.get("api_key") or not cfg.get("database_id"):
        return {"ok": False, "error": "Notion API Key or Database ID is missing"}

    client = pymongo.MongoClient(MONGO_URI)
    db = client.ridewell

    query = {} if include_old else {"status": "active"}
    students = list(db.students.find(query, {"_id": 0}))
    if include_old:
        archived = list(db.archived_students.find({}, {"_id": 0}))
        students.extend(archived)

    trainers = {t["id"]: t["name"] for t in db.users.find({"role": "trainer"}, {"id": 1, "name": 1, "_id": 0})}

    success_count = 0
    failed_count = 0

    for s in students:
        tname = trainers.get(s.get("assigned_trainer_id"), "Unassigned")
        if sync_student_to_notion(s, tname):
            success_count += 1
        else:
            failed_count += 1

    return {
        "ok": True,
        "total": len(students),
        "synced": success_count,
        "failed": failed_count,
        "message": f"Successfully synced {success_count} students to Notion database"
    }
