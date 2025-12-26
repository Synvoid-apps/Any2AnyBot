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

def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🔁 Convert Again", callback_data="convert_again"),
        InlineKeyboardButton("📌 Menu", callback_data="show_menu"),
        InlineKeyboardButton("📊 Usage", callback_data="show_usage")
    )
    return kb

@bot.message_handler(commands=['start'])
def start(msg):
    get_user(msg.from_user.id)
    bot.reply_to(msg,
    "👋 Welcome to Any2Any Converter WebApp 🌍\n"
    "📥 Send any file to convert!")

@bot.message_handler(commands=['usage'])
def usage_cmd(msg):
    user = get_user(msg.from_user.id)
    bot.reply_to(msg,
        f"📊 Used Today: {user['today_count']}/10\n"
        f"VIP: {'Yes 💎' if user['is_vip'] else 'No ❌'}")

@bot.callback_query_handler(func=lambda c:c.data=="convert_again")
def again(call):
    bot.send_message(call.message.chat.id, "📥 Send a new file!")

@bot.callback_query_handler(func=lambda c:c.data=="show_menu")
def menu(call):
    bot.send_message(call.message.chat.id, "/start\n/usage")

@bot.callback_query_handler(func=lambda c:c.data=="show_usage")
def show(call):
    usage_cmd(call.message)

# ================= IMAGE PROCESSING =================

@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    uid = msg.from_user.id
    if not usage_allowed(uid):
        return bot.reply_to(msg, "❌ Daily limit over!")

    file_id = msg.photo[-1].file_id
    user_files[uid] = file_id

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("PNG", callback_data="img_png"),
        InlineKeyboardButton("JPG", callback_data="img_jpg")
    )
    bot.reply_to(msg, "Select Output Format:", reply_markup=kb)

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

    bot.send_document(uid, open(out, "rb"), caption="✔ Done!", reply_markup=main_menu())
    update_usage(uid)
    os.remove(inp); os.remove(out)

# ================= VIDEO =================

@bot.message_handler(content_types=['video'])
def handle_video(msg):
    uid=msg.from_user.id
    user_files[uid]=msg.video.file_id

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🎥 MP4", callback_data="v_mp4"),
        InlineKeyboardButton("🎧 MP3", callback_data="v_mp3")
    )
    bot.reply_to(msg, "Select Mode:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("v_"))
def convert_video(call):
    uid=call.message.chat.id
    mode=call.data[2:]
    bot.send_message(uid,"🎬 Working…")

    file = bot.get_file(user_files[uid])
    data = bot.download_file(file.file_path)

    inp = f"v_{uid}.mp4"
    out = f"o_{uid}.{'mp3' if mode=='mp3' else 'mp4'}"

    open(inp,"wb").write(data)

    if mode == "mp3":
        ffmpeg.input(inp).output(out, acodec="mp3").run(overwrite_output=True)
    else:
        ffmpeg.input(inp).output(out).run(overwrite_output=True)

    bot.send_document(uid, open(out, "rb"), caption="✔ Done!", reply_markup=main_menu())
    update_usage(uid)
    os.remove(inp); os.remove(out)

# ================= WEBHOOK SERVER =================

bot.remove_webhook()
bot.set_webhook(url=FULL_URL)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "Bot Running!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8080)))
