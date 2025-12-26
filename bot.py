import telebot
import os
import time
import qrcode
import io
from telebot import types
from pymongo import MongoClient
from flask import Flask, request


# ✔ ENV VARIABLES — must set in Railway
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")
BASE_URL = os.getenv("BASE_URL")

# ✔ MongoDB
client = MongoClient(MONGO_URI)
db = client["any2anybot"]
users_collection = db["users"]
payment_links = db["payment_links"]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


# ---------------- USER DB ----------------
def get_user(uid):
    u = users_collection.find_one({"user_id": uid})
    if not u:
        users_collection.insert_one({"user_id": uid, "vip": False})
    return users_collection.find_one({"user_id": uid})


# ---------------- COMMANDS ----------------
@bot.message_handler(commands=['id'])
def user_id(msg):
    bot.send_message(msg.chat.id, f"🆔 Your ID:\n<code>{msg.from_user.id}</code>")


@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID: return
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})
    links = payment_links.count_documents({})
    bot.send_message(
        ADMIN_ID,
        f"📊 System Stats:\n"
        f"👥 Users: {total}\n"
        f"💎 VIP: {vip}\n"
        f"🔗 Links: {links}"
    )


# ---------------- MAIN MENU ----------------
@bot.message_handler(commands=['start'])
def start(msg):
    get_user(msg.from_user.id)

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Convert Image", "💎 VIP Plans")

    bot.send_message(
        msg.chat.id,
        "<b>🔥 Any2Any Converter</b>\n"
        "Convert Anything → Anything\n\n"
        "Managed by <b>AskEdge Labs™</b>",
        reply_markup=kb
    )


# ---------------- VIP PANEL ----------------
@bot.message_handler(func=lambda m: m.text == "💎 VIP Plans")
def vip(msg):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("₹30 / 30 Days", callback_data="V30"),
        types.InlineKeyboardButton("₹59 / Lifetime", callback_data="V59")
    )
    bot.send_message(msg.chat.id, "🔥 Choose VIP Plan", reply_markup=kb)


def get_next_link(amount):
    return payment_links.find_one({"status": "available", "amount": amount})


def assign_link(link_id, uid):
    payment_links.update_one(
        {"id": link_id},
        {"$set": {"status": "assigned", "assigned_to": uid, "ts": time.time()}}
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("V"))
def handle_payment(c):
    uid = c.from_user.id
    amount = 30 if c.data == "V30" else 59

    link = get_next_link(amount)

    if not link:
        bot.send_message(uid, "❌ All payment links are used.\nAdmin will add more soon!")
        bot.send_message(ADMIN_ID, "⚠️ Add more payment links!")
        return

    assign_link(link["id"], uid)

    bot.send_message(
        uid,
        f"💳 Pay ₹{amount} using secure link:\n\n"
        f"{link['url']}\n\n"
        "After payment → Send Screenshot"
    )

    bot.send_message(
        ADMIN_ID,
        f"🆕 Payment Link Assigned\n"
        f"User: {uid}\n"
        f"Link ID: {link['id']}\n"
        f"Amount: ₹{amount}\n\n"
        f"Mark Paid:\n/paid_{link['id']}_{uid}\n"
        f"Reset Link:\n/unpaid_{link['id']}"
    )


# ---------------- ADMIN: PAYMENT CONTROL ----------------
@bot.message_handler(commands=['addlink'])
def add_link(msg):
    if msg.from_user.id != ADMIN_ID: return

    try:
        _, amount, url = msg.text.split(" ", 2)
        amount = int(amount)
        new_id = payment_links.count_documents({}) + 1

        payment_links.insert_one({
            "id": new_id,
            "amount": amount,
            "url": url,
            "status": "available",
            "assigned_to": None
        })

        bot.send_message(ADMIN_ID, f"✔ Link Added!\nID: {new_id}\n₹{amount}\n{url}")

    except:
        bot.send_message(ADMIN_ID, "❌ Format:\n/addlink 30 <URL>")


@bot.message_handler(commands=['links'])
def list_links(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    
    data = payment_links.find()
    text = "🔗 Payment Links:\n\n"
    for d in data:
        text += f"ID {d['id']} | ₹{d['amount']} | {d['status']}\n"
    bot.send_message(ADMIN_ID, text)


@bot.message_handler(commands=['paid'])
def paid(msg):
    if msg.from_user.id != ADMIN_ID: return
    _, lid, uid = msg.text.split("_")
    lid, uid = int(lid), int(uid)

    users_collection.update_one({"user_id": uid}, {"$set": {"vip": True}})
    payment_links.update_one({"id": lid}, {"$set": {"status": "paid"}})

    bot.send_message(uid, "🎉 VIP Activated!")
    bot.send_message(ADMIN_ID, f"✔ Paid confirmed for User {uid}")


@bot.message_handler(commands=['unpaid'])
def unpaid(msg):
    if msg.from_user.id != ADMIN_ID: return
    _, lid = msg.text.split("_")
    lid = int(lid)

    payment_links.update_one(
        {"id": lid},
        {"$set": {"status": "available", "assigned_to": None, "ts": None}}
    )

    bot.send_message(ADMIN_ID, f"🔁 Link {lid} reset!")


# ---------------- PLACEHOLDER ----------------
@bot.message_handler(func=lambda m: m.text == "Convert Image")
def convert_image(msg):
    bot.send_message(msg.chat.id, "📤 Send any image\n(Next update: Compression + Format)")


@bot.message_handler(content_types=['photo'])
def receive_photo(msg):
    bot.send_message(msg.chat.id, "👌 Image received! Tools coming next update!")


# ---------------- WEBHOOK SERVER ----------------
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates(
        [telebot.types.Update.de_json(request.data.decode())]
    )
    return "OK", 200


if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{BASE_URL}/{TOKEN}")
    
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
