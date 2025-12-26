import telebot
import os
import time
import qrcode
from telebot import types
from pymongo import MongoClient
from datetime import datetime, timedelta
from flask import Flask, request

# ✔ ENV from Railway (Secret & Safe)
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
UPI_ID = os.getenv("UPI_ID")
MONGO_URI = os.getenv("MONGO_URI")
BASE_URL = os.getenv("BASE_URL")

# ✔ Database
client = MongoClient(MONGO_URI)
db = client["any2anybot"]
users_collection = db["users"]
files_collection = db["files"]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ✔ COMMAND: Show User ID
@bot.message_handler(commands=['id'])
def send_user_id(msg):
    bot.send_message(msg.chat.id, f"🆔 Your ID:\n<code>{msg.from_user.id}</code>")

# ✔ ADMIN PANEL
@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})

    bot.send_message(
        ADMIN_ID,
        f"📊 Admin Panel\n\n"
        f"👥 Users: {total}\n"
        f"💎 VIP Users: {vip}"
    )

# ✔ USER REGISTER
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

# ✔ MAIN UI
@bot.message_handler(commands=['start'])
def start(msg):
    get_user(msg.from_user.id)

    kb = types.ReplyKeyboardMarkup(True)
    kb.add("Convert Image", "💎 VIP Plans")

    bot.send_message(
        msg.chat.id,
        "<b>🔥 Any2Any Converter</b>\nConvert Anything → Anything\n\n"
        "Managed by <b>AskEdge Labs™️</b>",
        reply_markup=kb
    )

# ✔ VIP UI
@bot.message_handler(func=lambda m: m.text == "💎 VIP Plans")
def vip(msg):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("₹30 / 30 Days", callback_data="plan_30"),
        types.InlineKeyboardButton("₹59 / Lifetime", callback_data="plan_59")
    )
    bot.send_message(msg.chat.id, "🔥 Choose VIP Plan", reply_markup=kb)

# ✔ QR Generator (Fully Fixed)
def generate_qr(amount, uid):
    upi_url = f"upi://pay?pa={UPI_ID}&pn=AskEdgeLabs&am={amount}&cu=INR&tn=VIP-{uid}"
    path = f"/tmp/vip_{uid}_{amount}.png"
    qrcode.make(upi_url).save(path)
    return path

@bot.callback_query_handler(func=lambda c: c.data.startswith("plan"))
def vip_payment(c):
    amount = 30 if c.data == "plan_30" else 59
    uid = c.from_user.id

    qr = generate_qr(amount, uid)
    bot.send_photo(uid, open(qr, 'rb'),
                   caption=f"Scan & Pay ₹{amount} to:\n\n<code>{UPI_ID}</code>\n\n"
                           "After Payment → Send Screenshot")

    bot.send_message(
        ADMIN_ID,
        f"⚠ Payment Request\nUser: {uid}\nPlan: ₹{amount}\n\n"
        f"Activate:\n/approve_{uid}_{amount}"
    )

# ✔ ADMIN Approve VIP
@bot.message_handler(commands=["approve"])
def approve(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    _, uid, amt = msg.text.split("_")
    uid = int(uid)
    users_collection.update_one({"user_id": uid}, {"$set": {"vip": True}})
    bot.send_message(uid, "🎉 VIP Activated Successfully!")
    bot.send_message(ADMIN_ID, f"✔ VIP Activated for {uid}")

# ✔ Convert Image Placeholder
@bot.message_handler(func=lambda m: m.text == "Convert Image")
def ask_img(msg):
    bot.send_message(msg.chat.id, "📤 Send any image...\n"
                                  "(Next update: Compress / Resize / Format Convert UI)")

@bot.message_handler(content_types=['photo'])
def img(msg):
    bot.send_message(msg.chat.id, "👌 Image received!\n🔥 Conversion engine next update!")

# ✔ WEBHOOK SERVER (Full Fix)
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates(
        [telebot.types.Update.de_json(request.data.decode())]
    )
    return "OK", 200

if __name__ == "__main__":
    print("🔄 Resetting Webhook...")
    bot.remove_webhook()
    time.sleep(2)

    success = bot.set_webhook(
        url=f"{BASE_URL}/{TOKEN}",
        allowed_updates=["message", "callback_query"]
    )
    print("Webhook Set:", success)

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
