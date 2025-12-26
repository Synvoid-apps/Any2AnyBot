import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from dotenv import load_dotenv
from flask import Flask, request
from PIL import Image
import ffmpeg
from db import update_usage, usage_allowed, get_user, save_file, list_files, set_vip

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
FULL_URL = f"{WEBHOOK_URL}/{TOKEN}"
ADMIN_ID = 6141075929  # <--- You are Admin 💎🔥

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)

user_files = {}

# ---- HOME INLINE MENU ----
def home_menu():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🔁 Convert File", callback_data="convert_menu"),
        InlineKeyboardButton("📦 My Files", callback_data="my_files")
    )
    kb.add(
        InlineKeyboardButton("📊 Usage", callback_data="show_usage"),
        InlineKeyboardButton("💎 VIP", callback_data="vip_info")
    )
    kb.add(InlineKeyboardButton("ℹ Help", callback_data="help_menu"))
    return kb


@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id
    get_user(uid)
    bot.reply_to(msg,
        "👋 Welcome to Any2Any Converter WebApp 🌍\n"
        "Send file or choose below 👇",
        reply_markup=home_menu()
    )


# ---- ADMIN COMMAND FOR VIP ----
@bot.message_handler(commands=['vip'])
def make_vip(msg):
    if msg.from_user.id != ADMIN_ID:
        return bot.reply_to(msg, "❌ Not authorized")
    try:
        uid = int(msg.text.split()[1])
        set_vip(uid, True)
        bot.reply_to(msg, f"💎 User {uid} is now VIP!")
    except:
        bot.reply_to(msg, "Usage: /vip user_id")


# ---- MENU ACTIONS ----
@bot.callback_query_handler(func=lambda c: c.data == "convert_menu")
def convert_menu(call):
    bot.send_message(call.message.chat.id, "📥 Send any file!")


@bot.callback_query_handler(func=lambda c: c.data == "help_menu")
def help_menu(call):
    bot.send_message(call.message.chat.id,
        "🛠 Supported:\n• PNG/JPG\n• MP3/MP4\nCloud Storage enabled\nJust Send 😊")


@bot.callback_query_handler(func=lambda c:c.data=="show_usage")
def show_usage(call):
    user = get_user(call.message.chat.id)
    bot.send_message(call.message.chat.id,
        f"📊 Used Today: {user['today_count']}/10\n"
        f"VIP: {'Yes 💎' if user['is_vip'] else 'No ❌'}"
    )


# ---- VIP INFO ----
@bot.callback_query_handler(func=lambda c: c.data == "vip_info")
def vip_info(call):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("₹30/Month 🔥", callback_data="pay_month"),
        InlineKeyboardButton("₹59/Lifetime 💎", callback_data="pay_life")
    )
    bot.send_message(call.message.chat.id,
        "💎 VIP Plans:\nChoose one for unlimited power ⚡",
        reply_markup=kb)

# Payment Dummy
@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_"))
def vip_pay(call):
    bot.send_message(call.message.chat.id,
        "💳 Payment will be added soon!\nContact Admin: @AskEdgeLabs")


# ---- MY FILES MENU ----
@bot.callback_query_handler(func=lambda c: c.data == "my_files")
def my_files(call):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🖼 Images", callback_data="cat_image"),
        InlineKeyboardButton("🎞 Videos", callback_data="cat_video"),
        InlineKeyboardButton("🎧 Audio", callback_data="cat_audio")
    )
    bot.send_message(call.message.chat.id,
        "📦 Media Library ↓",
        reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))
def show_category(call):
    uid = call.message.chat.id
    ftype = call.data[4:]

    items = list_files(uid, ftype)

    if not items:
        return bot.send_message(uid, f"❌ No {ftype}s here 😅")

    kb = InlineKeyboardMarkup()
    for i, f in enumerate(items):
        kb.add(InlineKeyboardButton(f["name"], callback_data=f"dl_{f['file_id']}"))

    bot.send_message(uid, f"📂 Your {ftype.capitalize()} Files:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("dl_"))
def dl_file(call):
    file_id = call.data[3:]
    bot.send_document(call.message.chat.id, file_id, caption="📥 Download from Cloud!")


# ---- IMAGE ----
@bot.message_handler(content_types=['photo'])
def image_handler(msg):
    uid = msg.from_user.id
    if not usage_allowed(uid):
        return bot.reply_to(msg,"❌ Daily limit reached!")

    user_files[uid] = msg.photo[-1].file_id
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("PNG", callback_data="img_png"),
        InlineKeyboardButton("JPG", callback_data="img_jpg")
    )
    bot.reply_to(msg,"Format:",reply_markup=kb)


@bot.callback_query_handler(func=lambda c:c.data.startswith("img_"))
def convert_img(call):
    uid = call.message.chat.id
    fmt = call.data[4:]
    bot.send_message(uid,"⏳ Processing…")

    f = bot.get_file(user_files[uid])
    data = bot.download_file(f.file_path)

    inp=f"img_{uid}.jpg"
    out=f"file_{uid}.{fmt}"
    open(inp,"wb").write(data)

    Image.open(inp).convert("RGB").save(out)

    sent = bot.send_document(uid, open(out,"rb"), reply_markup=home_menu())
    save_file(uid, sent.document.file_id, out, "image")
    update_usage(uid)

    os.remove(inp); os.remove(out)


# ---- VIDEO ----
@bot.message_handler(content_types=['video'])
def vid(msg):
    uid = msg.from_user.id
    user_files[uid] = msg.video.file_id

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("MP3", callback_data="v_mp3"),
        InlineKeyboardButton("MP4", callback_data="v_mp4")
    )
    bot.reply_to(msg,"Convert to:",reply_markup=kb)


@bot.callback_query_handler(func=lambda c:c.data.startswith("v_"))
def video_convert(call):
    uid = call.message.chat.id
    fmt = call.data[2:]
    bot.send_message(uid,"🎬 Working…")

    f = bot.get_file(user_files[uid])
    data = bot.download_file(f.file_path)

    inp=f"vid_{uid}.mp4"
    out=f"file_{uid}.{ 'mp3' if fmt=='mp3' else 'mp4'}"
    open(inp,"wb").write(data)

    if fmt=="mp3":
        ffmpeg.input(inp).output(out, acodec="mp3").run(overwrite_output=True)
        ftype="audio"
    else:
        ffmpeg.input(inp).output(out).run(overwrite_output=True)
        ftype="video"

    sent = bot.send_document(uid, open(out,"rb"), reply_markup=home_menu())
    save_file(uid, sent.document.file_id, out, ftype)
    update_usage(uid)

    os.remove(inp); os.remove(out)


# ---- WEBHOOK SERVER ----
bot.remove_webhook()
bot.set_webhook(url=FULL_URL)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK",200

@app.route("/")
def home():
    return "Bot is RUNNING! 🚀",200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8080)))
