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
BASE_URL = os.getenv("BASE_URL")

QR_FOLDER = "qr"

# ───────── DATABASE ─────────
client = MongoClient(MONGO_URI)
db = client["any2anybot"]
users_collection = db["users"]
files_collection = db["files"]

if not os.path.exists(QR_FOLDER):
    os.makedirs(QR_FOLDER)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ───────── BASIC COMMANDS ─────────
@bot.message_handler(commands=['id'])
def send_user_id(msg):
    bot.send_message(msg.chat.id, f"🆔 Your Telegram ID:\n<code>{msg.from_user.id}</code>")

@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})

    bot.send_message(ADMIN_ID,
                     f"📊 <b>Admin Panel</b>\n\n"
                     f"👥 Users: {total}\n"
                     f"💎 VIP: {vip}\n"
                     f"Managed by AskEdge Labs™️")

# ───────── USER SYSTEM ─────────
def get_user(uid):
    u = users_collection.find_one({"user_id": uid})
    if not u:
        users_collection.insert_one({
            "user_id": uid,
            "vip": False,
            "usage": 0
        })
        return get_user(uid)
    return u

def update_usage(uid):
    users_collection.update_one({"user_id": uid}, {"$inc": {"usage": 1}})

# ───────── MAIN MENU ─────────
@bot.message_handler(commands=['start'])
def start(msg):
    get_user(msg.from_user.id)

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Convert Image", "💎 VIP Plans")

    bot.send_message(msg.chat.id,
                     "🔥 <b>Any2Any Converter</b>\n"
                     "Convert Anything ➝ Anything\n\n"
                     "Managed by <b>AskEdge Labs™️</b>",
                     reply_markup=kb)

# ───────── VIP PLANS ─────────
@bot.message_handler(func=lambda m: m.text == "💎 VIP Plans")
def vip_options(msg):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("₹30 / 30 Days", callback_data="plan_30"),
        types.InlineKeyboardButton("₹59 / Lifetime", callback_data="plan_59")
    )
    bot.send_message(msg.chat.id, "🔥 Choose your VIP Plan", reply_markup=kb)

def generate_qr(amount, uid):
    upi_url = f"upi://pay?pa={UPI_ID}&pn=AskEdgeLabs&am={amount}&cu=INR&tn=VIP{uid}"
    path = f"{QR_FOLDER}/vip_{uid}_{amount}.png"
    qrcode.make(upi_url).save(path)
    return path

@bot.callback_query_handler(func=lambda c: c.data.startswith("plan"))
def vip_payment(c):
    amount = 30 if c.data == "plan_30" else 59
    uid = c.from_user.id

    qr = generate_qr(amount, uid)
    bot.send_photo(uid, open(qr, 'rb'),
                   caption=f"Scan & Pay UPI\n\n₹{amount} → {UPI_ID}\n\n"
                           "After Payment → Send Screenshot for Activation 🔥")

    bot.send_message(ADMIN_ID,
                     f"⚠ Payment Request\nUser: {uid}\nPlan: ₹{amount}\n\n"
                     f"Approve:\n/approve_{uid}_{amount}")

@bot.message_handler(commands=["approve"])
def approve(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    _, uid, amt = msg.text.split("_")
    uid = int(uid)
    users_collection.update_one({"user_id": uid}, {"$set": {"vip": True}})
    bot.send_message(uid, "🎉 VIP Activated Successfully!")
    bot.send_message(ADMIN_ID, f"✔ VIP Activated for {uid}")

# ───────── IMAGE COMPRESSION FEATURE ─────────
@bot.message_handler(func=lambda m: m.text == "Convert Image")
def ask_img(msg):
    bot.send_message(msg.chat.id,
                     "📤 Send any image to convert or reduce MB ➝ KB")

@bot.message_handler(content_types=['photo'])
def image_received(msg):
    uid = msg.from_user.id
    get_user(uid)
    bot.send_message(uid,
                     "👌 Image received!\nNow enter target size e.g.:\n\n"
                     "<code>100KB</code> or <code>1MB</code>")

    bot.register_next_step_handler(msg, compress_step)

def compress_step(msg):
    bot.send_message(msg.chat.id, "⚡ Compression coming in next update!")

# ───────── WEBHOOK SERVER ─────────
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.data.decode())])
    return "OK", 200

if __name__ == "__main__":
    print("Refreshing Webhook...")
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(
        url=f"{BASE_URL}/{TOKEN}",
        allowed_updates=["message", "callback_query"]
    )
    print("Webhook Set:", f"{BASE_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
