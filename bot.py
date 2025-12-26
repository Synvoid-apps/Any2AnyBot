import telebot, os, time, qrcode, ffmpeg
from PIL import Image
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, WEBHOOK_URL, ADMIN_ID, DAILY_LIMIT
from db import *
import shutil

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
app = Flask(__name__)

QR_FOLDER = "qr"
os.makedirs(QR_FOLDER, exist_ok=True)

FULL_URL = f"{WEBHOOK_URL}/{BOT_TOKEN}"

# ---------- MENUS ----------
def home_menu():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🔁 Convert", callback_data="convert"),
        InlineKeyboardButton("📦 My Files", callback_data="files"),
    )
    kb.add(
        InlineKeyboardButton("📊 Usage", callback_data="usage"),
        InlineKeyboardButton("💎 VIP Plans", callback_data="vip"),
    )
    kb.add(InlineKeyboardButton("ℹ Help", callback_data="help"))
    return kb

@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id
    get_user(uid)
    bot.reply_to(msg, "👋 Welcome to Any2Any Converter!\nSend a file 👇",
                 reply_markup=home_menu())


# ---------- ADMIN PANEL ----------
@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID: return
    u, vip, conv = get_stats()
    bot.reply_to(msg,
        f"📈 Any2Any Business Dashboard\n\n"
        f"👥 Total Users: {u}\n"
        f"💎 VIP Users: {vip}\n"
        f"🔁 Converted Files: {conv}\n"
        f"⚡ Managed by AskEdge Labs")


@bot.message_handler(commands=['vip'])
def vip_cmd(msg):
    if msg.from_user.id != ADMIN_ID: return
    try:
        uid = int(msg.text.split()[1])
        set_vip(uid)
        bot.send_message(uid, "💎 VIP Activated!\nUnlimited access enabled 🚀")
        bot.reply_to(msg, f"Done! VIP for {uid}")
    except:
        bot.reply_to(msg, "Usage: /vip USER_ID")


# ---------- VIP MENU ----------
@bot.callback_query_handler(func=lambda c: c.data == "vip")
def vip_menu(call):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("₹30 Monthly 🔥", callback_data="pay30"),
        InlineKeyboardButton("₹59 Lifetime 💎", callback_data="pay59")
    )
    bot.send_message(call.message.chat.id,
        "💎 VIP Plans — Choose one 👇\nPay → Send Screenshot → Admin approves",
        reply_markup=kb)


def generate_order_qr(amount, prefix):
    order = f"{prefix}-{int(time.time())}"
    upi = f"upi://pay?pa={UPI_ID}&pn=AskEdge+Labs&am={amount}&cu=INR&tn={order}"
    file = f"{QR_FOLDER}/{order}.png"
    qrcode.make(upi).save(file)
    return order, file

@bot.callback_query_handler(func=lambda c: c.data == "pay30")
def pay30(call):
    uid = call.message.chat.id
    order, qr = generate_order_qr(30, "M")
    bot.send_photo(uid, open(qr,"rb"),
        caption=f"🔁 Monthly VIP — ₹30\n📌 Order ID: `{order}`\nScan & Pay → Screenshot bhejo!")
    bot.send_message(ADMIN_ID, f"📥 New Monthly Order: {order} by {uid}")

@bot.callback_query_handler(func=lambda c: c.data == "pay59")
def pay59(call):
    uid = call.message.chat.id
    order, qr = generate_order_qr(59, "L")
    bot.send_photo(uid, open(qr,"rb"),
        caption=f"💎 Lifetime VIP — ₹59\n📌 Order ID: `{order}`\nScan & Pay → Screenshot bhejo!")
    bot.send_message(ADMIN_ID, f"📥 New Lifetime Order: {order} by {uid}")


# ---------- PAYMENT SCREENSHOT ----------
@bot.message_handler(content_types=['photo'])
def ss(msg):
    uid = msg.from_user.id
    if uid != ADMIN_ID:
        bot.forward_message(ADMIN_ID, uid, msg.message_id)
        bot.send_message(uid, "📨 Screenshot sent! Admin verify karega 🙂")
    else:
        bot.send_message(uid, "✔ Screenshot received!")


# ---------- USAGE ----------
@bot.callback_query_handler(func=lambda c: c.data == "usage")
def usage(call):
    uid = call.message.chat.id
    u = get_user(uid)
    bot.send_message(uid,
        f"📊 Today: {u['today_count']}/{DAILY_LIMIT}\n"
        f"💎 VIP: {'Yes' if u['is_vip'] else 'No'}")


# ---------- HELP ----------
@bot.callback_query_handler(func=lambda c: c.data == "help")
def help(call):
    bot.send_message(call.message.chat.id,
        "📌 Just send Image / Video & choose conversion!")


# ---------- Cloud Files ----------
@bot.callback_query_handler(func=lambda c: c.data == "files")
def files_menu(call):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🖼 Images", callback_data="fi_image"),
        InlineKeyboardButton("🎞 Videos", callback_data="fi_video"),
        InlineKeyboardButton("🎧 Audio", callback_data="fi_audio")
    )
    bot.send_message(call.message.chat.id,"📂 Select category",reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("fi_"))
def list_my_files(call):
    uid = call.message.chat.id
    t = call.data[3:]
    arr = list_files(uid, t)
    kb = InlineKeyboardMarkup()
    for f in arr:
        kb.add(InlineKeyboardButton(f["name"], callback_data=f"dl_{f['file_id']}"))
    bot.send_message(uid,f"📂 Your {t}:",reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("dl_"))
def dl(call):
    bot.send_document(call.message.chat.id, call.data[3:], reply_markup=home_menu())


# ---------- IMAGE ----------
@bot.message_handler(content_types=['photo'])
def image_handler(msg):
    uid = msg.from_user.id
    if not usage_allowed(uid):
        return bot.reply_to(msg, "⛔ Limit reached! Buy VIP 💎")
    fid = msg.photo[-1].file_id
    file = bot.get_file(fid)
    data = bot.download_file(file.file_path)
    i = f"tmp_{uid}.jpg"
    open(i,"wb").write(data)
    out = f"cnv_{uid}.png"
    Image.open(i).convert("RGBA").save(out)

    send = bot.send_document(uid, open(out,"rb"),reply_markup=home_menu())
    save_file(uid, send.document.file_id, out, "image")
    update_usage(uid)
    os.remove(i); os.remove(out)


# ---------- VIDEO ----------
@bot.message_handler(content_types=['video'])
def vid(msg):
    uid = msg.from_user.id
    if not usage_allowed(uid):
        return bot.reply_to(msg, "⛔ Limit reached! Buy VIP 💎")
    fid = msg.video.file_id
    file = bot.get_file(fid)
    data = bot.download_file(file.file_path)
    i=f"v{uid}.mp4"; o=f"v{uid}.mp3"
    open(i,"wb").write(data)
    ffmpeg.input(i).output(o).run(overwrite_output=True)
    send=bot.send_document(uid,open(o,"rb"),reply_markup=home_menu())
    save_file(uid,send.document.file_id,o,"audio")
    update_usage(uid)
    os.remove(i); os.remove(o)


# ---------- WEBHOOK ----------
bot.remove_webhook()
bot.set_webhook(url=FULL_URL)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def wh():
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return "OK",200

@app.route("/")
def home():
    return "Any2Any Bot Live 🔥"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)))
