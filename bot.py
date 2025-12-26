import telebot
import os
import time
import qrcode
import io
from telebot import types
from pymongo import MongoClient
from flask import Flask, request


# ---------------- ENV VARIABLES (Railway me set honge) ---------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
UPI_ID = os.getenv("UPI_ID")
MONGO_URI = os.getenv("MONGO_URI")
BASE_URL = os.getenv("BASE_URL")


# ---------------- DATABASE ----------------
client = MongoClient(MONGO_URI)
db = client["any2anybot"]
users_collection = db["users"]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


# ---------------- HELPERS ----------------
def get_user(uid):
    u = users_collection.find_one({"user_id": uid})
    if u is None:
        users_collection.insert_one({
            "user_id": uid,
            "vip": False,
            "usage": 0
        })
        return get_user(uid)
    return u


# ---------------- COMMANDS ----------------
@bot.message_handler(commands=['id'])
def send_id(msg):
    bot.send_message(msg.chat.id, f"🆔 Your ID:\n<code>{msg.from_user.id}</code>")


@bot.message_handler(commands=['stats'])
def admin_stats(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})
    bot.send_message(
        ADMIN_ID,
        f"📊 System Stats\n👥 Total users: {total}\n💎 VIP Users: {vip}"
    )


# ---------------- MAIN MENU ----------------
@bot.message_handler(commands=['start'])
def start(msg):
    get_user(msg.from_user.id)

    kb = types.ReplyKeyboardMarkup(True)
    kb.add("Convert Image", "💎 VIP Plans")

    bot.send_message(
        msg.chat.id,
        "<b>🔥 Any2Any Converter</b>\nConvert Anything → Anything\n\n"
        "Managed by <b>AskEdge Labs™</b>",
        reply_markup=kb
    )


# ---------------- VIP SYSTEM ----------------
@bot.message_handler(func=lambda m: m.text == "💎 VIP Plans")
def show_vip(msg):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("₹30 / 30 Days", callback_data="plan_30"),
        types.InlineKeyboardButton("₹59 / Lifetime", callback_data="plan_59")
    )
    bot.send_message(msg.chat.id, "🔥 Choose VIP Plan", reply_markup=kb)


# 📌 FINAL FIXED QR FUNCTION (IN-MEMORY)
def generate_qr(amount, uid):
    upi_url = f"upi://pay?pa={UPI_ID}&pn=AskEdgeLabs&am={amount}&cu=INR&tn=VIP-{uid}"
    qr_buffer = io.BytesIO()
    qrcode.make(upi_url).save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    return qr_buffer


@bot.callback_query_handler(func=lambda c: c.data.startswith("plan"))
def handle_payment(c):
    uid = c.from_user.id
    amount = 30 if c.data == "plan_30" else 59

    qr_img = generate_qr(amount, uid)

    bot.send_photo(
        uid,
        qr_img,
        caption=f"📌 Scan & Pay ₹{amount}\n"
                f"UPI: <code>{UPI_ID}</code>\n\n"
                "After payment — Send Screenshot"
    )

    bot.send_message(
        ADMIN_ID,
        f"💰 Payment Request\nUser: {uid}\nPlan: ₹{amount}\n\n"
        f"Approve:\n/approve_{uid}_{amount}"
    )


@bot.message_handler(commands=["approve"])
def approve(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    _, uid, amt = msg.text.split("_")
    uid = int(uid)

    users_collection.update_one(
        {"user_id": uid},
        {"$set": {"vip": True}}
    )
    bot.send_message(uid, "🎉 VIP Activated Successfully!")
    bot.send_message(ADMIN_ID, f"✔ VIP Activated for {uid}")


# ---------------- IMAGE PLACEHOLDER ----------------
@bot.message_handler(func=lambda m: m.text == "Convert Image")
def ask_image(msg):
    bot.send_message(msg.chat.id,
                     "📤 Send an image now!\n"
                     "(Next update: Compress / Resize / Format Convert)")


@bot.message_handler(content_types=['photo'])
def process_image(msg):
    bot.send_message(msg.chat.id,
                     "👌 Image received!\n"
                     "⚙ Processing tools coming next update!")


# ---------------- WEBHOOK SERVER ----------------
app = Flask(__name__)


@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates(
        [telebot.types.Update.de_json(request.data.decode())]
    )
    return "OK", 200


if __name__ == "__main__":
    print("🔄 Webhook refresh...")
    bot.remove_webhook()
    time.sleep(1)

    bot.set_webhook(
        url=f"{BASE_URL}/{TOKEN}",
        allowed_updates=["message", "callback_query"]
    )
    print("🚀 Webhook Set!")

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
