import os
import pymongo

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://learnanddrive:T5cYO6bCZYwYXP9w@driving.ws3cihd.mongodb.net/ridewell?retryWrites=true&w=majority"
)

client = pymongo.MongoClient(MONGO_URI)
db = client.ridewell

def to_12h(time_str):
    if not time_str or "-" not in time_str:
        return time_str
    parts = time_str.split("-")
    res = []
    for p in parts:
        p = p.strip()
        if ":" not in p:
            res.append(p)
            continue
        h, m = p.split(":")[:2]
        h = int(h)
        ampm = "PM" if h >= 12 else "AM"
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        res.append(f"{h12:02d}:{m} {ampm}")
    return " - ".join(res)

for s in db.slots.find():
    old_label = s.get("label")
    new_label = to_12h(old_label)
    print(f"Slot {s['id'][:6]}: {old_label} -> {new_label}")
    # Update both label and label_12h for backward & forward compatibility
    db.slots.update_one({"id": s["id"]}, {"$set": {"label": new_label, "label_24h": old_label, "label_12h": new_label}})

# Update student slot_time field to 12h
for st in db.students.find():
    old_st_slot = st.get("slot_time")
    if old_st_slot and "-" in old_st_slot and ("AM" not in old_st_slot and "PM" not in old_st_slot):
        new_st_slot = to_12h(old_st_slot)
        db.students.update_one({"id": st["id"]}, {"$set": {"slot_time": new_st_slot, "slot_time_24h": old_st_slot}})

print("Slots and Student slot times updated to 12-hour format in MongoDB Atlas.")
