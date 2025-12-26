import telebot
import os
import time
import qrcode
from telebot import types
from pymongo import MongoClient
from datetime import datetime, timedelta

# ───────── CONFIG ─────────
TOKEN = "YOUR_BOT_TOKEN"
ADMIN_ID = int("YOUR_ADMIN_ID")  # Example: 6141075929
UPI_ID = "YOUR_UPI_ID"  # Example: adityaraj8578095389-2@okicici
QR_FOLDER = "qr"

MONGO_URI = "YOUR_MONGO_URI"
client = MongoClient(MONGO_URI)
db = client["any2anybot"]
users_collection = db["users"]
files_collection = db["files"]

# QR Folder Secure Setup
if not os.path.exists(QR_FOLDER):
    os.makedirs(QR_FOLDER)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ───────── DB FUNCTIONS ─────────
def get_user(uid):
    user = users_collection.find_one({"user_id": uid})
    if not user:
        users_collection.insert_one({
            "user_id": uid,
            "vip": False,
            "usage": 0,
            "expiry": None
        })
        return get_user(uid)
    return user

def update_usage(uid):
    users_collection.update_one({"user_id": uid}, {"$inc": {"usage": 1}})

def set_vip(uid, days):
    expiry = datetime.now() + timedelta(days=days)
    users_collection.update_one({"user_id": uid}, {"$set": {"vip": True, "expiry": expiry}})
    bot.send_message(uid, "🎉 VIP Activated Successfully! Enjoy Unlimited Conversions 🚀")

# ───────── ADMIN PANEL ─────────
@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    total_users = users_collection.count_documents({})
    vip_users = users_collection.count_documents({"vip": True})
    bot.send_message(ADMIN_ID,
                     f"📊 <b>Admin Panel</b>\n\n"
                     f"👥 Users: {total_users}\n"
                     f"💎 VIP Users: {vip_users}")

# ───────── HOME / MENU ─────────
@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id
    get_user(uid)
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Convert File", "💎 VIP Plans")
    bot.send_message(uid, 
        "<b>🚀 Welcome to Any2AnyBot</b>\n"
        "Convert Anything → Anything 🔁✨\n"
        "Managed by <b>AskEdge Labs™️</b>",
        reply_markup=kb)

# ───────── VIP PLANS ─────────
@bot.message_handler(func=lambda m: m.text == "💎 VIP Plans")
def vip(msg):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("₹30 / 30 Days", callback_data="vip_30"),
        types.InlineKeyboardButton("₹59 / Lifetime", callback_data="vip_life")
    )
    bot.send_message(msg.chat.id,
        "<b>Unlimited Features 🔥</b>\n\n"
        "✔ No Limits\n"
        "✔ Fast Conversion\n"
        "✔ Access Cloud History\n\n"
        "Select a Plan 👇",
        reply_markup=kb)

# ───────── QR GENERATOR ─────────
def create_qr(amount, uid):
    upi_url = f"upi://pay?pa={UPI_ID}&pn=AskEdgeLabs&am={amount}&cu=INR&tn=VIP-{uid}"
    qr_path = f"{QR_FOLDER}/vip_{uid}_{amount}.png"
    qrcode.make(upi_url).save(qr_path)
    return qr_path

@bot.callback_query_handler(func=lambda c: c.data.startswith("vip_"))
def process_vip(c):
    amount = 30 if c.data == "vip_30" else 59
    img = create_qr(amount, c.from_user.id)
    bot.send_photo(c.message.chat.id, photo=open(img, 'rb'),
        caption=f"Scan & Pay UPI\n\nAmount: ₹{amount}\nUPI ID: {UPI_ID}\n\n"
                "📌 After Payment: Send Screenshot to Admin for Approval")
    bot.send_message(ADMIN_ID,
        f"⚠ Payment Pending ⚠\nUser ID: {c.from_user.id}\nPlan: ₹{amount}\n"
        "Approve with:\n"
        f"/approve_{c.from_user.id}_30" if amount == 30 else f"/approve_{c.from_user.id}_life")

# ───────── ADMIN APPROVAL COMMAND ─────────
@bot.message_handler(commands=['approve'])
def approve(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    
    data = msg.text.split("_")
    uid = int(data[1])
    plan = data[2]

    if plan == "30":
        set_vip(uid, 30)
    else:
        set_vip(uid, 9999)

    bot.send_message(ADMIN_ID, f"✔ VIP Activated for {uid}")

# ───────── CONVERSION ENTRY POINT ─────────
@bot.message_handler(func=lambda m: m.text == "Convert File")
def ask_file(msg):
    bot.send_message(msg.chat.id, "📤 Send any file to convert")

@bot.message_handler(content_types=['document'])
def file_received(msg):
    uid = msg.from_user.id
    user = get_user(uid)

    if not user["vip"]:
        if user["usage"] >= 5:
            bot.send_message(uid, "⚠ Free Limit Reached! Buy VIP for Unlimited 🚀")
            return

    update_usage(uid)
    bot.send_message(uid,
        "✔ File saved!\nProcessing coming in next update 🔥")

# ───────── WEBHOOK SERVER (Flask) ─────────
from flask import Flask, request
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

# Start WebHook
FULL_URL = f"https://any2anybot-production.up.railway.app/{TOKEN}"
bot.set_webhook(url=FULL_URL)

# Run App
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
