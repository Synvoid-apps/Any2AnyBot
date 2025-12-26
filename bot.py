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


# ========= ADMIN COMMAND MENU =========
def admin_menu(chat_id):
    bot.send_message(chat_id,
        "👑 ADMIN MENU\n\n"
        "/addlink 30 <URL>\n"
        "/addlink 59 <URL>\n"
        "/links - Show All Payment Links\n"
        "/users - Show All Users\n"
        "/stats - Basic Stats\n"
        "/revenue - Total Sales\n"
        "/broadcast - Send Msg to All\n"
        "/adminhelp - Help\n"
    )


@bot.message_handler(commands=['admin'])
def admin(msg):
    if msg.from_user.id != ADMIN_ID:
        bot.send_message(msg.chat.id, "⛔ Access Denied!")
        return
    admin_menu(msg.chat.id)


# ========= ADMIN Commands =========
@bot.message_handler(commands=['adminhelp'])
def adminhelp(msg):
    if msg.from_user.id != ADMIN_ID: return
    admin_menu(msg.chat.id)


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

    except:
        bot.send_message(ADMIN_ID, "❌ Format: /addlink 30 URL")


@bot.message_handler(commands=['links'])
def links(msg):
    if msg.from_user.id != ADMIN_ID: return
    txt = "🔗 PAYMENT LINKS:\n\n"
    for l in payment_links.find():
        txt += f"ID:{l['id']} ₹{l['amount']} - {l['status']}\n"
    bot.send_message(ADMIN_ID, txt)


@bot.message_handler(commands=['users'])
def users(msg):
    if msg.from_user.id != ADMIN_ID: return
    txt = "👥 USERS:\n"
    for u in users_collection.find():
        txt += f"{u['user_id']} - {'VIP' if u.get('vip') else 'FREE'}\n"
    bot.send_message(ADMIN_ID, txt)


@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID: return
    total = users_collection.count_documents({})
    vip = users_collection.count_documents({"vip": True})
    bot.send_message(ADMIN_ID, f"Total: {total}\nVIP: {vip}")


@bot.message_handler(commands=['revenue'])
def revenue(msg):
    if msg.from_user.id != ADMIN_ID: return
    paid = users_collection.count_documents({"vip": True})
    tot = sum(int(p["amount"]) for p in payment_links.find({"status": "paid"}))
    bot.send_message(ADMIN_ID, f"VIP Users: {paid}\nRevenue: ₹{tot}")


@bot.message_handler(commands=['broadcast'])
def ask_broad(msg):
    if msg.from_user.id != ADMIN_ID: return
    ask = bot.send_message(ADMIN_ID, "Enter Broadcast:")
    bot.register_next_step_handler(ask, do_broadcast)


def do_broadcast(msg):
    if msg.from_user.id != ADMIN_ID: return
    c = 0
    for u in users_collection.find():
        try:
            bot.send_message(u["user_id"], msg.text)
            c += 1
        except:
            pass
    bot.send_message(ADMIN_ID, f"Sent: {c}")


# ========= VIP Feature (Still Working) =========
@bot.message_handler(func=lambda m: m.text == "💎 VIP Plans")
def vipplans(msg):
    if msg.from_user.id != ADMIN_ID:
        bot.send_message(msg.chat.id, "Coming soon… 🔥")


@bot.message_handler(commands=['start'])
def start(msg):
    register(msg.from_user.id)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Convert Image", "💎 VIP Plans")
    bot.send_message(msg.chat.id, "🔥 Ready!", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == "Convert Image")
def convert(msg):
    bot.send_message(msg.chat.id, "📤 Send Image (Next Update)")


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
        allowed_updates=["message"]
    )
    app.run(host="0.0.0.0", port=8080)
