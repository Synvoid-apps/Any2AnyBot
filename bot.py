import telebot
import os
import time
from telebot import types
from pymongo import MongoClient
from flask import Flask, request


# ---------------- ENV VARIABLES ----------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")
BASE_URL = os.getenv("BASE_URL")

# ---------------- DATABASE ----------------
client = MongoClient(MONGO_URI)
db = client["any2anybot"]
users_collection = db["users"]
payment_links = db["payment_links"]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


# ---------------- USER REGISTER ----------------
def get_user(uid):
    u = users_collection.find_one({"user_id": uid})
    if not u:
        users_collection.insert_one({"user_id": uid, "vip": False})
        return get_user(uid)
    return u


# ---------------- ADMIN PANEL UI ----------------
def admin_panel(chat_id):
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})
    pending = payment_links.count_documents({"status": "assigned"})

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🔗 Manage Links", callback_data="admin_links"),
        types.InlineKeyboardButton("👥 Users", callback_data="admin_users")
    )
    kb.add(
        types.InlineKeyboardButton("📊 System Stats", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
    )

    bot.send_message(
        chat_id,
        f"👑 <b>AskEdge Admin Panel</b>\n\n"
        f"👥 Users: {total}\n"
        f"💎 VIP: {vip}\n"
        f"🕒 Pending Payments: {pending}",
        reply_markup=kb
    )


@bot.message_handler(commands=['admin'])
def open_admin(msg):
    if msg.from_user.id != ADMIN_ID: return
    admin_panel(msg.chat.id)


# ---------------- COMMANDS ----------------
@bot.message_handler(commands=['id'])
def user_id(msg):
    bot.send_message(msg.chat.id, f"🆔 <b>Your ID:</b>\n<code>{msg.from_user.id}</code>")


@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID: return
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})
    bot.send_message(
        ADMIN_ID,
        f"📊 Stats:\n"
        f"👥 Users: {total}\n"
        f"💎 VIP Users: {vip}"
    )


# ---------------- MAIN MENU ----------------
@bot.message_handler(commands=['start'])
def start(msg):
    get_user(msg.from_user.id)

    if msg.from_user.id == ADMIN_ID:
        admin_panel(msg.chat.id)
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Convert Image", "💎 VIP Plans")

    bot.send_message(
        msg.chat.id,
        "<b>🔥 Any2Any Converter</b>\nConvert Anything → Anything\n\nManaged by <b>AskEdge Labs™</b>",
        reply_markup=kb
    )


# ---------------- VIP SYSTEM ----------------
@bot.message_handler(func=lambda m: m.text == "💎 VIP Plans")
def vip(msg):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("₹30 / 30 Days", callback_data="V30"),
        types.InlineKeyboardButton("₹59 / Lifetime", callback_data="V59")
    )
    bot.send_message(msg.chat.id, "💎 Choose a VIP Plan:", reply_markup=kb)


def get_next_link(amount):
    return payment_links.find_one({"status": "available", "amount": amount})


def assign_link(link_id, uid):
    payment_links.update_one(
        {"id": link_id},
        {"$set": {"status": "assigned", "assigned_to": uid, "ts": time.time()}}
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("V"))
def pick_plan(c):
    uid = c.from_user.id
    amount = 30 if c.data == "V30" else 59

    link = get_next_link(amount)

    if not link:
        bot.send_message(uid, "❌ All payment links used. Admin adding new links!")
        bot.send_message(ADMIN_ID, "⚠ Add more payment links ASAP!")
        return

    assign_link(link["id"], uid)

    bot.send_message(
        uid,
        f"💳 Pay ₹{amount} using the link below 👇\n\n"
        f"{link['url']}\n\n"
        "After payment — Send Screenshot 📸"
    )

    bot.send_message(
        ADMIN_ID,
        f"🆕 VIP Request\nUser: {uid}\nLink ID: {link['id']}\nAmount: ₹{amount}\n\n"
        f"Mark Paid:\n/paid_{link['id']}_{uid}\n"
        f"Mark Unpaid:\n/unpaid_{link['id']}"
    )


# ---------------- ADMIN — PAYMENT CONTROL ----------------
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
    if msg.from_user.id != ADMIN_ID: return

    data = payment_links.find()
    text = "🔗 Payment Links:\n\n"
    for d in data:
        text += f"ID: {d['id']} | ₹{d['amount']} | {d['status']}\n"
    bot.send_message(ADMIN_ID, text or "No links found")


@bot.message_handler(commands=['paid'])
def mark_paid(msg):
    if msg.from_user.id != ADMIN_ID: return
    _, lid, uid = msg.text.split("_")
    lid, uid = int(lid), int(uid)

    users_collection.update_one({"user_id": uid}, {"$set": {"vip": True}})
    payment_links.update_one({"id": lid}, {"$set": {"status": "paid"}})

    bot.send_message(uid, "🎉 VIP Activated! Enjoy unlimited power!")
    bot.send_message(ADMIN_ID, f"✔ Payment Confirmed for User {uid}")


@bot.message_handler(commands=['unpaid'])
def unpaid(msg):
    if msg.from_user.id != ADMIN_ID: return
    _, lid = msg.text.split("_")
    lid = int(lid)

    payment_links.update_one(
        {"id": lid},
        {"$set": {"status": "available", "assigned_to": None, "ts": None}}
    )

    bot.send_message(ADMIN_ID, f"🔁 Link {lid} reset to available")


# ---------------- ADMIN PANEL CALLBACKS ----------------
@bot.callback_query_handler(func=lambda c: c.data == "admin_links")
def cl_links(c):
    if c.from_user.id != ADMIN_ID: return
    bot.send_message(c.message.chat.id,
                     "🔗 Link Commands:\n\n"
                     "/addlink 30 <URL>\n/addlink 59 <URL>\n"
                     "/links\n"
                     "/paid_id_userid\n"
                     "/unpaid_id")


@bot.callback_query_handler(func=lambda c: c.data == "admin_users")
def cl_users(c):
    if c.from_user.id != ADMIN_ID: return
    users = users_collection.find()
    txt = "👥 Users List:\n\n"
    for u in users:
        txt += f"🆔 {u['user_id']} - {'VIP' if u.get('vip') else 'FREE'}\n"
    bot.send_message(c.message.chat.id, txt)


@bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
def cl_stats(c):
    if c.from_user.id != ADMIN_ID: return
    stats(c.message)


@bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
def cl_broadcast(c):
    if c.from_user.id != ADMIN_ID: return
    msg = bot.send_message(c.message.chat.id, "📢 Send broadcast message:")
    bot.register_next_step_handler(msg, do_broadcast)


def do_broadcast(msg):
    if msg.from_user.id != ADMIN_ID: return
    for u in users_collection.find():
        try: bot.send_message(u['user_id'], msg.text)
        except: pass
    bot.send_message(ADMIN_ID, "✔ Broadcast sent to all users!")


# ---------------- IMAGE PLACEHOLDER ----------------
@bot.message_handler(func=lambda m: m.text == "Convert Image")
def convert_image(msg):
    bot.send_message(msg.chat.id,
                     "📤 Send any image\n"
                     "🛠 Tools coming soon!")


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
    time.sleep(2)
    bot.set_webhook(url=f"{BASE_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
