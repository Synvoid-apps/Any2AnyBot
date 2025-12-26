from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["any2any"]
users = db["users"]
files = db["files"]

# ---- USER SYSTEM ----
def get_user(uid):
    user = users.find_one({"_id": uid})
    if not user:
        user = {
            "_id": uid,
            "is_vip": False,
            "today_count": 0,
            "last_use": str(datetime.now().date())
        }
        users.insert_one(user)
    return user

def usage_allowed(uid):
    user = get_user(uid)
    if user["is_vip"]: return True
    return user["today_count"] < 10

def update_usage(uid):
    user = get_user(uid)
    today = str(datetime.now().date())
    if user["last_use"] != today:
        users.update_one({"_id": uid}, {"$set": {"today_count": 0, "last_use": today}})
    users.update_one({"_id": uid}, {"$inc": {"today_count": 1}})

# ---- VIP SYSTEM ----
def set_vip(uid, status=True):
    users.update_one({"_id": uid}, {"$set": {"is_vip": status}})

# ---- CLOUD FILE STORAGE ----
def save_file(uid, file_id, file_name, ftype):
    files.insert_one({
        "uid": uid,
        "file_id": file_id,
        "name": file_name,
        "type": ftype,
        "time": datetime.now()
    })

def list_files(uid, ftype):
    return list(files.find({"uid": uid, "type": ftype}).sort("_id", -1).limit(10))
