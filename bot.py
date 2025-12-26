import telebot
import os
import time
import qrcode
from telebot import types
from pymongo import MongoClient
from datetime import datetime, timedelta
from flask import Flask, request

# ───────── ENV FROM RAILWAY ─────────
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
UPI_ID = os.getenv("UPI_ID")
MONGO_URI = os.getenv("MONGO_URI")
BASE_URL = os.getenv("BASE_URL")  # Railway URL

QR_FOLDER = "qr"

# ───────── DATABASE ─────────
client = MongoClient(MONGO_URI)
db = client["any2anybot"]
users_collection = db["users"]
files_collection = db["files"]

# Ensure QR folder exists
if not os.path.exists(QR_FOLDER):
    os.makedirs(QR_FOLDER)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ───────── FUNCTIONS ─────────
def get_user(uid):
    u = users_collection.find_one({"user_id": uid})
    if not u:
        users_collection.insert_one({
            "user_id": uid,
            "vip": False,
            "usage": 0,
            "expiry": None,
        })
        return get_user(uid)
    return u

def set_vip(uid, days):
    expiry = datetime.now() + timedelta(days=days)
    users_collection.update_one({"user_id": uid}, {"$set": {"vip": True, "expiry": expiry}})
    bot.send_message(uid, "🎉 VIP Activated — Enjoy Unlimited Access 🚀")

def update_usage(uid):
    users_collection.update_one({"user_id": uid}, {"$inc": {"usage": 1}})

# ───────── ADMIN ─────────
@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})
    bot.send_message(ADMIN_ID,
                     f"📊 Admin Panel\n\n"
                     f"👥 Users: {total}\n"
                     f"💎 VIP: {vip}")

# ───────── MAIN MENU ─────────
@bot.message_handler(commands=['start'])
def start(msg):
    get_user(msg.from_user.id)
    kb = types.ReplyKeyboardMarkup(True)
    kb.add("Convert File", "💎 VIP Plans")
    bot.send_message(msg.chat.id,
                     "<b>🔥 Any2Any Converter</b>\nConvert Anything → Anything\n\nManaged by <b>AskEdge Labs™️</b>",
                     reply_markup=kb)

# ───────── VIP PLANS ─────────
@bot.message_handler(func=lambda m: m.text == "💎 VIP Plans")
def plans(msg):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("₹30 / 30 Days", callback_data="plan_30"),
        types.InlineKeyboardButton("₹59 / Lifetime", callback_data="plan_59")
    )
    bot.send_message(msg.chat.id, "Choose Your VIP Plan 🔥", reply_markup=kb)

def make_qr(amount, uid):
    upi_url = f"upi://pay?pa={UPI_ID}&pn=AskEdgeLabs&am={amount}&cu=INR&tn=VIP{uid}"
    path = f"{QR_FOLDER}/vip_{uid}_{amount}.png"
    qrcode.make(upi_url).save(path)
    return path

@bot.callback_query_handler(func=lambda c: c.data.startswith("plan"))
def handle_plans(c):
    amount = 30 if c.data == "plan_30" else 59
    img = make_qr(amount, c.from_user.id)

    bot.send_photo(c.message.chat.id, open(img, 'rb'),
                   caption=f"Amount: ₹{amount}\nUPI ID: {UPI_ID}\n\nSend Screenshot After Payment")

    bot.send_message(ADMIN_ID,
                     f"⚠ Payment Request\nUser: {c.from_user.id}\nPlan: ₹{amount}\n\n"
                     f"Activate:\n/approve_{c.from_user.id}_{amount}")

@bot.message_handler(commands=['approve'])
def approve(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    _, uid, amt = msg.text.split("_")
    uid = int(uid)
    days = 30 if amt == "30" else 9999
    set_vip(uid, days)

# ───────── FILE RECEIVE ─────────
@bot.message_handler(func=lambda m: m.text == "Convert File")
def ask(msg):
    bot.send_message(msg.chat.id, "📤 Send any file")

@bot.message_handler(content_types=['document'])
def doc(msg):
    user = get_user(msg.from_user.id)
    if not user["vip"]:
        if user["usage"] >= 5:
            bot.send_message(msg.chat.id, "⚠ Free Limit Reached — Buy VIP")
            return
    update_usage(msg.from_user.id)
    bot.send_message(msg.chat.id, "✔ File Received — Conversion update coming 🔥")

# ───────── WEBHOOK SERVER ─────────
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def wh():
    bot.process_new_updates([telebot.types.Update.de_json(request.data.decode())])
    return "OK", 200

FULL_URL = f"{BASE_URL}/{TOKEN}"
bot.set_webhook(url=FULL_URL)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
