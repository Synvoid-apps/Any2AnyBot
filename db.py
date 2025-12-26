from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["any2any"]
users = db["users"]

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
