"""End-to-end backend tests for RideWell Ops.

Covers: auth (admin/trainer), trainers CRUD with RBAC, students with auto class slots,
class updates, attendance upsert, payments + fees increment, dashboard stats and daily reports.
"""
import os
import uuid
from datetime import date

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://fleet-ops-89.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "admin@ridewell.com", "password": "admin123"}
TRAINER = {"email": "trainer@ridewell.com", "password": "trainer123"}
MANAGER = {"email": "manager@ridewell.com", "password": "manager123"}


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data and "user" in data
    assert data["user"]["role"] == "admin"
    return data["access_token"]


@pytest.fixture(scope="session")
def manager_token():
    r = requests.post(f"{API}/auth/login", json=MANAGER, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data and "user" in data
    assert data["user"]["role"] == "manager"
    return data["access_token"]


@pytest.fixture(scope="session")
def trainer_token():
    r = requests.post(f"{API}/auth/login", json=TRAINER, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def trainer_user(trainer_token):
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {trainer_token}"}, timeout=20)
    assert r.status_code == 200
    return r.json()


def _ah(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Auth ----------
class TestAuth:
    def test_admin_login(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_trainer_login(self, trainer_token):
        assert isinstance(trainer_token, str) and len(trainer_token) > 20

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": "x@x.com", "password": "wrong"}, timeout=20)
        assert r.status_code == 401

    def test_me_admin(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200
        u = r.json()
        assert u["email"] == "admin@ridewell.com"
        assert u["role"] == "admin"
        assert "password_hash" not in u

    def test_me_unauth(self):
        r = requests.get(f"{API}/auth/me", timeout=20)
        assert r.status_code == 401


# ---------- Trainers ----------
class TestTrainers:
    created_id = None

    def test_list_trainers_seeded(self, admin_token):
        r = requests.get(f"{API}/trainers", headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200
        trainers = r.json()
        assert any(t["email"] == "trainer@ridewell.com" for t in trainers)
        for t in trainers:
            assert "password_hash" not in t

    def test_create_trainer_admin(self, admin_token):
        email = f"test_trainer_{uuid.uuid4().hex[:6]}@ridewell.com"
        body = {"email": email, "password": "pwd12345", "name": "TEST Trainer", "phone": "+91 99999"}
        r = requests.post(f"{API}/trainers", json=body, headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["email"] == email
        assert t["role"] == "trainer"
        assert "password_hash" not in t
        assert "_id" not in t
        TestTrainers.created_id = t["id"]

    def test_create_trainer_manager(self, manager_token):
        email = f"mgr_created_{uuid.uuid4().hex[:6]}@ridewell.com"
        body = {"email": email, "password": "pwd12345", "name": "Manager Added Trainer", "phone": "+91 88888"}
        r = requests.post(f"{API}/trainers", json=body, headers=_ah(manager_token), timeout=20)
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["role"] == "trainer"
        assert t["name"] == "Manager Added Trainer"

    def test_create_trainer_forbidden_for_trainer(self, trainer_token):
        body = {"email": f"TEST_x_{uuid.uuid4().hex[:5]}@x.com", "password": "p", "name": "x"}
        r = requests.post(f"{API}/trainers", json=body, headers=_ah(trainer_token), timeout=20)
        assert r.status_code == 403

    def test_patch_trainer(self, admin_token):
        assert TestTrainers.created_id
        r = requests.patch(
            f"{API}/trainers/{TestTrainers.created_id}",
            json={"name": "TEST Renamed", "phone": "+91 11111"},
            headers=_ah(admin_token), timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "TEST Renamed"

    def test_delete_trainer(self, admin_token):
        assert TestTrainers.created_id
        r = requests.delete(f"{API}/trainers/{TestTrainers.created_id}", headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200
        # Verify removal
        r2 = requests.get(f"{API}/trainers", headers=_ah(admin_token), timeout=20)
        assert not any(t["id"] == TestTrainers.created_id for t in r2.json())


# ---------- Students + Classes ----------
class TestStudentsAndClasses:
    student_id = None
    class_id = None

    def test_create_student_with_10_class_slots(self, admin_token, trainer_user):
        body = {
            "name": "TEST Student",
            "phone": "9999900000",
            "license_type": "gearless",
            "joining_date": date.today().isoformat(),
            "total_classes": 10,
            "assigned_trainer_id": trainer_user["id"],
            "fees_total": 5000,
            "fees_paid": 0,
        }
        r = requests.post(f"{API}/students", json=body, headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["name"] == "TEST Student"
        TestStudentsAndClasses.student_id = s["id"]

        # 10 class slots
        rc = requests.get(f"{API}/students/{s['id']}/classes", headers=_ah(admin_token), timeout=20)
        assert rc.status_code == 200
        classes = rc.json()
        assert len(classes) == 10
        nums = sorted(c["class_number"] for c in classes)
        assert nums == list(range(1, 11))
        TestStudentsAndClasses.class_id = classes[0]["id"]

    def test_list_students_has_classes_completed(self, admin_token):
        r = requests.get(f"{API}/students", headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200
        students = r.json()
        ours = [s for s in students if s["id"] == TestStudentsAndClasses.student_id]
        assert ours and "classes_completed" in ours[0]
        assert ours[0]["classes_completed"] == 0

    def test_patch_student(self, admin_token):
        r = requests.patch(
            f"{API}/students/{TestStudentsAndClasses.student_id}",
            json={"notes": "TEST note", "phone": "9876543210"},
            headers=_ah(admin_token), timeout=20,
        )
        assert r.status_code == 200
        assert r.json()["notes"] == "TEST note"
        assert r.json()["phone"] == "9876543210"

    def test_patch_class(self, trainer_token, trainer_user):
        today = date.today().isoformat()
        r = requests.patch(
            f"{API}/classes/{TestStudentsAndClasses.class_id}",
            json={"status": "completed", "completed_date": today,
                  "trainer_id": trainer_user["id"], "notes": "good"},
            headers=_ah(trainer_token), timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "completed"
        assert r.json()["completed_date"] == today

        # classes_completed bump verified via list
        r2 = requests.get(f"{API}/students", headers=_ah(trainer_token), timeout=20)
        ours = [s for s in r2.json() if s["id"] == TestStudentsAndClasses.student_id][0]
        assert ours["classes_completed"] == 1

    def test_trainer_can_create_student_with_12_working_days(self, trainer_token, trainer_user):
        body = {
            "name": "Trainer Added Student",
            "phone": "9999911111",
            "license_type": "geared",
            "joining_date": date.today().isoformat(),
            "total_classes": 12,
        }
        r = requests.post(f"{API}/students", json=body, headers=_ah(trainer_token), timeout=20)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["name"] == "Trainer Added Student"
        assert s["total_classes"] == 12

        # Verify 12 classes were created and scheduled on working days (no Sundays)
        rc = requests.get(f"{API}/students/{s['id']}/classes", headers=_ah(trainer_token), timeout=20)
        assert rc.status_code == 200
        classes = rc.json()
        assert len(classes) == 12
        for c in classes:
            if c.get("scheduled_date"):
                dt = datetime.strptime(c["scheduled_date"], "%Y-%m-%d")
                assert dt.weekday() != 6, f"Class scheduled on Sunday: {c['scheduled_date']}"

    def test_get_student_invoice(self, admin_token):
        sid = TestStudentsAndClasses.student_id
        r = requests.get(f"{API}/students/{sid}/invoice", headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        inv = r.json()
        assert inv["invoice_number"].startswith("RW-INV-")
        assert "school" in inv
        assert "student" in inv
        assert "allotment" in inv
        assert "schedule" in inv
        assert "financials" in inv
        assert "instructions" in inv
        assert len(inv["instructions"]) > 0

    def test_trainer_cannot_delete_student(self, trainer_token):
        r = requests.delete(
            f"{API}/students/{TestStudentsAndClasses.student_id}",
            headers=_ah(trainer_token), timeout=20,
        )
        assert r.status_code == 403


# ---------- Attendance ----------
class TestAttendance:
    def test_upsert_and_filter(self, admin_token, trainer_user):
        today = date.today().isoformat()
        body = {"trainer_id": trainer_user["id"], "date": today, "status": "present", "notes": "ok"}
        r = requests.post(f"{API}/attendance", json=body, headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["status"] == "present"

        # Upsert again with different status
        r2 = requests.post(f"{API}/attendance",
                           json={**body, "status": "leave"},
                           headers=_ah(admin_token), timeout=20)
        assert r2.status_code == 200
        assert r2.json()["status"] == "leave"

        # Filter by date
        r3 = requests.get(f"{API}/attendance?date={today}", headers=_ah(admin_token), timeout=20)
        assert r3.status_code == 200
        recs = r3.json()
        assert any(a["trainer_id"] == trainer_user["id"] and a["date"] == today for a in recs)

    def test_trainer_cannot_mark_attendance(self, trainer_token, trainer_user):
        """Trainers must NOT be able to mark attendance for themselves or others."""
        today = date.today().isoformat()
        body = {"trainer_id": trainer_user["id"], "date": today, "status": "present"}
        r = requests.post(f"{API}/attendance", json=body, headers=_ah(trainer_token), timeout=20)
        assert r.status_code == 403, f"Expected 403 forbidden for trainer self-marking, got {r.status_code}"

    def test_manager_can_mark_attendance(self, manager_token, trainer_user):
        """Manager (subadmin) can mark attendance for trainers."""
        today = date.today().isoformat()
        body = {"trainer_id": trainer_user["id"], "date": today, "status": "present", "notes": "marked by manager"}
        r = requests.post(f"{API}/attendance", json=body, headers=_ah(manager_token), timeout=20)
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["status"] == "present"
        assert rec["marked_by_role"] == "manager"


# ---------- Payments ----------
class TestPayments:
    def test_create_payment_increments_fees(self, admin_token):
        sid = TestStudentsAndClasses.student_id
        # before
        before = requests.get(f"{API}/students/{sid}", headers=_ah(admin_token), timeout=20).json()
        paid_before = float(before.get("fees_paid", 0))

        body = {"student_id": sid, "amount": 1500, "date": date.today().isoformat(),
                "method": "cash", "notes": "TEST pay"}
        r = requests.post(f"{API}/payments", json=body, headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["amount"] == 1500

        after = requests.get(f"{API}/students/{sid}", headers=_ah(admin_token), timeout=20).json()
        assert float(after["fees_paid"]) == pytest.approx(paid_before + 1500)

    def test_payments_forbidden_for_manager(self, manager_token):
        r = requests.get(f"{API}/payments", headers=_ah(manager_token), timeout=20)
        assert r.status_code == 403, "Payments must be forbidden for manager"

    def test_payments_forbidden_for_trainer(self, trainer_token):
        r = requests.get(f"{API}/payments", headers=_ah(trainer_token), timeout=20)
        assert r.status_code == 403, "Payments must be forbidden for trainer"


# ---------- Dashboard / Reports ----------
class TestDashboardAndReports:
    def test_dashboard_stats(self, admin_token):
        r = requests.get(f"{API}/dashboard/stats", headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200
        d = r.json()
        for key in ["total_students", "active_students", "total_trainers",
                    "classes_today", "present_today", "absent_today",
                    "fees_total", "fees_paid", "fees_pending"]:
            assert key in d
        assert d["total_students"] >= 1
        assert d["total_trainers"] >= 1
        assert d["classes_today"] >= 1  # we completed one above

    def test_daily_report(self, admin_token):
        today = date.today().isoformat()
        r = requests.get(f"{API}/reports/daily?date={today}", headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200
        rep = r.json()
        assert rep["date"] == today
        assert isinstance(rep["classes"], list)
        assert isinstance(rep["attendance"], list)
        assert isinstance(rep["payments"], list)
        assert any(p.get("amount") == 1500 for p in rep["payments"])

    def test_weekly_report_summary_admin(self, admin_token):
        r = requests.get(f"{API}/reports/summary?period=weekly&location=Khajaguda", headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["period"] == "weekly"
        assert data["location"] == "Khajaguda"
        assert "summary" in data
        assert "classes_conducted" in data["summary"]
        assert "new_enrollments" in data["summary"]
        assert "trainer_performance" in data
        assert isinstance(data["trainer_performance"], list)
        # Admin can view total fees collected
        assert "total_fees_collected" in data["summary"]
        assert "payments" in data

    def test_weekly_report_summary_manager(self, manager_token):
        r = requests.get(f"{API}/reports/summary?period=weekly", headers=_ah(manager_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["period"] == "weekly"
        # Manager fees must NOT be exposed
        assert data["summary"]["total_fees_collected"] is None
        assert data["payments"] == []

    def test_monthly_report_summary(self, admin_token):
        r = requests.get(f"{API}/reports/summary?period=monthly", headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data["period"] == "monthly"
        assert "daily_progression" in data


# ---------- Locations & Multi-Location Isolation ----------
class TestLocationsAndLocationIsolation:
    def test_list_locations(self, admin_token):
        r = requests.get(f"{API}/locations", headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200
        locs = r.json()
        assert isinstance(locs, list)
        assert "Khajaguda" in locs

    def test_trainer_cannot_access_student_outside_location(self, trainer_token, admin_token):
        # Admin creates student in a different location (Kondapur)
        body = {
            "name": "Kondapur Student",
            "phone": "+91 99999 88888",
            "joining_date": date.today().isoformat(),
            "location": "Kondapur",
            "total_classes": 10,
        }
        r = requests.post(f"{API}/students", json=body, headers=_ah(admin_token), timeout=20)
        assert r.status_code == 200
        kondapur_student_id = r.json()["id"]

        try:
            # Trainer (in Khajaguda) tries to access Kondapur student directly -> 403 Forbidden
            r_trainer = requests.get(f"{API}/students/{kondapur_student_id}", headers=_ah(trainer_token), timeout=20)
            assert r_trainer.status_code in (403, 404), f"Expected 403 or 404 for cross-location access, got {r_trainer.status_code}"
            
            # Trainer listing students does not see Kondapur student
            r_list = requests.get(f"{API}/students", headers=_ah(trainer_token), timeout=20)
            assert r_list.status_code == 200
            student_ids = [s["id"] for s in r_list.json()]
            assert kondapur_student_id not in student_ids
        finally:
            # Cleanup test student
            requests.delete(f"{API}/students/{kondapur_student_id}", headers=_ah(admin_token), timeout=20)


# ---------- Holidays, Functions & Calendar ----------
class TestHolidaysAndCalendar:
    holiday_id = None
    holiday_date = "2026-12-25"

    def test_compute_working_days_skips_sundays_and_holidays(self):
        from server import compute_working_days
        # Start on Friday 2026-10-30:
        # Friday (10-30): Day 1
        # Saturday (10-31): Day 2
        # Sunday (11-01): SKIPPED (Sunday)
        # Monday (11-02): declared holiday -> SKIPPED
        # Tuesday (11-03): Day 3
        hols = {"2026-11-02"}
        days = compute_working_days("2026-10-30", 3, holiday_dates=hols)
        assert days == ["2026-10-30", "2026-10-31", "2026-11-03"], f"Unexpected working days: {days}"

    def test_manager_can_create_holiday(self, manager_token):
        body = {
            "date": TestHolidaysAndCalendar.holiday_date,
            "title": "Christmas Holiday",
            "type": "holiday",
            "notes": "Driving school closed for Christmas",
        }
        r = requests.post(f"{API}/holidays", json=body, headers=_ah(manager_token), timeout=20)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["date"] == TestHolidaysAndCalendar.holiday_date
        assert doc["title"] == "Christmas Holiday"
        TestHolidaysAndCalendar.holiday_id = doc["id"]

    def test_trainer_cannot_create_holiday(self, trainer_token):
        body = {
            "date": "2026-12-26",
            "title": "Boxing Day",
            "type": "holiday",
        }
        r = requests.post(f"{API}/holidays", json=body, headers=_ah(trainer_token), timeout=20)
        assert r.status_code == 403

    def test_list_holidays(self, trainer_token):
        r = requests.get(f"{API}/holidays?year=2026&month=12", headers=_ah(trainer_token), timeout=20)
        assert r.status_code == 200
        hols = r.json()
        assert any(h["date"] == TestHolidaysAndCalendar.holiday_date for h in hols)

    def test_schedule_today_returns_holiday_info(self, trainer_token):
        r = requests.get(f"{API}/schedule/today?date={TestHolidaysAndCalendar.holiday_date}", headers=_ah(trainer_token), timeout=20)
        assert r.status_code == 200
        res = r.json()
        assert res.get("holiday") is not None
        assert res["holiday"]["title"] == "Christmas Holiday"

    def test_delete_holiday(self, manager_token):
        if TestHolidaysAndCalendar.holiday_id:
            r = requests.delete(f"{API}/holidays/{TestHolidaysAndCalendar.holiday_id}", headers=_ah(manager_token), timeout=20)
            assert r.status_code == 200


# ---------- Cleanup ----------
def test_zz_cleanup_admin_deletes_student(admin_token=None):
    # Use a fresh login to ensure availability post-tests
    tok = requests.post(f"{API}/auth/login", json=ADMIN, timeout=20).json()["access_token"]
    sid = TestStudentsAndClasses.student_id
    if sid:
        r = requests.delete(f"{API}/students/{sid}", headers={"Authorization": f"Bearer {tok}"}, timeout=20)
        assert r.status_code == 200
