from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["any2any"]
users = db["users"]

def get_user(user_id):
    user = users.find_one({"_id": user_id})
    if not user:
        user = {
            "_id": user_id,
            "is_vip": False,
            "today_count": 0,
            "last_use": str(datetime.now().date())
        }
        users.insert_one(user)
    return user

def update_usage(user_id):
    user = get_user(user_id)
    last = user["last_use"]
    today = str(datetime.now().date())

    if last != today:
        users.update_one({"_id": user_id},
                         {"$set": {"today_count": 0, "last_use": today}})

    users.update_one({"_id": user_id},
                     {"$inc": {"today_count": 1}})

def usage_allowed(user_id):
    user = get_user(user_id)
    if user["is_vip"]:
        return True

    if user["today_count"] >= 10:
        return False
    return True

def reset_limits():
    today = str(datetime.now().date())
    users.update_many({}, {"$set": {"today_count": 0, "last_use": today}})
