import telebot
import os
import time
from telebot import types
from pymongo import MongoClient
from flask import Flask, request

# -------------- ENV CONFIG --------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")
BASE_URL = os.getenv("BASE_URL")

# -------------- DATABASE SETUP --------------
client = MongoClient(MONGO_URI)
db = client["any2anybot"]
users_collection = db["users"]
payment_links = db["payment_links"]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# -------------- USER REGISTER --------------
def get_user(uid):
    u = users_collection.find_one({"user_id": uid})
    if not u:
        users_collection.insert_one({"user_id": uid, "vip": False})
        return get_user(uid)
    return u

# -------------- ADMIN PANEL UI --------------
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
        types.InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
    )
    kb.add(
        types.InlineKeyboardButton("❓ Help", callback_data="admin_help")
    )

    bot.send_message(
        chat_id,
        f"👑 <b>AskEdge Admin Panel</b>\n\n"
        f"👥 Users: {total}\n"
        f"💎 VIP: {vip}\n"
        f"⏳ Pending Payments: {pending}",
        reply_markup=kb
    )

@bot.message_handler(commands=['admin'])
def open_admin(msg):
    if msg.from_user.id != ADMIN_ID: return
    admin_panel(msg.chat.id)

# -------------- HELP FOR ADMIN --------------
@bot.message_handler(commands=['helpadmin'])
def admin_help(msg):
    if msg.from_user.id != ADMIN_ID: 
        return
    
    help_text = (
        "👑 <b>Admin Command Guide</b>\n\n"
        "📌 <b>VIP & Payment Controls</b>\n"
        "/addlink 30 <URL>\n/addlink 59 <URL>\n"
        "/links\n"
        "/paid_id_userid\n"
        "/unpaid_id\n\n"
        
        "👥 <b>User Management</b>\n"
        "/users\n"
        
        "📊 <b>Stats & System</b>\n"
        "/stats\n"
        
        "📢 <b>Broadcast</b>\n"
        "/broadcast\n\n"
        
        "⚙ <b>Admin Panel UI</b>\n"
        "/admin\n"
    )
    
    bot.send_message(msg.chat.id, help_text)

@bot.callback_query_handler(func=lambda c: c.data == "admin_help")
def cl_help(c):
    if c.from_user.id != ADMIN_ID: return
    admin_help(c.message)

# -------------- BASIC USER COMMANDS --------------
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

# -------------- USER MAIN MENU --------------
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

# -------------- VIP PLANS & PAYMENT LINKS --------------
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
        {"$set": {"status": "assigned", "assigned_to": uid}}
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("V"))
def pick_plan(c):
    uid = c.from_user.id
    amount = 30 if c.data == "V30" else 59

    link = get_next_link(amount)

    if not link:
        bot.send_message(uid, "❌ All payment links used. Admin adding new links!")
        bot.send_message(ADMIN_ID, "⚠ Add more payment links")
        return

    assign_link(link["id"], uid)

    bot.send_message(
        uid,
        f"💳 Pay ₹{amount} 👇\n{link['url']}\n\n"
        "📸 Send screenshot after payment!"
    )

    bot.send_message(
        ADMIN_ID,
        f"🆕 Payment Request\nUser: {uid}\nLinkID: {link['id']}\n💴 ₹{amount}\n\n"
        f"/paid_{link['id']}_{uid}\n"
        f"/unpaid_{link['id']}"
    )

# -------------- ADMIN PAYMENT CONTROL --------------
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
            "status": "available"
        })

        bot.send_message(ADMIN_ID, f"✔ Link Added!\nID: {new_id}")
    except:
        bot.send_message(ADMIN_ID, "❌ Format:\n/addlink 30 <URL>")

@bot.message_handler(commands=['links'])
def links(msg):
    if msg.from_user.id != ADMIN_ID: return

    data = payment_links.find()
    txt = "🔗 Payment Links:\n\n"
    for l in data:
        txt += f"ID: {l['id']} | ₹{l['amount']} | Status: {l['status']}\n"
    bot.send_message(ADMIN_ID, txt or "No Links")

@bot.message_handler(commands=['users'])
def users(msg):
    if msg.from_user.id != ADMIN_ID: return

    users = users_collection.find()
    txt = "👥 Users:\n"
    for u in users:
        txt += f"{u['user_id']} - {'VIP' if u.get('vip') else 'FREE'}\n"
    bot.send_message(ADMIN_ID, txt)

@bot.message_handler(commands=['paid'])
def paid(msg):
    if msg.from_user.id != ADMIN_ID: return
    _, lid, uid = msg.text.split("_")
    uid = int(uid)
    lid = int(lid)

    users_collection.update_one({"user_id": uid}, {"$set": {"vip": True}})
    payment_links.update_one({"id": lid},
                             {"$set": {"status": "paid"}})

    bot.send_message(uid, "🎉 VIP Activated!")
    bot.send_message(ADMIN_ID, "✔ Marked Paid")

@bot.message_handler(commands=['unpaid'])
def unpaid(msg):
    if msg.from_user.id != ADMIN_ID: return

    _, lid = msg.text.split("_")
    lid = int(lid)

    payment_links.update_one({"id": lid},
                             {"$set": {"status": "available"}})
    bot.send_message(ADMIN_ID, "🔁 Link Re-Activated")

# -------------- ADMIN BUTTON CALLBACK --------------
@bot.callback_query_handler(func=lambda c: c.data == "admin_links")
def cl_links(c):
    if c.from_user.id != ADMIN_ID: return
    bot.send_message(c.message.chat.id, "/addlink 30 <URL>\n/addlink 59 <URL>\n/links")

@bot.callback_query_handler(func=lambda c: c.data == "admin_users")
def cl_users(c):
    users(c.message)

@bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
def cl_stats(c):
    stats(c.message)

@bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
def cl_broadcast(c):
    if c.from_user.id != ADMIN_ID: return
    r = bot.send_message(c.message.chat.id, "Send broadcast message:")
    bot.register_next_step_handler(r, do_broadcast)

def do_broadcast(msg):
    if msg.from_user.id != ADMIN_ID: return
    for u in users_collection.find():
        try: bot.send_message(u['user_id'], msg.text)
        except: pass
    bot.send_message(ADMIN_ID, "Broadcast Sent ✔")

# -------------- IMAGE MENU --------------
@bot.message_handler(func=lambda m: m.text == "Convert Image")
def img(msg):
    bot.send_message(msg.chat.id,
                     "📤 Send any image\n(Processing Engine Coming Soon)")

# -------------- WEBHOOK SERVER --------------
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
