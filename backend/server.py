from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import re
import time
import uuid
import logging
import asyncio
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Query
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

# ---------- Hostinger Email & Marketing Services ----------
try:
    from backend.email_service import (
        send_smtp_email,
        send_enrollment_email,
        send_payment_receipt_email,
        get_email_config_status,
        is_smtp_configured
    )
    from backend.hostinger_reach_service import (
        sync_contacts_to_reach,
        get_reach_summary
    )
    from backend.n8n_service import (
        dispatch_n8n_event,
        is_n8n_configured
    )
    from backend.google_sheets_service import (
        sync_student_to_google_sheet,
        sync_all_active_students_to_sheet,
        is_sheets_sync_enabled
    )
    from backend.notion_service import (
        sync_student_to_notion,
        sync_all_students_to_notion,
        get_notion_config,
        is_notion_configured,
        clean_database_id
    )
except ImportError:
    from email_service import (
        send_smtp_email,
        send_enrollment_email,
        send_payment_receipt_email,
        get_email_config_status,
        is_smtp_configured
    )
    from hostinger_reach_service import (
        sync_contacts_to_reach,
        get_reach_summary
    )
    from n8n_service import (
        dispatch_n8n_event,
        is_n8n_configured
    )
    from google_sheets_service import (
        sync_student_to_google_sheet,
        sync_all_active_students_to_sheet,
        is_sheets_sync_enabled
    )
    from notion_service import (
        sync_student_to_notion,
        sync_all_students_to_notion,
        get_notion_config,
        is_notion_configured,
        clean_database_id
    )


# ---------- DB ----------
mongo_url = os.environ.get("MONGO_URL")
db_name = os.environ.get("DB_NAME")
if not mongo_url or not db_name:
    missing = []
    if not mongo_url:
        missing.append("MONGO_URL")
    if not db_name:
        missing.append("DB_NAME")
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
_mongo_client_kwargs = {
    # Fail fast (important for local dev + serverless cold starts)
    "serverSelectionTimeoutMS": 5000,
    "connectTimeoutMS": 5000,
}
try:
    import certifi
    is_local = "localhost" in mongo_url or "127.0.0.1" in mongo_url
    has_tls = "tls=true" in mongo_url.lower() or "ssl=true" in mongo_url.lower() or "mongodb+srv" in mongo_url
    if not is_local or has_tls:
        client = AsyncIOMotorClient(mongo_url, tlsCAFile=certifi.where(), **_mongo_client_kwargs)
    else:
        client = AsyncIOMotorClient(mongo_url, **_mongo_client_kwargs)
except ImportError:
    client = AsyncIOMotorClient(mongo_url, **_mongo_client_kwargs)
db = client[db_name]

# ---------- App ----------
app = FastAPI(title="RideWell Ops")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ridewell")

# ---------- Auth helpers ----------
JWT_SECRET = os.environ.get("JWT_SECRET", "devsecret")
JWT_ALG = "HS256"
ACCESS_MIN = 60 * 12  # 12 hours


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_MIN),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


_user_cache = {}  # user_id -> (user_dict, timestamp)
_stats_cache = {}  # cache_key -> {"data": dict, "timestamp": float}
_slots_cache = {"timestamp": 0, "data": None}
_trainers_cache = {}  # cache_key -> {"time": ts, "data": list}

def invalidate_stats():
    _stats_cache.clear()

def invalidate_slots():
    _slots_cache["timestamp"] = 0

def invalidate_trainers():
    _trainers_cache.clear()


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        token = request.query_params.get("auth") or request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    now = time.time()
    cached = _user_cache.get(user_id)
    if cached and (now - cached[1]) < 60:
        return cached[0]

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.get("status") and user["status"] != "active":
        raise HTTPException(status_code=403, detail="Account is not active")

    _user_cache[user_id] = (user, now)
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_manager_or_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Manager or admin access required")
    return user


# ---------- Models ----------
class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: Literal["admin", "manager", "trainer"]
    location: Optional[str] = None
    phone: Optional[str] = None
    created_at: str


class ManagerCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    location: Optional[str] = None
    phone: Optional[str] = None


class ManagerUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None


class UserLocationUpdate(BaseModel):
    location: Optional[str] = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TrainerCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    location: Optional[str] = "Khajaguda"
    phone: Optional[str] = None
    shift: Optional[Literal["morning", "afternoon", "both"]] = "both"
    salary_type: Optional[Literal["part_time", "full_time"]] = "full_time"
    base_salary: Optional[int] = 0


class TrainerRegister(BaseModel):
    """Self-signup by trainer — creates a pending account that admin must approve."""
    email: EmailStr
    password: str
    name: str
    location: Optional[str] = "Khajaguda"
    phone: Optional[str] = None


class TrainerUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    photo_url: Optional[str] = None
    shift: Optional[Literal["morning", "afternoon", "both"]] = None
    salary_type: Optional[Literal["part_time", "full_time"]] = None
    base_salary: Optional[int] = None


class StudentCreate(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    age: Optional[int] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    license_type: Literal["gearless", "geared", "both"] = "gearless"
    joining_date: str  # ISO date
    slot_time: Optional[str] = None
    location: Optional[str] = "Khajaguda"
    needs_pickup: bool = False
    pickup_address: Optional[str] = None
    drop_address: Optional[str] = None
    total_classes: int = 10
    assigned_trainer_id: Optional[str] = None
    pickup_trainer_id: Optional[str] = None
    drop_trainer_id: Optional[str] = None
    photo_url: Optional[str] = None
    fees_total: float = 0
    fees_paid: float = 0
    notes: Optional[str] = None


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    age: Optional[int] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    license_type: Optional[Literal["gearless", "geared", "both"]] = None
    joining_date: Optional[str] = None
    slot_time: Optional[str] = None
    location: Optional[str] = None
    needs_pickup: Optional[bool] = None
    pickup_address: Optional[str] = None
    drop_address: Optional[str] = None
    total_classes: Optional[int] = None
    assigned_trainer_id: Optional[str] = None
    pickup_trainer_id: Optional[str] = None
    drop_trainer_id: Optional[str] = None
    photo_url: Optional[str] = None
    fees_total: Optional[float] = None
    fees_paid: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[Literal["active", "completed", "dropped"]] = None


class SlotCreate(BaseModel):
    label: str  # e.g. "06:00-07:00"
    start_time: str  # "06:00"
    end_time: str  # "07:00"


class ClassUpdate(BaseModel):
    scheduled_date: Optional[str] = None
    completed_date: Optional[str] = None
    trainer_id: Optional[str] = None
    status: Optional[Literal["pending", "completed", "missed", "absent"]] = None
    notes: Optional[str] = None


class AttendanceCreate(BaseModel):
    trainer_id: str
    date: str
    status: Literal["present", "absent", "leave"]
    notes: Optional[str] = None


class PaymentCreate(BaseModel):
    student_id: str
    amount: float
    date: str
    method: Literal["cash", "upi", "card", "bank"] = "cash"
    notes: Optional[str] = None


class PaymentUpdate(BaseModel):
    amount: Optional[float] = None
    date: Optional[str] = None
    method: Optional[Literal["cash", "upi", "card", "bank"]] = None
    notes: Optional[str] = None


class HolidayCreate(BaseModel):
    date: str  # YYYY-MM-DD
    title: str
    type: Literal["holiday", "function"] = "holiday"
    location: Optional[str] = None  # None = All branches
    notes: Optional[str] = None


# ---------- Startup / Seed ----------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@ridewell.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Admin",
            "role": "admin",
            "status": "active",
            "phone": None,
            "photo_url": None,
            "created_at": _now_iso(),
        })
        logger.info("Seeded admin user")
    else:
        updates = {}
        if not verify_password(admin_password, existing["password_hash"]):
            updates["password_hash"] = hash_password(admin_password)
        if existing.get("status") != "active":
            updates["status"] = "active"
        if updates:
            await db.users.update_one({"email": admin_email}, {"$set": updates})


    # Seed demo manager (subadmin)
    manager_email = os.environ.get("MANAGER_EMAIL", "manager@ridewell.com").lower()
    manager_password = os.environ.get("MANAGER_PASSWORD", "manager123")
    existing_mgr = await db.users.find_one({"email": manager_email})
    if not existing_mgr:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": manager_email,
            "password_hash": hash_password(manager_password),
            "name": "Branch Manager",
            "role": "manager",
            "status": "active",
            "location": "",
            "phone": "+91 98765 43211",
            "photo_url": None,
            "created_at": _now_iso(),
        })
        logger.info("Seeded demo manager user")
    else:
        updates = {}
        if existing_mgr.get("role") != "manager":
            updates["role"] = "manager"
        if existing_mgr.get("status") != "active":
            updates["status"] = "active"
        if not verify_password(manager_password, existing_mgr["password_hash"]):
            updates["password_hash"] = hash_password(manager_password)
        if updates:
            await db.users.update_one({"email": manager_email}, {"$set": updates})

    # Backfill legacy students and trainers without location to default location
    await db.students.update_many({"location": {"$exists": False}}, {"$set": {"location": "Khajaguda"}})
    await db.users.update_many({"role": "trainer", "location": {"$exists": False}}, {"$set": {"location": "Khajaguda"}})


async def seed_default_slots():
    if await db.slots.count_documents({}) > 0:
        return
    defaults = [
        ("06:00-07:00", "06:00", "07:00"),
        ("07:00-08:00", "07:00", "08:00"),
        ("08:00-09:00", "08:00", "09:00"),
        ("17:00-18:00", "17:00", "18:00"),
        ("18:00-19:00", "18:00", "19:00"),
    ]
    for label, st, en in defaults:
        await db.slots.insert_one({
            "id": str(uuid.uuid4()),
            "label": label,
            "start_time": st,
            "end_time": en,
            "created_at": _now_iso(),
        })


async def _safe_create_index(collection, keys, **kwargs):
    """Create index, dropping conflicting one if needed."""
    try:
        await collection.create_index(keys, **kwargs)
    except Exception as e:
        if "IndexKeySpecsConflict" in str(e) or "already exists" in str(e):
            if isinstance(keys, str):
                index_name = f"{keys}_1"
            else:
                index_name = "_".join(f"{k}_{v}" for k, v in keys)
            try:
                await collection.drop_index(index_name)
                await collection.create_index(keys, **kwargs)
                logger.info("Recreated index %s", index_name)
            except Exception as e2:
                logger.warning("Could not recreate index: %s", e2)
        else:
            logger.warning("Index creation issue (non-fatal): %s", e)


_indexes_initialized = False


async def _init_db_in_background():
    global _indexes_initialized
    if _indexes_initialized:
        return
    try:
        await _safe_create_index(db.users, "id", unique=True)
        await _safe_create_index(db.users, "email", unique=True)
        await _safe_create_index(db.users, "role")
        await _safe_create_index(db.users, "location")

        await _safe_create_index(db.students, "id", unique=True)
        await _safe_create_index(db.students, "status")
        await _safe_create_index(db.students, "location")
        await _safe_create_index(db.students, [("location", 1), ("status", 1), ("joining_date", -1)])
        await _safe_create_index(db.students, [("joining_date", -1)])
        await _safe_create_index(db.students, "assigned_trainer_id")

        await _safe_create_index(db.classes, [("student_id", 1), ("class_number", 1)], unique=True)
        await _safe_create_index(db.classes, [("student_id", 1), ("status", 1)])
        await _safe_create_index(db.classes, [("student_id", 1), ("scheduled_date", 1)])
        await _safe_create_index(db.classes, [("student_id", 1), ("completed_date", 1)])
        await _safe_create_index(db.classes, "status")
        await _safe_create_index(db.classes, "completed_date")
        await _safe_create_index(db.classes, "scheduled_date")
        await _safe_create_index(db.classes, [("trainer_id", 1), ("completed_date", 1)])

        await _safe_create_index(db.attendance, [("trainer_id", 1), ("date", 1)], unique=True)
        await _safe_create_index(db.attendance, [("date", 1), ("status", 1)])
        await _safe_create_index(db.attendance, "date")

        await _safe_create_index(db.payments, "id", unique=True)
        await _safe_create_index(db.payments, [("student_id", 1), ("date", -1)])
        await _safe_create_index(db.payments, [("date", -1)])

        await _safe_create_index(db.slots, "label", unique=True)
        await _safe_create_index(db.holidays, [("date", 1), ("location", 1)])
        await _safe_create_index(db.holidays, "id", unique=True)
        await seed_admin()
        await seed_default_slots()
        _indexes_initialized = True
        logger.info("Database indexes and seeds initialized in background")
    except Exception as e:
        logger.warning("Background DB index setup warning: %s", e)


@app.on_event("startup")
async def _startup():
    # Fire and forget in background so HTTP requests are not blocked on cold start
    asyncio.create_task(_init_db_in_background())


@app.on_event("shutdown")
async def _shutdown():
    client.close()


# ---------- Auth Endpoints ----------
def _set_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=ACCESS_MIN * 60,
        path="/",
    )


@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    status_val = user.get("status", "active")
    if status_val == "pending":
        raise HTTPException(status_code=403, detail="Account pending admin approval")
    if status_val == "rejected":
        raise HTTPException(status_code=403, detail="Account access has been revoked")
    token = create_access_token(user["id"], user["email"], user["role"])
    _set_cookie(response, token)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"], "email": user["email"], "name": user["name"],
            "role": user["role"], "location": user.get("location"),
            "phone": user.get("phone"),
            "photo_url": user.get("photo_url"),
            "status": status_val,
            "created_at": user["created_at"],
        },
    }


@api.post("/auth/register")
async def register_trainer(body: TrainerRegister):
    """Trainer self-signup. Creates a pending account that admin must approve."""
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(body.password),
        "name": body.name,
        "role": "trainer",
        "status": "pending",
        "location": body.location or "Khajaguda",
        "phone": body.phone,
        "photo_url": None,
        "created_at": _now_iso(),
    }
    await db.users.insert_one(doc)
    return {"ok": True, "message": "Registration submitted. Waiting for admin approval."}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.patch("/auth/location")
async def update_my_location(body: UserLocationUpdate, user: dict = Depends(get_current_user)):
    """Allow managers and admins to change/switch their active branch location."""
    raw_loc = (body.location or "").strip()
    if raw_loc in ("All", "All Branches", "all", "ALL BRANCHES"):
        loc = ""
    else:
        loc = raw_loc
    await db.users.update_one({"id": user["id"]}, {"$set": {"location": loc}})
    _user_cache.pop(user["id"], None)
    return await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


# ---------- Users / Trainers ----------
@api.get("/trainers")
async def list_trainers(
    status: Optional[str] = Query(None, description="active|pending|rejected"),
    location: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    cache_key = f"{status}_{location}_{user.get('role')}_{user.get('id')}"
    now = time.time()
    if cache_key in _trainers_cache and (now - _trainers_cache[cache_key]["time"] < 60):
        return _trainers_cache[cache_key]["data"]

    q = {"role": "trainer"}
    if status:
        q["status"] = status
    # non-admin / non-manager can only see active trainers
    if user.get("role") not in ("admin", "manager"):
        q["status"] = "active"

    # Location isolation: Trainers can only see trainers in their own location
    if user.get("role") == "trainer":
        trainer_loc = user.get("location")
        if trainer_loc:
            q["location"] = trainer_loc
    elif location:
        q["location"] = location

    trainers = await db.users.find(q, {"_id": 0, "password_hash": 0}).to_list(500)
    _trainers_cache[cache_key] = {"time": now, "data": trainers}
    return trainers


@api.post("/trainers")
async def create_trainer(body: TrainerCreate, user: dict = Depends(require_manager_or_admin)):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists")
    loc = body.location or user.get("location") or "Khajaguda"
    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(body.password),
        "name": body.name,
        "role": "trainer",
        "status": "active",  # admin or manager created trainers are auto-active
        "location": loc or "Khajaguda",
        "phone": body.phone,
        "photo_url": None,
        "shift": body.shift or "both",
        "salary_type": body.salary_type or "full_time",
        "base_salary": body.base_salary or 0,
        "created_at": _now_iso(),
    }
    await db.users.insert_one(doc)
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    invalidate_trainers()
    invalidate_stats()
    return doc


@api.post("/trainers/{trainer_id}/approve")
async def approve_trainer(trainer_id: str, user: dict = Depends(require_manager_or_admin)):
    res = await db.users.update_one(
        {"id": trainer_id, "role": "trainer"},
        {"$set": {"status": "active"}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Trainer not found")
    invalidate_trainers()
    invalidate_stats()
    _user_cache.pop(trainer_id, None)
    trainer = await db.users.find_one({"id": trainer_id}, {"_id": 0, "password_hash": 0})
    return trainer


@api.post("/trainers/{trainer_id}/reject")
async def reject_trainer(trainer_id: str, user: dict = Depends(require_manager_or_admin)):
    res = await db.users.update_one(
        {"id": trainer_id, "role": "trainer"},
        {"$set": {"status": "rejected"}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Trainer not found")
    invalidate_trainers()
    invalidate_stats()
    _user_cache.pop(trainer_id, None)
    trainer = await db.users.find_one({"id": trainer_id}, {"_id": 0, "password_hash": 0})
    return trainer


@api.patch("/trainers/{trainer_id}")
async def update_trainer(trainer_id: str, body: TrainerUpdate, user: dict = Depends(get_current_user)):
    # Admin or manager can edit any trainer; trainers can edit only themselves
    if user.get("role") not in ("admin", "manager") and user.get("id") != trainer_id:
        raise HTTPException(status_code=403, detail="Cannot edit other trainers")
    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.phone is not None:
        updates["phone"] = body.phone
    if body.location is not None:
        updates["location"] = body.location
    if body.password:
        updates["password_hash"] = hash_password(body.password)
    if body.photo_url is not None:
        updates["photo_url"] = body.photo_url
    if body.shift is not None:
        updates["shift"] = body.shift
    if body.salary_type is not None:
        updates["salary_type"] = body.salary_type
    if body.base_salary is not None:
        updates["base_salary"] = body.base_salary
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    res = await db.users.update_one({"id": trainer_id, "role": "trainer"}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Trainer not found")
    invalidate_trainers()
    _user_cache.pop(trainer_id, None)
    trainer = await db.users.find_one({"id": trainer_id}, {"_id": 0, "password_hash": 0})
    return trainer


@api.delete("/trainers/{trainer_id}")
async def delete_trainer(trainer_id: str, user: dict = Depends(require_manager_or_admin)):
    res = await db.users.delete_one({"id": trainer_id, "role": "trainer"})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Trainer not found")
    invalidate_trainers()
    invalidate_stats()
    _user_cache.pop(trainer_id, None)
    return {"status": "ok"}


@api.get("/trainers/{trainer_id}")
async def get_trainer(trainer_id: str, user: dict = Depends(get_current_user)):
    trainer = await db.users.find_one({"id": trainer_id, "role": "trainer"}, {"_id": 0, "password_hash": 0})
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    # Prevent trainers from inspecting trainers of different locations
    if user.get("role") == "trainer" and trainer["id"] != user["id"]:
        trainer_loc = user.get("location")
        if trainer_loc and trainer.get("location") and trainer.get("location") != trainer_loc:
            raise HTTPException(status_code=403, detail="Cannot view trainer outside your location")
    
    # Get assigned students
    students = await db.students.find({"assigned_trainer_id": trainer_id}, {"_id": 0}).to_list(100)
    
    # Get attendance history
    attendance = await db.attendance.find({"trainer_id": trainer_id}, {"_id": 0}).sort("date", -1).to_list(1000)
    
    return {
        "trainer": trainer,
        "students": students,
        "attendance": attendance,
    }


# ---------- Managers (Subadmin) ----------
@api.get("/managers")
async def list_managers(user: dict = Depends(require_admin)):
    """Admin only: list all managers."""
    managers = await db.users.find(
        {"role": "manager"}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(100)
    return managers


@api.post("/managers")
async def create_manager(body: ManagerCreate, user: dict = Depends(require_admin)):
    """Admin only: create a new manager account."""
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(body.password),
        "name": body.name,
        "role": "manager",
        "status": "active",
        "location": body.location,
        "phone": body.phone,
        "photo_url": None,
        "created_at": _now_iso(),
    }
    await db.users.insert_one(doc)
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    return doc


@api.patch("/managers/{manager_id}")
async def update_manager(manager_id: str, body: ManagerUpdate, user: dict = Depends(get_current_user)):
    """Admin or the manager themselves can update profile."""
    if user.get("role") != "admin" and user.get("id") != manager_id:
        raise HTTPException(status_code=403, detail="Cannot edit other managers")
    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.phone is not None:
        updates["phone"] = body.phone
    if body.location is not None:
        updates["location"] = body.location
    if body.password:
        updates["password_hash"] = hash_password(body.password)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    res = await db.users.update_one({"id": manager_id, "role": "manager"}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Manager not found")
    _user_cache.pop(manager_id, None)
    return await db.users.find_one({"id": manager_id, "role": "manager"}, {"_id": 0, "password_hash": 0})


@api.delete("/managers/{manager_id}")
async def delete_manager(manager_id: str, user: dict = Depends(require_admin)):
    """Admin only: delete a manager account."""
    res = await db.users.delete_one({"id": manager_id, "role": "manager"})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Manager not found")
    _user_cache.pop(manager_id, None)
    return {"status": "ok"}


# ---------- Students ----------
def compute_working_days(
    start_date_str: str,
    num_days: int,
    holiday_dates: Optional[set[str]] = None,
) -> list[str]:
    """
    Computes `num_days` consecutive working days starting from start_date_str,
    skipping Sundays (Sunday is day 6 in python weekday where Monday=0)
    and skipping any declared holidays/functions in holiday_dates.
    """
    try:
        curr = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except Exception:
        curr = date.today()
    holidays = holiday_dates or set()
    working_days = []
    safety = 0
    while len(working_days) < num_days and safety < 600:
        safety += 1
        curr_str = curr.isoformat()
        if curr.weekday() != 6 and curr_str not in holidays:  # Skip Sundays and declared holidays/functions
            working_days.append(curr_str)
        curr += timedelta(days=1)
    return working_days


async def _create_class_slots(
    student_id: str,
    total: int,
    trainer_id: Optional[str],
    joining_date: Optional[str] = None,
    location: Optional[str] = None,
):
    total_classes = total or 10
    h_query = {"$or": [{"location": None}, {"location": ""}]}
    if location:
        h_query = {"$or": [{"location": None}, {"location": ""}, {"location": location}]}
    try:
        hols = await db.holidays.find(h_query, {"date": 1, "_id": 0}).to_list(1000)
        holiday_dates = {h["date"] for h in hols if "date" in h}
    except Exception as e:
        logger.warning("Could not fetch holidays for class slots: %s", e)
        holiday_dates = set()

    working_days = compute_working_days(
        joining_date or date.today().isoformat(),
        total_classes,
        holiday_dates=holiday_dates,
    )
    docs = []
    for i in range(1, total_classes + 1):
        sched_date = working_days[i - 1] if i - 1 < len(working_days) else None
        docs.append({
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "class_number": i,
            "scheduled_date": sched_date,
            "completed_date": None,
            "trainer_id": trainer_id,
            "status": "pending",
            "notes": None,
            "updated_at": _now_iso(),
        })
    if docs:
        await db.classes.insert_many(docs)


@api.get("/students")
async def list_students(
    limit: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    trainer_id: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    include_classes: Optional[bool] = Query(True),
    user: dict = Depends(get_current_user),
):
    coll = db.students
    q = {}
    if status:
        if status == "old":
            coll = db.archived_students
        else:
            q["status"] = status
    if trainer_id:
        q["assigned_trainer_id"] = trainer_id

    # Strict location isolation: Trainers can only see students in their own location
    if user.get("role") == "trainer":
        trainer_loc = user.get("location")
        if trainer_loc:
            q["$or"] = [
                {"location": trainer_loc},
                {"assigned_trainer_id": user["id"]},
            ]
        else:
            q["assigned_trainer_id"] = user["id"]
    elif location:
        q["location"] = location

    cursor = coll.find(q, {"_id": 0}).sort("joining_date", -1)
    if limit:
        cursor = cursor.limit(limit)

    students = await cursor.to_list(1000)
    if not students:
        return []

    is_admin = user.get("role") == "admin"

    # Batch-aggregate completed and absent classes for all students in 1 single query instead of N separate calls
    student_ids = [s["id"] for s in students if "id" in s]
    completed_counts = {}
    absent_counts = {}
    if include_classes:
        class_coll = db.archived_classes if status == "old" else db.classes
        pipeline = [
            {"$match": {"student_id": {"$in": student_ids}, "status": {"$in": ["completed", "absent", "missed"]}}},
            {"$group": {
                "_id": {"student_id": "$student_id", "status": "$status"},
                "count": {"$sum": 1}
            }},
        ]
        async for doc in class_coll.aggregate(pipeline):
            sid = doc["_id"]["student_id"]
            st = doc["_id"]["status"]
            if st == "completed":
                completed_counts[sid] = completed_counts.get(sid, 0) + doc["count"]
            else:
                absent_counts[sid] = absent_counts.get(sid, 0) + doc["count"]

    for s in students:
        completed = completed_counts.get(s.get("id"), 0)
        absent = absent_counts.get(s.get("id"), 0)
        total_c = s.get("total_classes", 10) or 10
        rem = max(0, total_c - completed)
        s["classes_completed"] = completed
        s["classes_absent"] = absent
        s["classes_remaining"] = rem
        # Last 3 working days condition: 1 to 3 classes remaining out of course
        s["is_ending_soon"] = (0 < rem <= 3 and s.get("status") == "active")

        # Payments strictly visible only to admin
        if not is_admin:
            s.pop("fees_total", None)
            s.pop("fees_paid", None)

    return students


@api.post("/students")
async def create_student(body: StudentCreate, user: dict = Depends(get_current_user)):
    sid = str(uuid.uuid4())
    is_trainer = user.get("role") == "trainer"
    loc = (user.get("location") or "Khajaguda") if is_trainer else (body.location or "Khajaguda")
    assigned_trainer = (user["id"] if is_trainer and not body.assigned_trainer_id else body.assigned_trainer_id)
    total_classes = body.total_classes or 10

    doc = {
        "id": sid,
        "name": body.name,
        "phone": body.phone,
        "email": body.email,
        "age": body.age,
        "gender": body.gender,
        "license_type": body.license_type,
        "joining_date": body.joining_date,
        "slot_time": body.slot_time,
        "location": loc,
        "needs_pickup": body.needs_pickup,
        "pickup_address": body.pickup_address,
        "drop_address": body.drop_address,
        "total_classes": total_classes,
        "assigned_trainer_id": assigned_trainer,
        "pickup_trainer_id": body.pickup_trainer_id,
        "drop_trainer_id": body.drop_trainer_id,
        "photo_url": body.photo_url,
        "fees_total": body.fees_total if user.get("role") in ("admin", "manager") else (body.fees_total or 0),
        "fees_paid": body.fees_paid if user.get("role") in ("admin", "manager") else (body.fees_paid or 0),
        "notes": body.notes,
        "status": "active",
        "created_at": _now_iso(),
    }
    await db.students.insert_one(doc)
    
    # Automatically record initial payment in transaction ledger (manager or admin)
    if doc["fees_paid"] > 0:
        payment_doc = {
            "id": str(uuid.uuid4()),
            "student_id": sid,
            "amount": doc["fees_paid"],
            "date": body.joining_date,
            "method": "cash",
            "notes": "Initial enrollment payment",
            "recorded_by": user["id"],
            "created_at": _now_iso(),
        }
        await db.payments.insert_one(payment_doc)
        logger.info("Automatically recorded initial payment of %d for student %s", doc["fees_paid"], sid)

    await _create_class_slots(sid, total_classes, assigned_trainer, body.joining_date, loc)
    
    # Trigger Hostinger email notification, Reach marketing sync, and n8n webhook in background
    try:
        # 1. Dispatch to Hostinger n8n instance (Invoice / Welcome Kit / WhatsApp)
        asyncio.create_task(asyncio.to_thread(dispatch_n8n_event, "student.enrolled", dict(doc)))

        if doc.get("email"):
            # 2. Send transactional enrollment confirmation via Hostinger SMTP
            asyncio.create_task(asyncio.to_thread(send_enrollment_email, dict(doc)))
            # 3. Sync student contact to Hostinger Reach (Email Marketing)
            asyncio.create_task(asyncio.to_thread(
                sync_contacts_to_reach,
                [{"name": doc.get("name"), "email": doc.get("email"), "phone": doc.get("phone")}],
                "Student"
            ))

        # 4. Sync student record to Google Sheets in parallel
        trainer_name = "Unassigned"
        if assigned_trainer:
            tr_user = await db.users.find_one({"id": assigned_trainer}, {"name": 1})
            if tr_user:
                trainer_name = tr_user.get("name", "Unassigned")
        asyncio.create_task(asyncio.to_thread(sync_student_to_google_sheet, dict(doc), trainer_name))
        # 5. Sync student record to Notion in parallel
        asyncio.create_task(asyncio.to_thread(sync_student_to_notion, dict(doc), trainer_name))
    except Exception as mail_err:
        logger.warning("Non-blocking background email/marketing/sheets/n8n error for student %s: %s", sid, mail_err)

    doc.pop("_id", None)
    if user.get("role") != "admin":
        doc.pop("fees_total", None)
        doc.pop("fees_paid", None)
    invalidate_stats()
    return doc


@api.get("/students/{student_id}")
async def get_student(student_id: str, user: dict = Depends(get_current_user)):
    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        s = await db.archived_students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    if user.get("role") == "trainer":
        trainer_loc = user.get("location")
        if trainer_loc and s.get("location") and s.get("location") != trainer_loc and s.get("assigned_trainer_id") != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied to student outside your location")
    return s


@api.get("/students/{student_id}/invoice")
async def get_student_invoice(student_id: str, user: dict = Depends(get_current_user)):
    """
    Returns official admission receipt & training agreement invoice for a student,
    including allotted trainer, allocated hourly slot, 10 working days training calendar,
    fees/payments breakdown, and mandatory training rules.
    """
    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        s = await db.archived_students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")

    # Access control
    if user.get("role") == "trainer":
        trainer_loc = user.get("location")
        if trainer_loc and s.get("location") and s.get("location") != trainer_loc and s.get("assigned_trainer_id") != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied to student outside your location")

    # Fetch allotted trainer, pickup trainer, drop trainer
    trainer_ids = [tid for tid in [s.get("assigned_trainer_id"), s.get("pickup_trainer_id"), s.get("drop_trainer_id")] if tid]
    trainers = await db.users.find({"id": {"$in": trainer_ids}}, {"_id": 0, "password_hash": 0}).to_list(10)
    trainer_map = {t["id"]: t for t in trainers}

    assigned_trainer = trainer_map.get(s.get("assigned_trainer_id"))
    pickup_trainer = trainer_map.get(s.get("pickup_trainer_id"))
    drop_trainer = trainer_map.get(s.get("drop_trainer_id"))

    # Fetch 10 working days class slots
    classes = await db.classes.find({"student_id": student_id}, {"_id": 0}).sort("class_number", 1).to_list(100)
    if not classes:
        classes = await db.archived_classes.find({"student_id": student_id}, {"_id": 0}).sort("class_number", 1).to_list(100)

    # Fetch payments ledger
    payments = await db.payments.find({"student_id": student_id}, {"_id": 0}).sort("date", 1).to_list(100)

    fees_total = float(s.get("fees_total", 0) or 0)
    fees_paid = float(s.get("fees_paid", 0) or 0)
    fees_balance = max(0.0, fees_total - fees_paid)
    is_fully_paid = fees_paid >= fees_total if fees_total > 0 else True

    # Deterministic invoice numbering e.g. RW-INV-XXXXXXXX
    inv_suffix = student_id[:8].upper()
    invoice_number = f"RW-INV-{inv_suffix}"

    branch_location = s.get("location") or "Khajaguda"
    branch_addresses = {
        "Khajaguda": "Plot 42, Gachibowli-Khajaguda Main Road, Near Bio-Diversity Park, Hyderabad - 500075",
        "Madhapur": "Near Metro Station, Hitech City Main Road, Madhapur, Hyderabad - 500081",
        "Attapur": "Main Road, Pillar No 143, Attapur, Hyderabad - 500048",
    }
    branch_address = branch_addresses.get(branch_location, "Main Road, Hyderabad, Telangana")

    instructions = [
        f"MANDATORY REPORTING TIME: You must report at the branch / pickup point precisely at your allotted time slot ({s.get('slot_time') or 'assigned hour'}). Training vehicles depart strictly on schedule; late arrivals will not receive extra time.",
        "10 WORKING DAYS COURSE: Training is strictly scheduled for 10 consecutive working days (skipping Sundays and officially declared school holidays/functions). Check your schedule card below for exact class dates.",
        "LEARNER LICENSE (LLR) MANDATORY: You must carry your valid Learner's License (physical copy or official mParivahan digital copy) during every single driving session. Driving without an LLR is strictly prohibited by law.",
        "SAFETY & ATTIRE: Wear comfortable, flat footwear (sneakers or closed shoes). High heels, loose sandals, or barefoot driving are strictly prohibited. Seatbelt / helmet must be fastened before turning on ignition.",
        "ABSENCE & RESCHEDULING NOTICE: If an unavoidable emergency arises, notify your allotted trainer or branch manager in advance. Unattended sessions are marked as 'Absent' in the official 10-day training ledger.",
        f"BALANCE FEES: Any outstanding course balance (₹{int(fees_balance):,}) must be cleared on or before the 6th training session.",
        f"ALLOTTED TRAINER CONTACT: Your primary driving instructor is {assigned_trainer.get('name') if assigned_trainer else 'Assigned Instructor'} ({assigned_trainer.get('phone') if assigned_trainer else 'Branch Reception'}). Call directly for day-of pickup or vehicle coordination.",
    ]

    # Format course name
    course_map = {
        "scooty": "Scooty Training",
        "gearless": "Scooty Training",
        "geared": "Motorcycle (Geared) Training",
        "2w": "Two Wheeler Training",
        "4w": "Car / 4-Wheeler Training",
        "lmv": "Car Driving Course",
        "combo": "Combo (2-Wheeler + 4-Wheeler)",
    }
    raw_course = str(s.get("license_type") or "scooty").lower()
    course_name = course_map.get(raw_course, f"{s.get('license_type', 'Driving').title()} Training")

    # Format clean date helper
    def _clean_date_fmt(d_str):
        if not d_str:
            return "—"
        try:
            from datetime import datetime
            return datetime.strptime(d_str[:10], "%Y-%m-%d").strftime("%d-%b-%Y")
        except Exception:
            return d_str

    start_date_clean = _clean_date_fmt(s.get("joining_date") or date.today().isoformat())
    end_date_clean = _clean_date_fmt(classes[-1].get("scheduled_date")) if classes and classes[-1].get("scheduled_date") else start_date_clean
    validity_str = f"{start_date_clean} to {end_date_clean}"

    latest_payment = payments[-1] if payments else None
    payment_mode = (latest_payment.get("method") or "Cash").capitalize() if latest_payment else "Cash"

    # Deterministic receipt number e.g. 300, 301 or stored receipt_no
    receipt_no = s.get("receipt_no")
    if not receipt_no:
        receipt_no = str(abs(hash(student_id)) % 900 + 100)

    # Look up manager for this branch
    manager_doc = await db.users.find_one({"role": "manager", "location": branch_location}, {"_id": 0, "password_hash": 0})
    if not manager_doc:
        manager_doc = await db.users.find_one({"role": "manager"}, {"_id": 0, "password_hash": 0})

    return {
        "invoice_number": invoice_number,
        "receipt_no": receipt_no,
        "date": date.today().isoformat(),
        "issue_date_formatted": _clean_date_fmt(date.today().isoformat()),
        "created_at": s.get("created_at") or _now_iso(),
        "course_name": course_name,
        "validity": validity_str,
        "working_days": "Monday–Saturday",
        "daily_duration": "1 hour",
        "sessions_count": len(classes) if classes else int(s.get("total_classes", 10) or 10),
        "payment_mode": payment_mode,
        "received_by": "LEARN & DRIVE2",
        "manager": {
            "name": manager_doc.get("name") if manager_doc else "Branch Manager",
            "phone": manager_doc.get("phone") if manager_doc else "+91 85018 52055",
            "email": manager_doc.get("email") if manager_doc else "manager@learnanddrive.com",
            "location": branch_location,
        },
        "school": {
            "name": "LEARN & DRIVE2",
            "tagline": "RIDE WITH CONFIDENCE",
            "motto": "LEARN • RIDE • DRIVE WITH CONFIDENCE",
            "branch": f"{branch_location} Branch",
            "address": branch_address,
            "phone": "+91 85018 52055",
            "email": "support@learnanddrive.com",
            "rto_registration": "TS-RTO-DRV-2024-8842",
        },
        "student": {
            "id": s["id"],
            "name": s["name"],
            "phone": s.get("phone"),
            "email": s.get("email"),
            "age": s.get("age"),
            "gender": s.get("gender"),
            "license_type": s.get("license_type", "gearless"),
            "location": branch_location,
            "joining_date": s.get("joining_date"),
            "slot_time": s.get("slot_time"),
            "needs_pickup": s.get("needs_pickup", False),
            "pickup_address": s.get("pickup_address"),
            "drop_address": s.get("drop_address"),
            "status": s.get("status", "active"),
        },
        "allotment": {
            "assigned_trainer": {
                "id": assigned_trainer.get("id") if assigned_trainer else None,
                "name": assigned_trainer.get("name") if assigned_trainer else "Unassigned",
                "phone": assigned_trainer.get("phone") if assigned_trainer else "—",
            } if assigned_trainer else None,
            "pickup_trainer": {
                "id": pickup_trainer.get("id") if pickup_trainer else None,
                "name": pickup_trainer.get("name") if pickup_trainer else "—",
                "phone": pickup_trainer.get("phone") if pickup_trainer else "—",
            } if pickup_trainer else None,
            "drop_trainer": {
                "id": drop_trainer.get("id") if drop_trainer else None,
                "name": drop_trainer.get("name") if drop_trainer else "—",
                "phone": drop_trainer.get("phone") if drop_trainer else "—",
            } if drop_trainer else None,
            "slot_hour": s.get("slot_time") or "To be allotted",
        },
        "schedule": [
            {
                "class_number": c["class_number"],
                "scheduled_date": c.get("scheduled_date"),
                "status": c.get("status", "pending"),
                "completed_date": c.get("completed_date"),
            }
            for c in classes
        ],
        "financials": {
            "fees_total": fees_total,
            "fees_paid": fees_paid,
            "fees_balance": fees_balance,
            "is_fully_paid": is_fully_paid,
            "status_label": "PAID IN FULL" if is_fully_paid else f"BALANCE DUE: ₹{int(fees_balance):,}",
            "payments_ledger": payments,
        },
        "instructions": instructions,
    }


@api.patch("/students/{student_id}")
async def update_student(student_id: str, body: StudentUpdate, user: dict = Depends(get_current_user)):
    target_coll = db.students
    existing = await target_coll.find_one({"id": student_id}, {"_id": 0})
    if not existing:
        target_coll = db.archived_students
        existing = await target_coll.find_one({"id": student_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Student not found")
    if user.get("role") == "trainer":
        trainer_loc = user.get("location")
        if trainer_loc and existing.get("location") and existing.get("location") != trainer_loc and existing.get("assigned_trainer_id") != user["id"]:
            raise HTTPException(status_code=403, detail="Cannot edit student outside your location")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if user.get("role") == "trainer":
        updates.pop("fees_total", None)
        updates.pop("fees_paid", None)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # If fees_paid increased, record the delta as a new payment
    new_fees_paid = updates.get("fees_paid")
    old_fees_paid = existing.get("fees_paid", 0) or 0
    if new_fees_paid is not None and new_fees_paid > old_fees_paid and user.get("role") in ("admin", "manager"):
        delta = new_fees_paid - old_fees_paid
        payment_doc = {
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "amount": delta,
            "date": date.today().isoformat(),
            "method": "cash",
            "notes": "Updated fees payment",
            "recorded_by": user["id"],
            "created_at": _now_iso(),
        }
        await db.payments.insert_one(payment_doc)
        logger.info("Recorded additional payment of %d for student %s", delta, student_id)

    # If assigned_trainer_id updated, sync pending classes
    new_trainer_id = updates.get("assigned_trainer_id")
    if new_trainer_id:
        await db.classes.update_many(
            {"student_id": student_id, "status": "pending"},
            {"$set": {"trainer_id": new_trainer_id, "updated_at": _now_iso()}}
        )

    await target_coll.update_one({"id": student_id}, {"$set": updates})
    invalidate_stats()
    return await target_coll.find_one({"id": student_id}, {"_id": 0})


@api.delete("/students/{student_id}")
async def delete_student(student_id: str, user: dict = Depends(require_manager_or_admin)):
    await db.students.delete_one({"id": student_id})
    await db.archived_students.delete_one({"id": student_id})
    await db.classes.delete_many({"student_id": student_id})
    await db.archived_classes.delete_many({"student_id": student_id})
    await db.payments.delete_many({"student_id": student_id})
    invalidate_stats()
    return {"ok": True}


# ---------- Classes ----------
@api.get("/classes/active")
async def list_active_classes(location: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Bulk fetch all classes for all active students in a single indexed query, scoped by location."""
    q = {"status": "active"}
    if user.get("role") == "trainer":
        if user.get("location"):
            q["location"] = user["location"]
    elif location:
        q["location"] = location

    active_students = await db.students.find(q, {"id": 1, "_id": 0}).to_list(1000)
    student_ids = [s["id"] for s in active_students if "id" in s]
    classes = await db.classes.find(
        {"student_id": {"$in": student_ids}},
        {"_id": 0}
    ).sort("class_number", 1).to_list(5000)
    
    grouped = {}
    for c in classes:
        grouped.setdefault(c["student_id"], []).append(c)
    return grouped


@api.get("/students/{student_id}/classes")
async def list_classes(student_id: str, user: dict = Depends(get_current_user)):
    classes = await db.classes.find({"student_id": student_id}, {"_id": 0}).sort("class_number", 1).to_list(100)
    if not classes:
        classes = await db.archived_classes.find({"student_id": student_id}, {"_id": 0}).sort("class_number", 1).to_list(100)
    return classes


@api.delete("/classes/{class_id}")
async def delete_class(class_id: str, user: dict = Depends(require_manager_or_admin)):
    await db.classes.delete_one({"id": class_id})
    await db.archived_classes.delete_one({"id": class_id})
    invalidate_stats()
    return {"ok": True}


@api.patch("/classes/{class_id}")
async def update_class(class_id: str, body: ClassUpdate, user: dict = Depends(get_current_user)):
    existing = await db.classes.find_one({"id": class_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Class not found")
    prev_status = existing.get("status")

    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Normalize missed -> absent
    if updates.get("status") == "missed":
        updates["status"] = "absent"

    # Absent is recorded on the day it was marked so it shows on that day's schedule
    if updates.get("status") == "absent" and "completed_date" not in updates:
        updates["completed_date"] = date.today().isoformat()
    # Back to pending means the class hasn't happened on any day yet
    if updates.get("status") == "pending" and "completed_date" not in updates:
        updates["completed_date"] = None

    updates["updated_at"] = _now_iso()
    await db.classes.update_one({"id": class_id}, {"$set": updates})
    updated_class = await db.classes.find_one({"id": class_id}, {"_id": 0})
    invalidate_stats()

    new_status = updates.get("status")
    student_id = existing["student_id"]

    # Check student course completion when all scheduled classes are conducted
    if updated_class:
        student = await db.students.find_one({"id": student_id})
        if student:
            total_classes = student.get("total_classes", 10) or 10
            pending = await db.classes.count_documents({"student_id": student_id, "status": "pending"})
            marked_count = await db.classes.count_documents({"student_id": student_id, "status": {"$in": ["completed", "absent", "missed"]}})
            if pending == 0 and marked_count >= total_classes:
                await db.students.update_one(
                    {"id": student_id, "status": "active"},
                    {"$set": {"status": "completed", "completed_at": _now_iso()}},
                )
                logger.info("Auto-completed student %s (all %d scheduled classes conducted)", student_id, total_classes)
            elif student.get("status") == "completed" and pending > 0:
                await db.students.update_one(
                    {"id": student_id},
                    {"$set": {"status": "active", "completed_at": None}},
                )

    return updated_class


# ---------- Trainer Attendance ----------
@api.get("/attendance")
async def list_attendance(
    date: Optional[str] = None,
    trainer_id: Optional[str] = None,
    location: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    q = {}
    if date:
        q["date"] = date
    if trainer_id:
        q["trainer_id"] = trainer_id

    # If location is provided and not trainer_id, scope to trainers of that location
    if location and not trainer_id and user.get("role") != "trainer":
        loc_re = {"$regex": f"^{location.strip()}$", "$options": "i"}
        trainers_in_loc = await db.users.find({"role": "trainer", "location": loc_re}, {"id": 1, "_id": 0}).to_list(500)
        t_ids = [t["id"] for t in trainers_in_loc if "id" in t]
        q["trainer_id"] = {"$in": t_ids}

    # If user is a trainer, strictly limit to their own attendance records
    if user.get("role") == "trainer":
        q["trainer_id"] = user["id"]

    records = await db.attendance.find(q, {"_id": 0}).sort("date", -1).to_list(1000)
    return records


@api.post("/attendance")
async def upsert_attendance(body: AttendanceCreate, user: dict = Depends(get_current_user)):
    # Strictly marked by manager or admin; trainers can NO LONGER mark attendance for themselves or others
    if user.get("role") not in ("admin", "manager"):
        raise HTTPException(
            status_code=403,
            detail="Trainer attendance must strictly be marked by manager or admin",
        )

    # Verify target trainer exists
    target_trainer = await db.users.find_one({"id": body.trainer_id, "role": "trainer"})
    if not target_trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    doc = {
        "trainer_id": body.trainer_id,
        "date": body.date,
        "status": body.status,
        "notes": body.notes,
        "marked_by": user["id"],
        "marked_by_name": user.get("name"),
        "marked_by_role": user.get("role"),
        "updated_at": _now_iso(),
    }
    await db.attendance.update_one(
        {"trainer_id": body.trainer_id, "date": body.date},
        {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4())}},
        upsert=True,
    )
    invalidate_stats()
    return await db.attendance.find_one(
        {"trainer_id": body.trainer_id, "date": body.date}, {"_id": 0}
    )


# ---------- Payments ----------
@api.get("/payments")
async def list_payments(student_id: Optional[str] = None, user: dict = Depends(require_admin)):
    """Admin only — payments strictly visible only to admin."""
    q = {}
    if student_id:
        q["student_id"] = student_id
    payments = await db.payments.find(q, {"_id": 0}).sort("date", -1).to_list(1000)
    return payments


@api.post("/payments")
async def create_payment(body: PaymentCreate, user: dict = Depends(require_admin)):
    """Admin only — record payments."""
    doc = {
        "id": str(uuid.uuid4()),
        "student_id": body.student_id,
        "amount": body.amount,
        "date": body.date,
        "method": body.method,
        "notes": body.notes,
        "recorded_by": user["id"],
        "created_at": _now_iso(),
    }
    await db.payments.insert_one(doc)
    # bump fees_paid on student
    await db.students.update_one(
        {"id": body.student_id},
        {"$inc": {"fees_paid": body.amount}},
    )
    
    # Trigger Hostinger payment receipt email & n8n invoice generation in background
    try:
        async def _notify_payment():
            student = await db.students.find_one({"id": body.student_id}, {"_id": 0})
            if student:
                # 1. Dispatch event to Hostinger n8n for PDF Invoice & WhatsApp
                n8n_invoice_data = {
                    "payment_id": doc["id"],
                    "invoice_number": f"INV-{doc['id'][:8].upper()}",
                    "amount": doc["amount"],
                    "date": doc["date"],
                    "method": doc["method"],
                    "student_id": student.get("id"),
                    "student_name": student.get("name"),
                    "student_phone": student.get("phone"),
                    "student_email": student.get("email"),
                    "fees_total": student.get("fees_total", 0),
                    "fees_paid": student.get("fees_paid", 0) + doc["amount"],
                    "balance_due": max(0, student.get("fees_total", 0) - (student.get("fees_paid", 0) + doc["amount"]))
                }
                dispatch_n8n_event("payment.recorded", n8n_invoice_data)

                # 2. Send Hostinger SMTP receipt email
                if student.get("email"):
                    send_payment_receipt_email(dict(doc), dict(student))
        asyncio.create_task(_notify_payment())
    except Exception as pay_mail_err:
        logger.warning("Non-blocking receipt email/n8n dispatch failed: %s", pay_mail_err)

    doc.pop("_id", None)
    invalidate_stats()
    return doc


@api.patch("/payments/{payment_id}")
async def update_payment(payment_id: str, body: PaymentUpdate, user: dict = Depends(require_admin)):
    """Admin only — edit an existing payment. Recalculates student fees_paid when amount changes."""
    existing = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Payment not found")

    updates = {}
    if body.amount is not None:
        updates["amount"] = body.amount
    if body.date is not None:
        updates["date"] = body.date
    if body.method is not None:
        updates["method"] = body.method
    if body.notes is not None:
        updates["notes"] = body.notes

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = _now_iso()
    updates["updated_by"] = user["id"]
    await db.payments.update_one({"id": payment_id}, {"$set": updates})

    # If amount changed, recalculate fees_paid on the student
    if body.amount is not None:
        old_amount = existing.get("amount", 0)
        diff = body.amount - old_amount
        if diff != 0:
            await db.students.update_one(
                {"id": existing["student_id"]},
                {"$inc": {"fees_paid": diff}},
            )

    invalidate_stats()
    return await db.payments.find_one({"id": payment_id}, {"_id": 0})


@api.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str, user: dict = Depends(require_admin)):
    """Admin only — delete a payment and subtract amount from student fees_paid."""
    existing = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Payment not found")

    await db.payments.delete_one({"id": payment_id})

    # Subtract the deleted payment from student's fees_paid
    amount = existing.get("amount", 0)
    if amount > 0:
        await db.students.update_one(
            {"id": existing["student_id"]},
            {"$inc": {"fees_paid": -amount}},
        )

    invalidate_stats()
    return {"ok": True, "deleted_id": payment_id}




# ---------- Slots ----------
@api.get("/slots")
async def list_slots(user: dict = Depends(get_current_user)):
    now = time.time()
    if _slots_cache["data"] is not None and (now - _slots_cache["timestamp"] < 120):
        return _slots_cache["data"]
    slots = await db.slots.find({}, {"_id": 0}).sort("start_time", 1).to_list(100)
    _slots_cache["data"] = slots
    _slots_cache["timestamp"] = now
    return slots


@api.post("/slots")
async def create_slot(body: SlotCreate, user: dict = Depends(require_manager_or_admin)):
    if await db.slots.find_one({"label": body.label}):
        raise HTTPException(status_code=400, detail="Slot label already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "label": body.label,
        "start_time": body.start_time,
        "end_time": body.end_time,
        "created_at": _now_iso(),
    }
    await db.slots.insert_one(doc)
    doc.pop("_id", None)
    invalidate_slots()
    return doc


@api.delete("/slots/{slot_id}")
async def delete_slot(slot_id: str, user: dict = Depends(require_manager_or_admin)):
    res = await db.slots.delete_one({"id": slot_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Slot not found")
    invalidate_slots()
    return {"ok": True}


# ---------- Schedule (Today's Ops View) ----------
@api.get("/schedule/today")
async def schedule_today(
    date: Optional[str] = None,
    location: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    day = date or datetime.now(timezone.utc).date().isoformat()

    # Determine target location filter
    target_location = None
    if user.get("role") == "trainer":
        target_location = user.get("location")
    elif location:
        target_location = location

    student_q = {"status": "active"}
    trainer_q = {"role": "trainer"}
    if target_location:
        loc_re = {"$regex": f"^{re.escape(target_location)}$", "$options": "i"}
        loc_trainers = await db.users.find({"role": "trainer", "location": loc_re}, {"id": 1}).to_list(100)
        loc_trainer_ids = [t["id"] for t in loc_trainers if "id" in t]
        student_q["$or"] = [
            {"location": loc_re},
            {"assigned_trainer_id": {"$in": loc_trainer_ids}},
        ]
        trainer_q["location"] = loc_re

    slots = await db.slots.find({}, {"_id": 0}).sort("start_time", 1).to_list(100)
    students = await db.students.find(
        student_q,
        {
            "_id": 0,
            "id": 1,
            "name": 1,
            "phone": 1,
            "location": 1,
            "slot_time": 1,
            "total_classes": 1,
            "assigned_trainer_id": 1,
            "pickup_trainer_id": 1,
            "drop_trainer_id": 1,
            "needs_pickup": 1,
            "pickup_address": 1,
        },
    ).to_list(1000)
    trainers = await db.users.find(
        trainer_q, {"_id": 0, "id": 1, "name": 1, "phone": 1, "location": 1, "shift": 1}
    ).to_list(500)

    # group students by slot
    by_slot = {}
    unassigned = []

    student_ids = [s["id"] for s in students if "id" in s]

    # Bulk query 1: Today's scheduled or completed classes for all active students
    today_classes_task = db.classes.find(
        {"student_id": {"$in": student_ids}, "$or": [{"completed_date": day}, {"scheduled_date": day}]},
        {"_id": 0, "id": 1, "student_id": 1, "class_number": 1, "status": 1, "scheduled_date": 1, "completed_date": 1, "trainer_id": 1, "notes": 1},
    ).to_list(1000)

    # Bulk query 2: Pending classes to determine the next class for all active students
    pending_classes_task = db.classes.find(
        {"student_id": {"$in": student_ids}, "status": "pending"},
        {"_id": 0, "id": 1, "student_id": 1, "class_number": 1, "status": 1, "scheduled_date": 1},
    ).sort("class_number", 1).to_list(1000)

    # Bulk query 3: Completed & Absent classes counts for active students
    status_counts_task = db.classes.aggregate([
        {"$match": {"student_id": {"$in": student_ids}, "status": {"$in": ["completed", "absent", "missed"]}}},
        {"$group": {
            "_id": {"student_id": "$student_id", "status": "$status"},
            "count": {"$sum": 1}
        }},
    ]).to_list(1000)

    today_classes_list, pending_classes_list, status_agg = await asyncio.gather(
        today_classes_task, pending_classes_task, status_counts_task
    )

    completed_map = {}
    absent_map = {}
    for doc in status_agg:
        sid = doc["_id"]["student_id"]
        st = doc["_id"]["status"]
        if st == "completed":
            completed_map[sid] = completed_map.get(sid, 0) + doc["count"]
        else:
            absent_map[sid] = absent_map.get(sid, 0) + doc["count"]

    today_map = {c["student_id"]: c for c in today_classes_list}
    next_map = {}
    for c in pending_classes_list:
        sid = c["student_id"]
        if sid not in next_map:
            next_map[sid] = c

    for s in students:
        sid = s["id"]
        next_class = next_map.get(sid)
        today_class = today_map.get(sid)
        completed = completed_map.get(sid, 0)
        absent = absent_map.get(sid, 0)
        total_c = s.get("total_classes", 10) or 10
        rem = max(0, total_c - completed)
        student_row = {
            "id": sid,
            "name": s["name"],
            "phone": s["phone"],
            "location": s.get("location"),
            "slot_time": s.get("slot_time"),
            "needs_pickup": s.get("needs_pickup", False),
            "pickup_address": s.get("pickup_address"),
            "drop_address": s.get("drop_address"),
            "assigned_trainer_id": s.get("assigned_trainer_id"),
            "pickup_trainer_id": s.get("pickup_trainer_id"),
            "drop_trainer_id": s.get("drop_trainer_id"),
            "classes_completed": completed,
            "classes_absent": absent,
            "total_classes": total_c,
            "classes_remaining": rem,
            "is_ending_soon": (0 < rem <= 3),
            "next_class": next_class,
            "today_class": today_class,
        }
        slot = s.get("slot_time")
        if slot:
            by_slot.setdefault(slot, []).append(student_row)
        else:
            unassigned.append(student_row)

    # Check if target day is Sunday or has a declared holiday/function
    try:
        is_sunday = (datetime.strptime(day, "%Y-%m-%d").date().weekday() == 6)
    except Exception:
        is_sunday = False

    holiday_q = {"date": day}
    if target_location:
        holiday_q["$or"] = [{"location": None}, {"location": ""}, {"location": target_location}]
    today_holiday = await db.holidays.find_one(holiday_q, {"_id": 0})

    return {
        "date": day,
        "is_sunday": is_sunday,
        "holiday": today_holiday,
        "location": target_location,
        "slots": slots,
        "by_slot": by_slot,
        "unassigned": unassigned,
        "trainers": trainers,
    }


async def _reschedule_pending_classes_for_holiday(holiday_date: str, location: Optional[str] = None):
    """
    If a holiday/function is created on a working day, shift pending classes
    that were scheduled on or after that holiday date so that they skip the new holiday.
    """
    try:
        sq = {"status": "active"}
        if location:
            sq["location"] = location
        students = await db.students.find(sq, {"id": 1, "location": 1}).to_list(2000)
        if not students:
            return

        all_hols = await db.holidays.find({}, {"date": 1, "location": 1, "_id": 0}).to_list(1000)

        for st in students:
            sid = st["id"]
            st_loc = st.get("location")
            st_holidays = {
                h["date"] for h in all_hols
                if not h.get("location") or h.get("location") == st_loc
            }

            pending_classes = await db.classes.find(
                {"student_id": sid, "status": "pending", "scheduled_date": {"$gte": holiday_date}},
                {"id": 1, "class_number": 1, "scheduled_date": 1}
            ).sort("class_number", 1).to_list(100)

            if not pending_classes:
                continue

            has_conflict = any(c.get("scheduled_date") == holiday_date for c in pending_classes)
            if not has_conflict:
                continue

            first_date = pending_classes[0].get("scheduled_date") or holiday_date
            num_classes = len(pending_classes)
            new_dates = compute_working_days(first_date, num_classes, holiday_dates=st_holidays)

            for idx, pc in enumerate(pending_classes):
                if idx < len(new_dates) and pc.get("scheduled_date") != new_dates[idx]:
                    await db.classes.update_one(
                        {"id": pc["id"]},
                        {"$set": {"scheduled_date": new_dates[idx], "updated_at": _now_iso()}}
                    )
    except Exception as e:
        logger.warning("Error rescheduling pending classes for holiday: %s", e)


# ---------- Holidays & Functions Calendar ----------
@api.get("/holidays")
async def list_holidays(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    location: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    q = {}
    if user.get("role") == "trainer":
        trainer_loc = user.get("location")
        if trainer_loc:
            q["$or"] = [{"location": None}, {"location": ""}, {"location": trainer_loc}]
    elif location:
        q["$or"] = [{"location": None}, {"location": ""}, {"location": location}]

    if year and month:
        prefix = f"{year:04d}-{month:02d}"
        q["date"] = {"$regex": f"^{prefix}"}
    elif year:
        q["date"] = {"$regex": f"^{year:04d}"}

    holidays = await db.holidays.find(q, {"_id": 0}).sort("date", 1).to_list(1000)
    return holidays


@api.post("/holidays")
async def create_holiday(
    body: HolidayCreate,
    user: dict = Depends(require_manager_or_admin),
):
    try:
        datetime.strptime(body.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    # Manager can only declare holidays for their branch
    existing = await db.holidays.find_one({"date": body.date, "location": body.location})
    if existing:
        raise HTTPException(status_code=400, detail="Holiday or function already declared for this date and location")

    doc = {
        "id": str(uuid.uuid4()),
        "date": body.date,
        "title": body.title.strip(),
        "type": body.type,
        "location": body.location,
        "notes": body.notes.strip() if body.notes else None,
        "created_by": user["id"],
        "created_at": _now_iso(),
    }
    await db.holidays.insert_one(doc)
    doc.pop("_id", None)

    # Shift any pending student classes that clash with this new holiday
    asyncio.create_task(_reschedule_pending_classes_for_holiday(body.date, body.location))

    return doc


@api.delete("/holidays/{holiday_id}")
async def delete_holiday(
    holiday_id: str,
    user: dict = Depends(require_manager_or_admin),
):
    existing = await db.holidays.find_one({"id": holiday_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Holiday not found")
    await db.holidays.delete_one({"id": holiday_id})
    return {"ok": True}


# ---------- Locations ----------
@api.get("/locations")
async def list_locations(user: dict = Depends(get_current_user)):
    """List all available locations."""
    defaults = ["Attapur", "Khajaguda", "Madhapur"]
    user_locs = await db.users.distinct("location")
    student_locs = await db.students.distinct("location")
    all_locs = sorted(list({loc for loc in (defaults + user_locs + student_locs) if loc and isinstance(loc, str)}))
    return all_locs


# ---------- Dashboard / Reports ----------
@api.get("/dashboard/stats")
async def dashboard_stats(location: Optional[str] = None, user: dict = Depends(get_current_user)):
    # Determine target location filter
    target_location = None
    if user.get("role") == "trainer":
        target_location = user.get("location")
    elif location:
        target_location = location

    cache_key = f"{target_location}_{user.get('role')}"
    now = time.time()
    cached = _stats_cache.get(cache_key)
    if cached and (now - cached["timestamp"] < 30):
        return cached["data"]

    today = date.today().isoformat()
    
    student_q = {}
    active_student_q = {"status": "active"}
    trainer_q = {"role": "trainer"}
    if target_location:
        student_q["location"] = target_location
        active_student_q["location"] = target_location
        trainer_q["location"] = target_location

    # Run all count and aggregation queries concurrently in parallel
    total_students_task = db.students.count_documents(student_q)
    active_students_task = db.students.count_documents(active_student_q)
    total_trainers_task = db.users.count_documents(trainer_q)
    classes_today_q = {"completed_date": today, "status": "completed"}
    if target_location:
        loc_students = await db.students.find(student_q, {"id": 1, "_id": 0}).to_list(5000)
        classes_today_q["student_id"] = {"$in": [s["id"] for s in loc_students if "id" in s]}
    classes_today_task = db.classes.count_documents(classes_today_q)

    # Filter trainer attendance if location is selected
    if target_location:
        loc_trainers = await db.users.find(trainer_q, {"id": 1, "_id": 0}).to_list(500)
        loc_trainer_ids = [t["id"] for t in loc_trainers if "id" in t]
        present_today_task = db.attendance.count_documents({"date": today, "trainer_id": {"$in": loc_trainer_ids}, "status": "present"})
        absent_today_task = db.attendance.count_documents({"date": today, "trainer_id": {"$in": loc_trainer_ids}, "status": "absent"})
    else:
        present_today_task = db.attendance.count_documents({"date": today, "status": "present"})
        absent_today_task = db.attendance.count_documents({"date": today, "status": "absent"})

    fees_pipeline = []
    if target_location:
        fees_pipeline.append({"$match": {"location": target_location}})
    fees_pipeline.append({"$group": {"_id": None, "total": {"$sum": "$fees_total"}, "paid": {"$sum": "$fees_paid"}}})
    fees_agg_task = db.students.aggregate(fees_pipeline).to_list(1)

    (
        total_students,
        active_students,
        total_trainers,
        classes_today_completed,
        present_today,
        absent_today,
        fees_agg,
    ) = await asyncio.gather(
        total_students_task,
        active_students_task,
        total_trainers_task,
        classes_today_task,
        present_today_task,
        absent_today_task,
        fees_agg_task,
    )

    # Calculate active students ending soon (last 3 working days) so managers/admins can identify slots opening up
    active_students_list = await db.students.find(
        active_student_q,
        {"_id": 0, "id": 1, "name": 1, "phone": 1, "slot_time": 1, "location": 1, "total_classes": 1, "assigned_trainer_id": 1}
    ).to_list(1000)
    act_student_ids = [s["id"] for s in active_students_list if "id" in s]
    completed_counts = {}
    if act_student_ids:
        comp_agg = await db.classes.aggregate([
            {"$match": {"student_id": {"$in": act_student_ids}, "status": "completed"}},
            {"$group": {"_id": "$student_id", "completed_count": {"$sum": 1}}},
        ]).to_list(1000)
        completed_counts = {doc["_id"]: doc["completed_count"] for doc in comp_agg}

    ending_soon_students = []
    for s in active_students_list:
        completed = completed_counts.get(s["id"], 0)
        total_c = s.get("total_classes", 10) or 10
        rem = max(0, total_c - completed)
        if 0 < rem <= 3:
            ending_soon_students.append({
                "id": s["id"],
                "name": s["name"],
                "phone": s["phone"],
                "slot_time": s.get("slot_time") or "Flexible",
                "location": s.get("location") or "Khajaguda",
                "classes_completed": completed,
                "total_classes": total_c,
                "classes_remaining": rem,
                "assigned_trainer_id": s.get("assigned_trainer_id"),
            })
    ending_soon_students.sort(key=lambda x: x["classes_remaining"])

    is_admin = user.get("role") == "admin"
    fees_total = (fees_agg[0]["total"] if fees_agg else 0) if is_admin else 0
    fees_paid = (fees_agg[0]["paid"] if fees_agg else 0) if is_admin else 0

    res = {
        "location": target_location,
        "total_students": total_students,
        "active_students": active_students,
        "total_trainers": total_trainers,
        "classes_today": classes_today_completed,
        "present_today": present_today,
        "absent_today": absent_today,
        "fees_total": fees_total,
        "fees_paid": fees_paid,
        "fees_pending": max(0, fees_total - fees_paid) if is_admin else 0,
        "ending_soon_count": len(ending_soon_students),
        "ending_soon_students": ending_soon_students,
    }
    _stats_cache[cache_key] = {"data": res, "timestamp": now}
    return res


@api.get("/reports/summary")
async def reports_summary(
    period: Literal["daily", "weekly", "monthly", "custom"] = "weekly",
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    user: dict = Depends(require_manager_or_admin),
):
    """
    Weekly, monthly, daily, and custom reports for Managers and Admins.
    Filterable by branch location. Admins and Managers see the same report, including financials.
    """
    # Reports are identical for admins and managers, including financials
    show_financials = user.get("role") in ("admin", "manager")
    today_dt = date.today()

    # Determine date range
    if period == "daily":
        s_date = start_date or today_dt.isoformat()
        e_date = end_date or s_date
    elif period == "weekly":
        # Current week (Monday to Sunday)
        if start_date and end_date:
            s_date = start_date
            e_date = end_date
        else:
            monday = today_dt - timedelta(days=today_dt.weekday())
            sunday = monday + timedelta(days=6)
            s_date = start_date or monday.isoformat()
            e_date = end_date or sunday.isoformat()
    elif period == "monthly":
        if start_date and end_date:
            s_date = start_date
            e_date = end_date
        else:
            first_day = today_dt.replace(day=1)
            if today_dt.month == 12:
                last_day = date(today_dt.year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = date(today_dt.year, today_dt.month + 1, 1) - timedelta(days=1)
            s_date = start_date or first_day.isoformat()
            e_date = end_date or last_day.isoformat()
    else:  # custom
        s_date = start_date or today_dt.isoformat()
        e_date = end_date or s_date

    # Determine target location filter
    target_location = None
    if location and location.strip():
        target_location = location.strip()

    # 1. Fetch Students & Trainers (branch filtered + all students for name resolution)
    sq = {}
    tq = {"role": "trainer"}
    if target_location:
        loc_re = {"$regex": f"^{target_location}$", "$options": "i"}
        loc_trainers = await db.users.find({"role": "trainer", "location": loc_re}, {"id": 1, "_id": 0}).to_list(500)
        loc_t_ids = [t["id"] for t in loc_trainers if "id" in t]
        sq["$or"] = [
            {"location": loc_re},
            {"assigned_trainer_id": {"$in": loc_t_ids}},
        ]
        tq["location"] = loc_re

    students_task = db.students.find(sq, {"_id": 0}).to_list(2000)
    all_students_task = db.students.find({}, {"_id": 0, "id": 1, "name": 1, "location": 1, "slot_time": 1}).to_list(3000)
    trainers_task = db.users.find(tq, {"_id": 0, "password_hash": 0}).to_list(500)
    all_trainers_task = db.users.find({"role": "trainer"}, {"_id": 0, "id": 1, "name": 1, "location": 1}).to_list(500)

    students, all_students, trainers, all_trainers = await asyncio.gather(
        students_task, all_students_task, trainers_task, all_trainers_task
    )

    student_map = {s["id"]: s for s in students}
    student_ids = set(student_map.keys())
    all_student_map = {s["id"]: s for s in all_students}
    all_trainer_map = {t["id"]: t for t in all_trainers}
    trainer_map = {t["id"]: t for t in trainers}
    trainer_ids = set(trainer_map.keys())

    new_students = [
        s for s in students
        if (s.get("joining_date") and s_date <= s["joining_date"] <= e_date)
        or (s.get("created_at") and s_date <= s["created_at"][:10] <= e_date)
    ]
    active_count = sum(1 for s in students if s.get("status") == "active")
    completed_count = sum(1 for s in students if s.get("status") == "completed")
    dropped_count = sum(1 for s in students if s.get("status") == "dropped")

    # 3. Fetch Classes & Attendance concurrently
    cq = {
        "completed_date": {"$gte": s_date, "$lte": e_date},
        "status": "completed",
    }
    if target_location:
        cq["student_id"] = {"$in": list(student_ids)}
    completed_classes_task = db.classes.find(cq, {"_id": 0}).sort("completed_date", -1).to_list(2000)

    # Absences are dated by the day they were marked; older records without that date fall back to scheduled_date
    mq = {
        "status": {"$in": ["absent", "missed"]},
        "$or": [
            {"completed_date": {"$gte": s_date, "$lte": e_date}},
            {"completed_date": None, "scheduled_date": {"$gte": s_date, "$lte": e_date}},
        ],
    }
    if target_location:
        mq["student_id"] = {"$in": list(student_ids)}
    missed_classes_task = db.classes.find(mq, {"_id": 0}).to_list(1000)

    aq = {"date": {"$gte": s_date, "$lte": e_date}}
    if target_location:
        aq["trainer_id"] = {"$in": list(trainer_ids)}
    attendance_records_task = db.attendance.find(aq, {"_id": 0}).to_list(2000)

    # 5. Financial Metrics
    pq_task = None
    if show_financials:
        pq = {"date": {"$gte": s_date, "$lte": e_date}}
        if target_location:
            pq["student_id"] = {"$in": list(student_ids)}
        pq_task = db.payments.find(pq, {"_id": 0}).sort("date", -1).to_list(2000)

    completed_classes, missed_classes, attendance_records = await asyncio.gather(
        completed_classes_task, missed_classes_task, attendance_records_task
    )

    total_fees_collected = 0
    payment_methods_summary = {}
    recent_payments = []
    if show_financials and pq_task:
        payments = await pq_task
        total_fees_collected = sum(p.get("amount", 0) for p in payments)
        for p in payments:
            m = p.get("method", "cash")
            payment_methods_summary[m] = payment_methods_summary.get(m, 0) + p.get("amount", 0)
        recent_payments = payments[:100]

    trainer_stats = []
    for t in trainers:
        tid = t["id"]
        t_classes = [c for c in completed_classes if c.get("trainer_id") == tid]
        t_att = [a for a in attendance_records if a.get("trainer_id") == tid]
        present = sum(1 for a in t_att if a.get("status") == "present")
        absent = sum(1 for a in t_att if a.get("status") == "absent")
        leave = sum(1 for a in t_att if a.get("status") == "leave")
        total_marked = present + absent + leave
        att_rate = round((present / total_marked * 100), 1) if total_marked > 0 else 0
        active_assigned = sum(1 for s in students if s.get("assigned_trainer_id") == tid)
        month_enrolled = sum(1 for s in new_students if s.get("assigned_trainer_id") == tid)
        trainer_stats.append({
            "id": tid,
            "name": t.get("name"),
            "phone": t.get("phone"),
            "location": t.get("location"),
            "students_assigned": active_assigned,
            "new_students_month": month_enrolled,
            "classes_conducted": len(t_classes),
            "present_days": present,
            "absent_days": absent,
            "leave_days": leave,
            "attendance_rate": att_rate,
        })
    trainer_stats.sort(key=lambda x: (x["new_students_month"], x["students_assigned"], x["classes_conducted"]), reverse=True)

    # 6. Daily progression
    daily_breakdown = {}
    try:
        curr_dt = datetime.strptime(s_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(e_date, "%Y-%m-%d").date()
        # limit progression items to max 60 days
        diff = (end_dt - curr_dt).days
        if 0 <= diff <= 62:
            while curr_dt <= end_dt:
                iso = curr_dt.isoformat()
                daily_breakdown[iso] = {
                    "date": iso,
                    "day_name": curr_dt.strftime("%a"),
                    "classes_count": 0,
                    "present_trainers": 0,
                }
                curr_dt += timedelta(days=1)

            for c in completed_classes:
                cd = c.get("completed_date")
                if cd in daily_breakdown:
                    daily_breakdown[cd]["classes_count"] += 1

            for a in attendance_records:
                ad = a.get("date")
                if ad in daily_breakdown and a.get("status") == "present":
                    daily_breakdown[ad]["present_trainers"] += 1
    except Exception as e:
        logger.warning("Error building daily breakdown: %s", e)

    return {
        "period": period,
        "start_date": s_date,
        "end_date": e_date,
        "location": target_location,
        "summary": {
            "classes_conducted": len(completed_classes),
            "classes_absent": len(missed_classes),
            "classes_missed": len(missed_classes),
            "new_enrollments": len(new_students),
            "active_students": active_count,
            "completed_students": completed_count,
            "dropped_students": dropped_count,
            "active_trainers": len(trainers),
            "total_fees_collected": total_fees_collected if show_financials else None,
        },
        "payment_methods": payment_methods_summary if show_financials else {},
        "trainer_performance": trainer_stats,
        "daily_progression": list(daily_breakdown.values()),
        "new_students": [
            {
                "id": s["id"],
                "name": s["name"],
                "phone": s.get("phone"),
                "location": s.get("location"),
                "joining_date": s.get("joining_date"),
                "assigned_trainer_name": all_trainer_map.get(s.get("assigned_trainer_id"), {}).get("name") or trainer_map.get(s.get("assigned_trainer_id"), {}).get("name", "—"),
                "slot_time": s.get("slot_time"),
            }
            for s in new_students
        ],
        "recent_classes": [
            {
                "id": c["id"],
                "class_number": c.get("class_number"),
                "completed_date": c.get("completed_date"),
                "student_id": c.get("student_id"),
                "student_name": all_student_map.get(c.get("student_id"), {}).get("name") or student_map.get(c.get("student_id"), {}).get("name", "—"),
                "trainer_id": c.get("trainer_id"),
                "trainer_name": all_trainer_map.get(c.get("trainer_id"), {}).get("name") or trainer_map.get(c.get("trainer_id"), {}).get("name", "—"),
                "slot_time": all_student_map.get(c.get("student_id"), {}).get("slot_time") or student_map.get(c.get("student_id"), {}).get("slot_time"),
                "location": all_student_map.get(c.get("student_id"), {}).get("location") or student_map.get(c.get("student_id"), {}).get("location") or target_location,
            }
            for c in completed_classes[:100]
        ],
        "payments": recent_payments if show_financials else [],
    }


@api.get("/reports/daily")
async def daily_report(
    date: Optional[str] = None,
    location: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    day = date or datetime.now(timezone.utc).date().isoformat()
    target_loc = None
    if user.get("role") == "trainer":
        target_loc = user.get("location")
    elif location:
        target_loc = location

    cq = {"completed_date": day}
    aq = {"date": day}
    pq = {"date": day}

    if target_loc:
        students = await db.students.find({"location": target_loc}, {"id": 1}).to_list(1000)
        sids = [s["id"] for s in students]
        trainers = await db.users.find({"role": "trainer", "location": target_loc}, {"id": 1}).to_list(500)
        tids = [t["id"] for t in trainers]
        cq["$or"] = [{"student_id": {"$in": sids}}, {"trainer_id": {"$in": tids}}]
        aq["trainer_id"] = {"$in": tids}
        pq["student_id"] = {"$in": sids}

    classes = await db.classes.find(cq, {"_id": 0}).to_list(500)
    attendance = await db.attendance.find(aq, {"_id": 0}).to_list(500)
    
    # Financial data is strictly admin only
    payments = []
    if user.get("role") == "admin":
        payments = await db.payments.find(pq, {"_id": 0}).to_list(500)

    return {"date": day, "location": target_loc, "classes": classes, "attendance": attendance, "payments": payments}


@api.get("/reports/export-archive-excel")
async def export_archive_excel(user: dict = Depends(get_current_user)):
    """Downloads the complete historical archive Excel file containing 245+ completed students,
    2,687+ completed classes, and payment logs.
    """
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Admin or Manager role required")
    archive_path = ROOT_DIR / "LearnAndDrive_Historical_Archive.xlsx"
    if not archive_path.exists():
        desktop_path = Path("/Users/harsha/Desktop/LearnAndDrive_Historical_Archive_2026-10-25.xlsx")
        if desktop_path.exists():
            archive_path = desktop_path
        else:
            raise HTTPException(status_code=404, detail="Archive excel file not found")
    return FileResponse(
        path=str(archive_path),
        filename="LearnAndDrive_Historical_Archive_2026-10-25.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------- Notion Database Integration API Endpoints ----------

class NotionConfigRequest(BaseModel):
    api_key: str
    database_id: str

@api.get("/notion/status")
async def get_notion_status(user: dict = Depends(get_current_user)):
    """Returns Notion connection status and masked credentials."""
    cfg = get_notion_config()
    api_key = cfg.get("api_key") or ""
    db_id = cfg.get("database_id") or ""
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else ("Configured" if api_key else "")
    return {
        "configured": bool(api_key and db_id),
        "api_key_masked": masked_key,
        "database_id": db_id,
    }

@api.post("/notion/config")
async def save_notion_config(req: NotionConfigRequest, user: dict = Depends(get_current_user)):
    """Saves Notion Integration API Key & Database ID into MongoDB settings."""
    if user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    clean_db = clean_database_id(req.database_id)
    await db.settings.update_one(
        {"key": "notion_sync"},
        {
            "$set": {
                "key": "notion_sync",
                "api_key": req.api_key.strip(),
                "database_id": clean_db,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True
    )
    return {"ok": True, "message": "Notion settings saved successfully", "database_id": clean_db}

@api.post("/notion/sync-all")
async def sync_all_to_notion(include_old: bool = False, user: dict = Depends(get_current_user)):
    """Pushes all students to Notion database."""
    if user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    result = await asyncio.to_thread(sync_all_students_to_notion, include_old)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Notion sync failed"))
    return result




# ---------- Hostinger Email & Marketing API Endpoints ----------

class SendTestEmailRequest(BaseModel):
    to_email: EmailStr
    subject: Optional[str] = "Test Email from Hostinger - RideWell"
    message: Optional[str] = "This is a test email verifying that your Hostinger SMTP email integration is active and working."

@api.get("/email/config")
async def get_email_status(user: dict = Depends(get_current_user)):
    """Return Hostinger SMTP and Reach integration status (Admin/Manager)."""
    smtp_status = get_email_config_status()
    reach_status = get_reach_summary()
    return {
        "smtp": smtp_status,
        "reach": reach_status
    }

@api.post("/email/test")
async def send_test_email_endpoint(body: SendTestEmailRequest, user: dict = Depends(require_manager_or_admin)):
    """Send a diagnostic test email via Hostinger SMTP (Manager or Admin)."""
    html_content = f"""
    <div style="font-family: sans-serif; padding: 24px; border: 1px solid #e4e4e7; border-radius: 8px; max-width: 500px;">
      <h2 style="color: #16a34a; margin-top: 0;">Hostinger SMTP Connected!</h2>
      <p>Congratulations, your Hostinger email server is successfully configured and sending transactional emails for <strong>Adarsh Motor Driving School</strong>.</p>
      <div style="background: #f4f4f5; padding: 12px; border-radius: 6px; font-size: 13px; margin: 16px 0;">
        <strong>Details:</strong><br>
        • Host: smtp.hostinger.com<br>
        • Recipient: {body.to_email}<br>
        • Dispatched by: {user.get('name', 'Admin')} ({user.get('email', '')})
      </div>
      <p style="font-size: 12px; color: #71717a;">Message: {body.message}</p>
    </div>
    """
    res = await asyncio.to_thread(
        send_smtp_email,
        body.to_email,
        body.subject,
        html_content,
        body.message
    )
    if not res.get("success") and not res.get("simulated"):
        raise HTTPException(status_code=500, detail=res.get("error", "Failed to deliver email via Hostinger SMTP"))
    return res

@api.get("/marketing/reach/status")
async def get_marketing_status(user: dict = Depends(get_current_user)):
    """Return Hostinger Reach Email Marketing status, quotas and tags."""
    return get_reach_summary()

@api.post("/marketing/reach/sync-all")
async def sync_all_contacts_to_reach(user: dict = Depends(require_manager_or_admin)):
    """
    Sync all students and users with valid email addresses to Hostinger Reach
    Email Marketing audience with appropriate tags (Manager or Admin).
    """
    # 1. Fetch all students with email
    students_cursor = db.students.find(
        {"email": {"$regex": r"@"}},
        {"_id": 0, "name": 1, "email": 1, "phone": 1, "status": 1}
    )
    students = await students_cursor.to_list(1000)

    # 2. Fetch all system users/staff with email
    users_cursor = db.users.find(
        {"email": {"$regex": r"@"}},
        {"_id": 0, "name": 1, "email": 1, "phone": 1}
    )
    users_list = await users_cursor.to_list(1000)

    # Dispatch sync in background thread
    student_contacts = [{"name": s.get("name"), "email": s.get("email"), "phone": s.get("phone")} for s in students if s.get("email")]
    staff_contacts = [{"name": u.get("name"), "email": u.get("email"), "phone": u.get("phone")} for u in users_list if u.get("email")]

    student_res = await asyncio.to_thread(sync_contacts_to_reach, student_contacts, "Student")
    staff_res = await asyncio.to_thread(sync_contacts_to_reach, staff_contacts, "Prospect")

    return {
        "success": True,
        "students_synced": len(student_contacts),
        "staff_synced": len(staff_contacts),
        "student_result": student_res,
        "staff_result": staff_res
    }


# ---------- Hostinger n8n Webhook Endpoint ----------

@api.get("/n8n/config")
async def get_n8n_status(user: dict = Depends(get_current_user)):
    """Check if Hostinger n8n webhook URL is configured."""
    return {
        "configured": is_n8n_configured(),
        "subscription": "Hostinger AI automation apps",
        "webhook_url": os.environ.get("N8N_WEBHOOK_URL", "") if user.get("role") in ("admin", "manager") else "[Restricted]"
    }

@api.post("/n8n/test")
async def send_n8n_test(user: dict = Depends(require_manager_or_admin)):
    """Send a mock payment & invoice event to the Hostinger n8n instance (Manager or Admin)."""
    test_data = {
        "payment_id": str(uuid.uuid4()),
        "invoice_number": "INV-TEST-001",
        "amount": 5000,
        "date": date.today().isoformat(),
        "method": "online",
        "student_id": "test-student-id",
        "student_name": "Test Student",
        "student_phone": "+919999999999",
        "student_email": "student@example.com",
        "fees_total": 8000,
        "fees_paid": 5000,
        "balance_due": 3000
    }
    res = await asyncio.to_thread(dispatch_n8n_event, "test.invoice.generate", test_data)
    return res



# ---------- Google Sheets Settings ----------
@api.get("/settings/google-sheet")
async def get_google_sheet_setting(user: dict = Depends(get_current_user)):
    setting = await db.settings.find_one({"key": "google_sheet_webhook"})
    url = setting.get("url", "") if setting else ""
    if not url:
        url = os.environ.get("GOOGLE_SHEET_WEBHOOK_URL", "")
    return {
        "configured": bool(url),
        "webhook_url": url,
    }


@api.post("/settings/google-sheet")
async def save_google_sheet_setting(body: dict, user: dict = Depends(get_current_user)):
    if user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    url = body.get("webhook_url", "").strip()
    await db.settings.update_one(
        {"key": "google_sheet_webhook"},
        {"$set": {"key": "google_sheet_webhook", "url": url}},
        upsert=True
    )
    os.environ["GOOGLE_SHEET_WEBHOOK_URL"] = url
    return {"ok": True, "webhook_url": url}


@api.post("/settings/google-sheet/sync-all")
async def trigger_google_sheet_sync_all(user: dict = Depends(require_manager_or_admin)):
    result = await asyncio.to_thread(sync_all_active_students_to_sheet)
    return result


# Include router + middleware
app.include_router(api)

# ---------- CORS ----------
origins_env = os.environ.get("CORS_ORIGINS", "")
if origins_env.strip():
    allowed_origins = [o.strip() for o in origins_env.split(",") if o.strip()]
else:
    # Default: allow common local dev ports + any Vercel domain
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# ---------- Serve React Frontend ----------
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

FRONTEND_BUILD_DIR = Path(__file__).parent.parent / "frontend" / "build"

if FRONTEND_BUILD_DIR.exists():
    # Mount the /static folder containing bundle assets
    app.mount("/static", StaticFiles(directory=str(FRONTEND_BUILD_DIR / "static")), name="static")

    @app.get("/{catchall:path}")
    async def serve_frontend(request: Request, catchall: str):
        # Do not catch requests starting with api/
        if catchall.startswith("api"):
            raise HTTPException(status_code=404, detail="Not Found")
        
        # Check if the requested file actually exists in the build root (like favicon.ico, logo192.png)
        file_path = FRONTEND_BUILD_DIR / catchall
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
            
        # Default to the SPA index.html for page routing
        return FileResponse(str(FRONTEND_BUILD_DIR / "index.html"))
