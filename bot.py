import telebot
import os
import time
from telebot import types
from pymongo import MongoClient
from flask import Flask, request

# ========= ENV CONFIG =========
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")
BASE_URL = os.getenv("BASE_URL")

# ========= DATABASE =========
client = MongoClient(MONGO_URI)
db = client["any2anybot"]
users_collection = db["users"]
payment_links = db["payment_links"]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


# ========= USER REGISTER =========
def register(uid):
    if not users_collection.find_one({"user_id": uid}):
        users_collection.insert_one({"user_id": uid, "vip": False})


# ========= ADMIN PANEL =========
def admin_panel(chat_id):
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔗 Manage Links", callback_data="admin_links"),
        types.InlineKeyboardButton("👥 Users", callback_data="admin_users")
    )
    kb.row(
        types.InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        types.InlineKeyboardButton("❓ Help", callback_data="admin_help")
    )
    kb.row(types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"))

    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})

    bot.send_message(
        chat_id,
        f"👑 <b>AskEdge Admin Panel</b>\n\n"
        f"👥 Total Users: {total}\n"
        f"💎 VIP Users: {vip}",
        reply_markup=kb
    )


@bot.message_handler(commands=['admin'])
def open_admin(msg):
    if msg.from_user.id == ADMIN_ID:
        admin_panel(msg.chat.id)


# ========= ADMIN CALLBACK FIRST (priority) =========
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin"))
def admin_callback(c):
    if c.from_user.id != ADMIN_ID:
        return

    if c.data == "admin_links":
        bot.send_message(c.message.chat.id,
            "Add Links:\n"
            "/addlink 30 <URL>\n/addlink 59 <URL>\n\n"
            "Show Links:\n/links"
        )

    elif c.data == "admin_users":
        text = "👥 All Users:\n\n"
        for u in users_collection.find():
            text += f"{u['user_id']} - {'VIP' if u.get('vip') else 'FREE'}\n"
        bot.send_message(c.message.chat.id, text)

    elif c.data == "admin_stats":
        stats(c.message)

    elif c.data == "admin_help":
        helpadmin(c.message)

    elif c.data == "admin_broadcast":
        ask = bot.send_message(c.message.chat.id, "📢 Enter message:")
        bot.register_next_step_handler(ask, do_broadcast)

    bot.answer_callback_query(c.id)


# ========= VIP CALLBACK SECOND =========
@bot.callback_query_handler(func=lambda c: c.data in ["V30", "V59"])
def pick_plan(c):
    uid = c.from_user.id
    amount = 30 if c.data == "V30" else 59

    link = payment_links.find_one({"status": "available", "amount": amount})
    
    if not link:
        bot.send_message(uid, "❌ No links available. Contact admin.")
        bot.send_message(ADMIN_ID, "⚠ Add more links!")
        return

    payment_links.update_one({"id": link["id"]},
                             {"$set": {"status": "assigned", "assigned_to": uid}})

    bot.send_message(
        uid,
        f"💳 Pay ₹{amount} here:\n{link['url']}\n\n"
        "📸 Send screenshot after payment!"
    )
    bot.send_message(
        ADMIN_ID,
        f"Payment Request\nUser: {uid}\nID: {link['id']}\n"
        f"/paid_{link['id']}_{uid}\n/unpaid_{link['id']}"
    )


# ========= ADMIN COMMANDS =========
@bot.message_handler(commands=['helpadmin'])
def helpadmin(msg):
    if msg.from_user.id != ADMIN_ID: return

    bot.send_message(msg.chat.id,
        "👑 Admin Commands\n\n"
        "/addlink 30 <url>\n/addlink 59 <url>\n"
        "/links\n/users\n/stats\n/revenue\n"
        "/admin\n"
    )


@bot.message_handler(commands=['addlink'])
def addlink(msg):
    if msg.from_user.id != ADMIN_ID: return
    try:
        _, amt, url = msg.text.split(" ", 2)
        amt = int(amt)
        nid = payment_links.count_documents({}) + 1

        payment_links.insert_one({
            "id": nid, "amount": amt, "url": url, "status": "available"
        })
        bot.send_message(ADMIN_ID, f"✔ Link Added (ID: {nid})")

    except Exception as e:
        bot.send_message(ADMIN_ID, f"Error: {e}\nFormat: /addlink 30 <url>")


@bot.message_handler(commands=['links'])
def links(msg):
    if msg.from_user.id != ADMIN_ID: return
    txt = "🔗 Links:\n\n"
    for l in payment_links.find():
        txt += f"ID:{l['id']} ₹{l['amount']} - {l['status']}\n"
    bot.send_message(ADMIN_ID, txt)


@bot.message_handler(commands=['revenue'])
def revenue(msg):
    if msg.from_user.id != ADMIN_ID: return
    paid = users_collection.count_documents({"vip": True})
    tot = sum(int(p["amount"]) for p in payment_links.find({"status": "paid"}))
    bot.send_message(ADMIN_ID, f"VIP: {paid}\nRevenue: ₹{tot}")


@bot.message_handler(commands=['users'])
def users(msg):
    if msg.from_user.id != ADMIN_ID: return
    txt = "👥 Users:\n"
    for u in users_collection.find():
        txt += f"{u['user_id']} - {'VIP' if u.get('vip') else 'FREE'}\n"
    bot.send_message(ADMIN_ID, txt)


@bot.message_handler(commands=['paid'])
def paid(msg):
    if msg.from_user.id != ADMIN_ID: return
    _, lid, uid = msg.text.split("_")
    payment_links.update_one({"id": int(lid)}, {"$set": {"status": "paid"}})
    users_collection.update_one({"user_id": int(uid)}, {"$set": {"vip": True}})
    bot.send_message(int(uid), "🎉 VIP Activated!")
    bot.send_message(ADMIN_ID, "✔ Marked Paid")


@bot.message_handler(commands=['unpaid'])
def unpaid(msg):
    if msg.from_user.id != ADMIN_ID: return
    _, lid = msg.text.split("_")
    payment_links.update_one({"id": int(lid)},
                             {"$set": {"status": "available"}})
    bot.send_message(ADMIN_ID, "🔁 Reset Done")


def do_broadcast(msg):
    if msg.from_user.id != ADMIN_ID: return
    c = 0
    for u in users_collection.find():
        try:
            bot.send_message(u["user_id"], msg.text)
            c += 1
        except:
            pass
    bot.send_message(ADMIN_ID, f"Sent to {c} users ✔")


# ========= USER MENU =========
@bot.message_handler(commands=['start'])
def start(msg):
    register(msg.from_user.id)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Convert Image", "💎 VIP Plans")
    bot.send_message(msg.chat.id, "🔥 Converter Bot Ready!", reply_markup=kb)


# ========= BASIC =========
@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID: return
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})
    bot.send_message(ADMIN_ID, f"Total Users: {total}\nVIP: {vip}")


@bot.message_handler(func=lambda m: m.text == "💎 VIP Plans")
def vipplans(msg):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("₹30/30 Days", callback_data="V30"))
    kb.add(types.InlineKeyboardButton("₹59/Lifetime", callback_data="V59"))
    bot.send_message(msg.chat.id, "Select Plan:", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == "Convert Image")
def convert(msg):
    bot.send_message(msg.chat.id, "📤 Send image (coming soon)")


# ========= WEBHOOK =========
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates(
        [telebot.types.Update.de_json(request.data.decode())]
    )
    return "OK"


if __name__ == '__main__':
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(
        url=f"{BASE_URL}/{TOKEN}",
        allowed_updates=["message", "callback_query"]
    )
    app.run(host="0.0.0.0", port=8080)
