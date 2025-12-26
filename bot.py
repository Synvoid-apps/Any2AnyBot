import telebot
import os
import time
from telebot import types
from pymongo import MongoClient
from flask import Flask, request

# ================= ENV CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")
BASE_URL = os.getenv("BASE_URL")

# ================= DATABASE ====================
client = MongoClient(MONGO_URI)
db = client["any2anybot"]
users_collection = db["users"]
payment_links = db["payment_links"]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ================= USER REGISTER ===============
def get_user(uid):
    u = users_collection.find_one({"user_id": uid})
    if not u:
        users_collection.insert_one({"user_id": uid, "vip": False})
        return get_user(uid)
    return u

# ================= ADMIN PANEL =================
def admin_panel(chat_id):
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})
    pending = payment_links.count_documents({"status": "assigned"})

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🔗 Manage Links", callback_data="admin_links"),
        types.InlineKeyboardButton("👥 Users", callback_data="admin_users"),
    )
    kb.add(
        types.InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
    )
    kb.add(types.InlineKeyboardButton("❓ Help", callback_data="admin_help"))

    bot.send_message(
        chat_id,
        f"👑 <b>AskEdge Admin Panel</b>\n\n"
        f"👥 Users: {total}\n"
        f"💎 VIP Users: {vip}\n"
        f"⏳ Pending Payments: {pending}",
        reply_markup=kb
    )

@bot.message_handler(commands=['admin'])
def open_admin(msg):
    if msg.from_user.id == ADMIN_ID:
        admin_panel(msg.chat.id)

# ================= ADMIN HELP ==================
@bot.message_handler(commands=['helpadmin'])
def admin_help(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    
    bot.send_message(
        msg.chat.id,
        "👑 <b>Admin Commands</b>\n\n"
        "💰 VIP & Payments:\n"
        "/addlink 30 <URL>\n/addlink 59 <URL>\n"
        "/links\n"
        "/paid_id_userid\n/unpaid_id\n\n"
        "📊 Reports:\n"
        "/stats\n/revenue\n\n"
        "👥 Users:\n"
        "/users\n\n"
        "⚙ Panel:\n"
        "/admin\n"
    )

# ================= VIP CALLBACK =================
@bot.callback_query_handler(func=lambda c: c.data in ["V30", "V59"])
def pick_plan(c):
    uid = c.from_user.id
    amount = 30 if c.data == "V30" else 59

    link = payment_links.find_one({"status": "available", "amount": amount})
    if not link:
        bot.send_message(uid, "❌ No payment links available! Contact Admin")
        bot.send_message(ADMIN_ID, "⚠ Add more links ASAP")
        return

    payment_links.update_one({"id": link["id"]},
                             {"$set": {"status": "assigned", "assigned_to": uid}})

    bot.send_message(
        uid,
        f"💳 Pay ₹{amount} using link 👇\n{link['url']}\n\n"
        "📸 Send screenshot after payment!"
    )

    bot.send_message(
        ADMIN_ID,
        f"🆕 Payment Request\nUser: {uid}\nLinkID: {link['id']}\n₹{amount}\n\n"
        f"/paid_{link['id']}_{uid}\n/unpaid_{link['id']}"
    )


# ================= ADMIN CALLBACKS ==============
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin"))
def admin_buttons(c):
    if c.from_user.id != ADMIN_ID:
        return

    if c.data == "admin_links":
        bot.send_message(c.message.chat.id,
            "/addlink 30 <URL>\n/addlink 59 <URL>\n"
            "/links\n/paid_id_userid\n/unpaid_id"
        )

    elif c.data == "admin_users":
        txt = "👥 Users:\n\n"
        for u in users_collection.find():
            txt += f"{u['user_id']} - {'VIP' if u.get('vip') else 'FREE'}\n"
        bot.send_message(c.message.chat.id, txt)

    elif c.data == "admin_stats":
        stats(c.message)

    elif c.data == "admin_help":
        admin_help(c.message)

    elif c.data == "admin_broadcast":
        ask = bot.send_message(c.message.chat.id, "📢 Send message:")
        bot.register_next_step_handler(ask, do_broadcast)

    bot.answer_callback_query(c.id)


# ================= REVENUE TRACKING =============
@bot.message_handler(commands=['revenue'])
def revenue(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    
    paid_users = users_collection.count_documents({"vip": True})
    total = 0
    for p in payment_links.find({"status": "paid"}):
        total += int(p["amount"])

    bot.send_message(
        ADMIN_ID,
        f"💰 <b>Total Revenue Report</b>\n\n"
        f"👑 VIP Activated: {paid_users}\n"
        f"₹ Earnings: ₹{total}"
    )


# ================= MAIN USER ====================
@bot.message_handler(commands=['start'])
def start(msg):
    get_user(msg.from_user.id)
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Convert Image", "💎 VIP Plans")
    bot.send_message(msg.chat.id, 
                     "<b>🔥 Any2Any Converter</b>\nConvert Anything → Anything",
                     reply_markup=kb)

# ================= BASIC FEATURES ===============
@bot.message_handler(commands=['id'])
def user_id(msg):
    bot.send_message(msg.chat.id, 
                     f"🆔 Your ID:\n<code>{msg.from_user.id}</code>")

@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})
    bot.send_message(ADMIN_ID, 
                     f"📊 Stats\nUsers: {total}\nVIP: {vip}")

@bot.message_handler(commands=['addlink'])
def add_link(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    
    try:
        _, amount, url = msg.text.split(" ", 2)
        amount = int(amount)
        new_id = payment_links.count_documents({}) + 1
        payment_links.insert_one(
            {"id": new_id, "amount": amount, "url": url, "status": "available"}
        )
        bot.send_message(ADMIN_ID, f"Link Added ✔ ID: {new_id}")
    except:
        bot.send_message(ADMIN_ID, "❌ Format\n/addlink 30 <URL>")

@bot.message_handler(commands=['links'])
def links(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    data = payment_links.find()
    txt = "🔗 Links:\n\n"
    for l in data:
        txt += f"ID:{l['id']} | ₹{l['amount']} | {l['status']}\n"
    bot.send_message(ADMIN_ID, txt or "No Links")

@bot.message_handler(commands=['users'])
def users(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    txt = "👥 Users:\n\n"
    for u in users_collection.find():
        txt += f"{u['user_id']} - {'VIP' if u.get('vip') else 'FREE'}\n"
    bot.send_message(ADMIN_ID, txt)

@bot.message_handler(commands=['paid'])
def paid(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    _, lid, uid = msg.text.split("_")
    lid = int(lid); uid = int(uid)
    users_collection.update_one({"user_id": uid}, {"$set": {"vip": True}})
    payment_links.update_one({"id": lid}, {"$set": {"status": "paid"}})
    bot.send_message(uid, "🎉 VIP Activated!")
    bot.send_message(ADMIN_ID, "✔ Payment accepted")

@bot.message_handler(commands=['unpaid'])
def unpaid(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    _, lid = msg.text.split("_")
    lid = int(lid)
    payment_links.update_one({"id": lid},
                             {"$set": {"status": "available", "assigned_to": None}})
    bot.send_message(ADMIN_ID, "🔁 Link Reset")


# ================= BROADCAST ====================
def do_broadcast(msg):
    for u in users_collection.find():
        try: bot.send_message(u['user_id'], msg.text)
        except: pass
    bot.send_message(ADMIN_ID, "✔ Broadcast sent")


# ================= USER IMAGE ===================
@bot.message_handler(func=lambda m: m.text == "Convert Image")
def img(msg):
    bot.send_message(msg.chat.id, 
                     "📤 Send image (Tool coming soon)")

# ================= WEBHOOK ======================
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.data.decode())])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(2)
    bot.set_webhook(
        url=f"{BASE_URL}/{TOKEN}",
        allowed_updates=["message", "callback_query"]
    )
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
