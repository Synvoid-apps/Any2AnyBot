import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from dotenv import load_dotenv
from flask import Flask, request
from PIL import Image
import ffmpeg
import zipfile
from db import update_usage, usage_allowed, get_user

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
FULL_URL = f"{WEBHOOK_URL}/{TOKEN}"

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)

user_files = {}
batch_list = {}
video_mode = {}
quality = {}

# ---- MAIN HOME INLINE MENU ---- #
def home_menu():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🔁 Convert File", callback_data="convert_menu"),
        InlineKeyboardButton("📦 My Files", callback_data="my_files")
    )
    kb.add(
        InlineKeyboardButton("📊 Usage", callback_data="show_usage"),
        InlineKeyboardButton("💎 Upgrade VIP", callback_data="vip_info")
    )
    kb.add(
        InlineKeyboardButton("ℹ Help", callback_data="help_menu")
    )
    return kb

@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id
    get_user(uid)
    bot.reply_to(msg,
        "👋 Welcome to Any2Any WebApp 🌍\n"
        "🤖 Send any file OR choose from menu below👇",
        reply_markup=home_menu()
    )

@bot.callback_query_handler(func=lambda c: c.data == "convert_menu")
def convert_menu(call):
    bot.send_message(call.message.chat.id, "📥 Send a file to start converting!")

@bot.callback_query_handler(func=lambda c: c.data == "help_menu")
def help_menu(call):
    bot.send_message(call.message.chat.id,
        "🛠 Supported Formats:\n"
        "• Images (PNG/JPG/WebP)\n"
        "• Video → MP3\n"
        "• Batch ZIP soon!\n"
        "Just send file 🙂"
    )

@bot.callback_query_handler(func=lambda c: c.data == "my_files")
def my_files(call):
    bot.send_message(call.message.chat.id, 
        "📦 Cloud Storage coming in Phase-6.2 ⚡")

@bot.callback_query_handler(func=lambda c: c.data == "vip_info")
def vip_info(call):
    bot.send_message(call.message.chat.id,
        "💎 VIP Coming Soon:\n"
        "✔ Unlimited Conversions\n"
        "✔ Extra Formats\n"
        "✔ Fastest Processing\n"
        "Stay tuned 🔥"
    )

@bot.callback_query_handler(func=lambda c:c.data=="show_usage")
def show_usage(call):
    user = get_user(call.message.chat.id)
    bot.send_message(call.message.chat.id,
        f"📊 Used Today: {user['today_count']}/10\n"
        f"VIP: {'Yes 💎' if user['is_vip'] else 'No ❌'}"
    )

# ===== IMAGE HANDLING ===== #
@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    uid = msg.from_user.id

    if not usage_allowed(uid):
        return bot.reply_to(msg, "❌ Limit reached! VIP coming soon 💎")

    file_id = msg.photo[-1].file_id
    user_files[uid] = file_id

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("PNG", callback_data="img_png"),
        InlineKeyboardButton("JPG", callback_data="img_jpg")
    )
    bot.reply_to(msg, "🎯 Select output format:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("img_"))
def convert_img(call):
    uid = call.message.chat.id
    fmt = call.data[4:]

    bot.send_message(uid, "⏳ Processing image…")

    f = bot.get_file(user_files[uid])
    data = bot.download_file(f.file_path)

    inp = f"in_{uid}.jpg"
    out = f"out_{uid}.{fmt}"

    open(inp, "wb").write(data)
    img = Image.open(inp).convert("RGB")
    img.save(out, quality=85, optimize=True)

    bot.send_document(uid, open(out, "rb"), reply_markup=home_menu())
    update_usage(uid)
    os.remove(inp); os.remove(out)

# ===== VIDEO HANDLING ===== #
@bot.message_handler(content_types=['video'])
def handle_video(msg):
    uid = msg.from_user.id
    user_files[uid] = msg.video.file_id

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🎧 MP3", callback_data="v_mp3"),
        InlineKeyboardButton("🎥 MP4", callback_data="v_mp4")
    )
    bot.reply_to(msg, "🎬 Select output format:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("v_"))
def convert_video(call):
    uid = call.message.chat.id
    mode = call.data[2:]

    bot.send_message(uid, "🎞 Converting…")

    f = bot.get_file(user_files[uid])
    data = bot.download_file(f.file_path)

    inp = f"in_{uid}.mp4"
    out = f"out_{uid}.{'mp3' if mode=='mp3' else 'mp4'}"

    open(inp,"wb").write(data)
    if mode == "mp3":
        ffmpeg.input(inp).output(out, acodec="mp3").run(overwrite_output=True)
    else:
        ffmpeg.input(inp).output(out).run(overwrite_output=True)

    bot.send_document(uid, open(out, "rb"), reply_markup=home_menu())
    update_usage(uid)
    os.remove(inp); os.remove(out)


# ===== WEBHOOK SERVER ===== #
bot.remove_webhook()
bot.set_webhook(url=FULL_URL)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "Bot Running! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
