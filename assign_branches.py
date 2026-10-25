import os
import pymongo

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://learnanddrive:T5cYO6bCZYwYXP9w@driving.ws3cihd.mongodb.net/ridewell?retryWrites=true&w=majority"
)

client = pymongo.MongoClient(MONGO_URI)
db = client.ridewell

durga_id = "60c0aeea-9d83-40b1-8385-6ba952fa6ce4"
swati_id = "adbd1bd2-1324-4595-93c4-8e668ac821c9"
ambika_id = "5e143682-9407-4289-a82b-c12a2dd5d71f"

# 1. Update trainers location
db.users.update_one({"id": durga_id}, {"$set": {"location": "Madhapur"}})
db.users.update_one({"id": swati_id}, {"$set": {"location": "Attapur"}})
db.users.update_one({"id": ambika_id}, {"$set": {"location": "Attapur"}})
db.users.update_many(
    {"role": "trainer", "id": {"$nin": [durga_id, swati_id, ambika_id]}},
    {"$set": {"location": "Khajaguda"}}
)
print("Trainers location updated successfully.")

# 2. Update active students
# Madhapur
r_m = db.students.update_many({"assigned_trainer_id": durga_id}, {"$set": {"location": "Madhapur"}})
# Attapur
r_a = db.students.update_many({"assigned_trainer_id": {"$in": [swati_id, ambika_id]}}, {"$set": {"location": "Attapur"}})
# Khajaguda (all remaining active students)
r_k = db.students.update_many({"assigned_trainer_id": {"$nin": [durga_id, swati_id, ambika_id]}}, {"$set": {"location": "Khajaguda"}})

print(f"Active Students Updated: Madhapur={r_m.modified_count}, Attapur={r_a.modified_count}, Khajaguda={r_k.modified_count}")

# 3. Update archived students
db.archived_students.update_many({"assigned_trainer_id": durga_id}, {"$set": {"location": "Madhapur"}})
db.archived_students.update_many({"assigned_trainer_id": {"$in": [swati_id, ambika_id]}}, {"$set": {"location": "Attapur"}})
db.archived_students.update_many({"assigned_trainer_id": {"$nin": [durga_id, swati_id, ambika_id]}}, {"$set": {"location": "Khajaguda"}})
print("Archived Students Updated.")

print("\n=== FINAL BRANCH BREAKDOWN ===")
for loc in ["Attapur", "Khajaguda", "Madhapur"]:
    st_c = db.students.count_documents({"location": loc})
    tr_c = db.users.count_documents({"role": "trainer", "location": loc})
    trainers_in_loc = [t["name"] for t in db.users.find({"role": "trainer", "location": loc}, {"name": 1})]
    print(f"[{loc}]")
    print(f"  Trainers ({tr_c}): {trainers_in_loc}")
    print(f"  Active Students: {st_c}")
