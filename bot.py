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
ADMIN_ID = 6141075929  # YOU ARE ADMIN 💎

UPI_ID = "adityaraj8578095389-2@okicici"

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)
user_files = {}


# HOME MENU
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
    get_user(msg.from_user.id)
    bot.reply_to(msg,
        "👋 Welcome to Any2Any Converter!\nSend file or choose below 👇",
        reply_markup=home_menu()
    )


# ADMIN COMMAND
@bot.message_handler(commands=['vip'])
def make_vip(msg):
    if msg.from_user.id != ADMIN_ID:
        return bot.reply_to(msg, "❌ Not allowed")
    try:
        uid = int(msg.text.split()[1])
        set_vip(uid, True)
        bot.reply_to(msg, f"💎 User {uid} is now VIP!")
    except:
        bot.reply_to(msg, "Usage: /vip user_id")


# VIP MENU
@bot.callback_query_handler(func=lambda c: c.data == "vip_info")
def vip_menu(call):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("₹30 Monthly 🔥", callback_data="vip_month"),
        InlineKeyboardButton("₹59 Lifetime 💎", callback_data="vip_life")
    )
    bot.send_message(call.message.chat.id,
        "💎 VIP Plans\nChoose a plan 👇\nSend Screenshot after payment!",
        reply_markup=kb)


# PAYMENT QR SENDERS
@bot.callback_query_handler(func=lambda c: c.data == "vip_month")
def pay_month(call):
    uid = call.message.chat.id
    bot.send_photo(uid, open("qr_month.png", "rb"),
        caption=f"📍 Scan & Pay ₹30\nUPI: `{UPI_ID}`\n📸 Screenshot bhejo confirm hone ke liye!"
    )

@bot.callback_query_handler(func=lambda c: c.data == "vip_life")
def pay_life(call):
    uid = call.message.chat.id
    bot.send_photo(uid, open("qr_life.png", "rb"),
        caption=f"📍 Scan & Pay ₹59\nUPI: `{UPI_ID}`\n📸 Screenshot bhejo confirm hone ke liye!"
    )


# SCREENSHOT HANDLING (Forward to Admin)
@bot.message_handler(content_types=['photo'])
def screenshot_handler(msg):
    uid = msg.from_user.id
    if uid != ADMIN_ID:
        bot.forward_message(ADMIN_ID, uid, msg.message_id)
        bot.send_message(uid, "📨 Screenshot sent for verification!\nAdmin approve karega 🙂")
        return
    bot.send_message(uid, "✔ Admin ne screenshot receive kar liya!")


# CONVERSION UI
@bot.callback_query_handler(func=lambda c: c.data == "convert_menu")
def convert_menu(call):
    bot.send_message(call.message.chat.id, "📥 Send a file!")


# HELP
@bot.callback_query_handler(func=lambda c: c.data == "help_menu")
def help_menu(call):
    bot.send_message(call.message.chat.id, "📌 Send Image or Video to convert it! Simple 🙂")


# USAGE
@bot.callback_query_handler(func=lambda c: c.data == "show_usage")
def show_usage(call):
    u = get_user(call.message.chat.id)
    bot.send_message(call.message.chat.id,
        f"📊 Used Today: {u['today_count']}/10\nVIP: {'Yes 💎' if u['is_vip'] else 'No ❌'}")


# MY FILES
@bot.callback_query_handler(func=lambda c: c.data == "my_files")
def my_files(call):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🖼 Images", callback_data="cat_image"),
        InlineKeyboardButton("🎞 Videos", callback_data="cat_video"),
        InlineKeyboardButton("🎧 Audio", callback_data="cat_audio")
    )
    bot.send_message(call.message.chat.id, "📂 Pick category", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))
def filter_files(call):
    uid = call.message.chat.id
    ftype = call.data[4:]
    items = list_files(uid, ftype)
    if not items:
        return bot.send_message(uid, "❌ No files stored yet")
    kb = InlineKeyboardMarkup()
    for f in items:
        kb.add(InlineKeyboardButton(f["name"], callback_data=f"dl_{f['file_id']}"))
    bot.send_message(uid, f"📂 Your {ftype}s:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("dl_"))
def download(call):
    bot.send_document(call.message.chat.id, call.data[3:])


# IMAGE CONVERT
@bot.message_handler(content_types=['photo'])
def img(msg):
    uid = msg.from_user.id
    if not usage_allowed(uid): return bot.reply_to(msg,"Limit Finished!")
    user_files[uid] = msg.photo[-1].file_id
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("PNG", callback_data="img_png"),
           InlineKeyboardButton("JPG", callback_data="img_jpg"))
    bot.reply_to(msg,"Format?",reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("img_"))
def convert_img(call):
    uid = call.message.chat.id
    fmt = call.data[4:]
    bot.send_message(uid,"⏳ Processing..")

    f = bot.get_file(user_files[uid])
    data = bot.download_file(f.file_path)

    inp=f"i{uid}.jpg"; out=f"o{uid}.{fmt}"
    open(inp,"wb").write(data)
    Image.open(inp).convert("RGB").save(out)

    sent=bot.send_document(uid,open(out,"rb"),reply_markup=home_menu())
    save_file(uid,sent.document.file_id,out,"image")
    update_usage(uid)
    os.remove(inp); os.remove(out)


# VIDEO
@bot.message_handler(content_types=['video'])
def video(msg):
    uid = msg.from_user.id
    user_files[uid] = msg.video.file_id
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("MP3",callback_data="v_mp3"),
           InlineKeyboardButton("MP4",callback_data="v_mp4"))
    bot.reply_to(msg,"Convert to?",reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("v_"))
def convert_vid(call):
    uid = call.message.chat.id
    fmt = call.data[2:]
    bot.send_message(uid,"🎬 Working..")
    f=bot.get_file(user_files[uid])
    data=bot.download_file(f.file_path)
    inp=f"v{uid}.mp4"; out=f"v{uid}.{fmt}"
    open(inp,"wb").write(data)
    ffmpeg.input(inp).output(out).run(overwrite_output=True)
    sent=bot.send_document(uid,open(out,"rb"),reply_markup=home_menu())
    save_file(uid,sent.document.file_id,out,"audio" if fmt=="mp3" else "video")
    update_usage(uid)
    os.remove(inp); os.remove(out)


# WEBHOOK SERVER
bot.remove_webhook()
bot.set_webhook(url=FULL_URL)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update=telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK",200

@app.route("/")
def home():
    return "Any2Any Bot Running 🚀"


if __name__=="__main__":
    app.run("0.0.0.0",int(os.environ.get("PORT",8080)))
