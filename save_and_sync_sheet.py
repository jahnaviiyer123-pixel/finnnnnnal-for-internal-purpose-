import os
import json
import urllib.request
import pymongo

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://learnanddrive:T5cYO6bCZYwYXP9w@driving.ws3cihd.mongodb.net/ridewell?retryWrites=true&w=majority"
)

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbz2c6a0llp1sPqUm5JTjroWuvdZ8q4JLcPlfJ8WKoNzItcOABNzsQRuDGWDjYZM_7R1/exec"

def main():
    print("Connecting to MongoDB Atlas...")
    client = pymongo.MongoClient(MONGO_URI)
    db = client.ridewell

    # 1. Save webhook URL into settings
    db.settings.update_one(
        {"key": "google_sheet_webhook"},
        {"$set": {"key": "google_sheet_webhook", "url": WEBHOOK_URL}},
        upsert=True
    )
    print("✓ Successfully saved Google Sheets webhook URL to database settings!")

    # 2. Fetch all active students and trainers
    students = list(db.students.find({"status": "active"}, {"_id": 0}))
    trainers = {t["id"]: t["name"] for t in db.users.find({"role": "trainer"}, {"id": 1, "name": 1, "_id": 0})}
    print(f"Found {len(students)} active students in database to sync into Google Sheets.")

    success_count = 0
    fail_count = 0

    for idx, s in enumerate(students, 1):
        trainer_name = trainers.get(s.get("assigned_trainer_id"), "Unassigned")
        fees_total = float(s.get("fees_total") or 0)
        fees_paid = float(s.get("fees_paid") or 0)
        balance = max(0.0, fees_total - fees_paid)

        payload = {
            "action": "sync_student",
            "student_id": s.get("id", ""),
            "name": s.get("name", ""),
            "phone": s.get("phone", ""),
            "email": s.get("email") or "",
            "branch": s.get("location") or "Khajaguda",
            "slot_time": s.get("slot_time") or "",
            "joining_date": s.get("joining_date") or "",
            "trainer": trainer_name,
            "total_classes": s.get("total_classes", 12),
            "fees_total": fees_total,
            "fees_paid": fees_paid,
            "balance_due": balance,
            "license_type": s.get("license_type", "4W"),
            "needs_pickup": "Yes" if s.get("needs_pickup") else "No",
            "pickup_address": s.get("pickup_address") or "",
            "status": s.get("status", "active"),
            "notes": s.get("notes") or "",
            "timestamp": s.get("created_at") or ""
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                WEBHOOK_URL,
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                if response.status in [200, 201, 302]:
                    success_count += 1
                    print(f"  [{idx}/{len(students)}] Synced {s.get('name')} ({s.get('location')}) - HTTP {response.status}")
                else:
                    fail_count += 1
                    print(f"  [{idx}/{len(students)}] Failed {s.get('name')} - HTTP {response.status}")
        except Exception as e:
            fail_count += 1
            print(f"  [{idx}/{len(students)}] Error syncing {s.get('name')}: {e}")

    print("\n==========================================")
    print(f"🎉 SYNC COMPLETED: {success_count} of {len(students)} students synced successfully to Google Sheet!")
    if fail_count > 0:
        print(f"⚠️ {fail_count} students encountered an error.")
    print("==========================================")

if __name__ == "__main__":
    main()
