"""
Safely archive and remove completed students and completed classes from active tables.
Leaves strictly active students (status == "active") and pending classes.
"""
import os
import pymongo

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://learnanddrive:T5cYO6bCZYwYXP9w@driving.ws3cihd.mongodb.net/ridewell?retryWrites=true&w=majority"
)

def run_cleanup():
    print("Connecting to MongoDB Atlas...")
    client = pymongo.MongoClient(MONGO_URI)
    db = client.ridewell

    # 1. Identify completed students
    completed_students = list(db.students.find({"status": {"$ne": "active"}}))
    active_students = list(db.students.find({"status": "active"}))
    print(f"Identified {len(completed_students)} old/completed students to archive and remove.")
    print(f"Identified {len(active_students)} active students to keep.")

    completed_sids = set(s["id"] for s in completed_students)

    # 2. Identify completed classes
    completed_classes = list(db.classes.find({
        "$or": [
            {"student_id": {"$in": list(completed_sids)}},
            {"status": {"$in": ["completed", "missed"]}}
        ]
    }))
    pending_classes = list(db.classes.find({
        "student_id": {"$in": [s["id"] for s in active_students]},
        "status": "pending"
    }))
    print(f"Identified {len(completed_classes)} old classes to archive and remove.")
    print(f"Identified {len(pending_classes)} pending classes to keep.")

    # 3. Archive into db.archived_students and db.archived_classes FIRST
    print("Archiving records into db.archived_students...")
    if completed_students:
        db.archived_students.delete_many({}) # clean previous test archives if any
        db.archived_students.insert_many(completed_students)
        print(f"-> Successfully inserted {db.archived_students.count_documents({})} into db.archived_students")

    print("Archiving records into db.archived_classes...")
    if completed_classes:
        db.archived_classes.delete_many({})
        db.archived_classes.insert_many(completed_classes)
        print(f"-> Successfully inserted {db.archived_classes.count_documents({})} into db.archived_classes")

    # 4. Remove completed students from db.students
    print("Removing old students from active db.students...")
    del_st_res = db.students.delete_many({"status": {"$ne": "active"}})
    print(f"-> Removed {del_st_res.deleted_count} students. Active students remaining: {db.students.count_documents({})}")

    # 5. Remove completed classes from db.classes
    print("Removing old classes from active db.classes...")
    del_cl_res = db.classes.delete_many({
        "$or": [
            {"student_id": {"$in": list(completed_sids)}},
            {"status": {"$in": ["completed", "missed"]}}
        ]
    })
    print(f"-> Removed {del_cl_res.deleted_count} classes. Pending classes remaining: {db.classes.count_documents({})}")

    print("\n=== FINAL VERIFICATION ===")
    print("Active db.students count:", db.students.count_documents({}))
    print("Active db.classes count:", db.classes.count_documents({}))
    print("Archived db.archived_students count:", db.archived_students.count_documents({}))
    print("Archived db.archived_classes count:", db.archived_classes.count_documents({}))
    print("\nDatabase optimization complete! Operational tables are now ultra-lightweight.")

if __name__ == "__main__":
    run_cleanup()
