from pymongo import MongoClient
from datetime import datetime, timedelta
from config import MONGO_URI, MONTHLY_DAYS

client = MongoClient(MONGO_URI)
db = client["any2any"]
users = db["users"]
files = db["files"]

def get_user(uid):
    user = users.find_one({"_id": uid})
    if not user:
        user = {
            "_id": uid,
            "is_vip": False,
            "expiry": None,
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

def set_vip(uid, status=True, days=MONTHLY_DAYS):
    expiry = None
    if status:
        expiry = datetime.now() + timedelta(days=days)
    users.update_one({"_id": uid}, {"$set": {"is_vip": status, "expiry": expiry}})

def check_vip_expiry(uid):
    user = get_user(uid)
    if user["expiry"] and datetime.now() > user["expiry"]:
        users.update_one({"_id": uid}, {"$set": {"is_vip": False, "expiry": None}})
        return True
    return False

def save_file(uid, fid, name, ftype):
    files.insert_one({
        "uid": uid,
        "file_id": fid,
        "name": name,
        "type": ftype,
        "time": datetime.now()
    })

def list_files(uid, ftype):
    return list(files.find({"uid": uid, "type": ftype}).sort("_id", -1).limit(10))

def get_stats():
    return (
        users.count_documents({}),
        users.count_documents({"is_vip": True}),
        files.count_documents({})
    )
