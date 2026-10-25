import os
import json
import urllib.request
import urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://trainers.learnanddrive.club/api"
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups", datetime.now().strftime("%Y%m%d_%H%M%S"))
os.makedirs(BACKUP_DIR, exist_ok=True)

print(f"[*] Starting complete backup to: {BACKUP_DIR}")

def make_request(endpoint, method="GET", data=None, token=None, timeout=120):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    body = json.dumps(data).encode("utf-8") if data else None
    with urllib.request.urlopen(req, data=body, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))

# 1. Login
login_data = make_request("/auth/login", method="POST", data={
    "email": "admin@ridewell.com",
    "password": "admin123"
})
token = login_data["access_token"]
print("[✓] Authenticated as Admin")

def save_json(filename, data):
    path = os.path.join(BACKUP_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[✓] Saved {filename} ({len(data) if isinstance(data, list) else 1} items)")

# 2. Fetch Trainers
print("[*] Fetching trainers...")
trainers = make_request("/trainers", token=token)
save_json("trainers.json", trainers)

# 3. Fetch Payments
print("[*] Fetching payments...")
payments = make_request("/payments", token=token)
save_json("payments.json", payments)

# 4. Fetch Attendance
print("[*] Fetching attendance...")
attendance = make_request("/attendance", token=token)
save_json("attendance.json", attendance)

# 5. Fetch Slots
print("[*] Fetching slots...")
slots = make_request("/slots", token=token)
save_json("slots.json", slots)

# 6. Fetch Students (takes ~60s due to unoptimized live N+1 loop)
print("[*] Fetching all students (waiting for live server)...")
students = make_request("/students", token=token, timeout=180)
save_json("students.json", students)

# 7. Fetch Classes in parallel (fast!)
print(f"[*] Fetching classes for all {len(students)} students in parallel...")
all_classes = []

def fetch_classes(s):
    sid = s.get("id")
    if not sid:
        return []
    try:
        return make_request(f"/students/{sid}/classes", token=token, timeout=30)
    except Exception as e:
        print(f"[!] Error fetching classes for {sid}: {e}")
        return []

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(fetch_classes, s) for s in students]
    for f in as_completed(futures):
        res = f.result()
        if res:
            all_classes.extend(res)

save_json("classes.json", all_classes)

# Manifest
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
print(f"\n[🎉] FULL DATABASE BACKUP COMPLETE!\n{json.dumps(manifest['counts'], indent=2)}")
