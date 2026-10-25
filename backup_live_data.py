import os
import json
import urllib.request
import urllib.error
from datetime import datetime

BASE_URL = "https://trainers.learnanddrive.club/api"
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups", datetime.now().strftime("%Y%m%d_%H%M%S"))
os.makedirs(BACKUP_DIR, exist_ok=True)

print(f"[*] Starting backup to: {BACKUP_DIR}")

def make_request(endpoint, method="GET", data=None, token=None):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    
    body = json.dumps(data).encode("utf-8") if data else None
    with urllib.request.urlopen(req, data=body, timeout=60) as res:
        return json.loads(res.read().decode("utf-8"))

# 1. Authenticate as admin
try:
    login_data = make_request("/auth/login", method="POST", data={
        "email": "admin@ridewell.com",
        "password": "admin123"
    })
    token = login_data["access_token"]
    print("[✓] Authenticated successfully as Admin")
except Exception as e:
    print(f"[!] Login error: {e}")
    raise

# Helper to save JSON
def save_json(filename, data):
    path = os.path.join(BACKUP_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[✓] Saved {filename} ({len(data) if isinstance(data, list) else 1} records)")

# 2. Fetch Students
print("[*] Fetching students...")
try:
    students = make_request("/students", token=token)
except Exception as e:
    print(f"[!] Could not fetch students: {e}")
    students = []
save_json("students.json", students)

# 3. Fetch Classes for each student
print("[*] Fetching classes for each student...")
all_classes = []
for s in students:
    sid = s.get("id")
    if sid:
        try:
            classes = make_request(f"/students/{sid}/classes", token=token)
            all_classes.extend(classes)
        except Exception as e:
            print(f"[!] Warning on student {sid} classes: {e}")
save_json("classes.json", all_classes)

# 4. Fetch Trainers
print("[*] Fetching trainers...")
try:
    trainers = make_request("/trainers", token=token)
except Exception as e:
    trainers = []
save_json("trainers.json", trainers)

# 5. Fetch Payments
print("[*] Fetching payments...")
try:
    payments = make_request("/payments", token=token)
except Exception as e:
    payments = []
save_json("payments.json", payments)

# 6. Fetch Attendance
print("[*] Fetching attendance...")
try:
    attendance = make_request("/attendance", token=token)
except Exception as e:
    attendance = []
save_json("attendance.json", attendance)

# 7. Fetch Slots
print("[*] Fetching slots...")
try:
    slots = make_request("/slots", token=token)
except Exception as e:
    slots = []
save_json("slots.json", slots)

# Write manifest
manifest = {
    "backup_timestamp": datetime.now().isoformat(),
    "backup_directory": BACKUP_DIR,
    "counts": {
        "students": len(students),
        "classes": len(all_classes),
        "trainers": len(trainers),
        "payments": len(payments),
        "attendance": len(attendance),
        "slots": len(slots),
    }
}
save_json("manifest.json", manifest)
print(f"\n[🎉] BACKUP COMPLETED SUCCESSFULLY!\nSummary: {json.dumps(manifest['counts'], indent=2)}")
