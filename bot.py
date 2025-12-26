import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from dotenv import load_dotenv
from PIL import Image
import ffmpeg
import zipfile
from db import update_usage, usage_allowed, get_user

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

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
        "👋 Welcome to Any2Any Converter v6.0\n"
        "📌 Send any File to Convert!\n"
        "🎯 Batch + VIP + Limits Enabled 🔥\n"
        "Try /help")

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    bot.reply_to(msg,
        "🛠 Supported:\n"
        "• Images: PNG JPG WEBP\n"
        "• Stickers → Images\n"
        "• Video → MP4 / MP3\n"
        "• Batch Convert ZIP\n\n"
        "Check Limits: /usage")

@bot.message_handler(commands=['usage'])
def usage_cmd(msg):
    user = get_user(msg.from_user.id)
    bot.reply_to(msg,
        f"📊 Used Today: {user['today_count']}/10\n"
        f"VIP: {'Yes 💎' if user['is_vip'] else 'No ❌'}")

@bot.callback_query_handler(func=lambda c:c.data=="show_menu")
def menu_screen(call):
    bot.send_message(call.message.chat.id, "/start\n/help\n/usage")

@bot.callback_query_handler(func=lambda c:c.data=="convert_again")
def again(call):
    bot.send_message(call.message.chat.id, "📥 Send a new file!")

@bot.callback_query_handler(func=lambda c:c.data=="show_usage")
def show_u(call):
    usage_cmd(call.message)

# ===== IMAGE + STICKER =====
@bot.message_handler(content_types=['photo'])
def photo_msg(msg):
    uid = msg.from_user.id
    if not usage_allowed(uid):
        return bot.reply_to(msg, "❌ Limit over! VIP unlock soon!")

    file_id = msg.photo[-1].file_id
    batch_list.setdefault(uid, []).append(file_id)

    if len(batch_list[uid]) >= 2:
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("Batch Convert", callback_data="batch"),
            InlineKeyboardButton("Single Convert", callback_data="single")
        )
        bot.reply_to(msg, "📌 Choose:", reply_markup=kb)
    else:
        bot.reply_to(msg, "📥 Send 1 more for batch or /convert")

@bot.callback_query_handler(func=lambda c:c.data=="single")
def handle_single(call):
    uid = call.message.chat.id
    user_files[uid] = batch_list[uid][-1]
    batch_list[uid].clear()
    ask_quality(call)

def ask_quality(call):
    uid = call.message.chat.id
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("Low", callback_data="q_low"),
        InlineKeyboardButton("Medium", callback_data="q_medium"),
        InlineKeyboardButton("High", callback_data="q_high")
    )
    bot.send_message(uid, "🎚 Select Quality:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("q_"))
def set_q(call):
    uid = call.message.chat.id
    quality[uid] = call.data[2:]
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("PNG", callback_data="img_png"),
        InlineKeyboardButton("JPG", callback_data="img_jpg")
    )
    bot.send_message(uid, "🎯 Output Format:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("img_"))
def convert_img(call):
    uid = call.message.chat.id
    fmt = call.data[4:]
    file_id = user_files.get(uid)

    bot.send_message(uid, "⏳ Processing image…")

    f = bot.get_file(file_id)
    data = bot.download_file(f.file_path)

    inp = f"in_{uid}.jpg"
    out = f"out_{uid}.{fmt}"

    open(inp, "wb").write(data)
    img = Image.open(inp).convert("RGB")

    q = {"low":50,"medium":80,"high":95}[quality.get(uid,"medium")]
    img.save(out, quality=q, optimize=True)

    bot.send_document(uid, open(out,"rb"), caption="✨ Done!", reply_markup=main_menu())

    update_usage(uid)
    os.remove(inp); os.remove(out)

# ===== BATCH ZIP =====
@bot.callback_query_handler(func=lambda c:c.data=="batch")
def make_zip(call):
    uid = call.message.chat.id
    bot.send_message(uid,"📦 Creating ZIP…")
    zp=f"b_{uid}.zip"

    with zipfile.ZipFile(zp,'w') as z:
        for i,fid in enumerate(batch_list[uid]):
            f = bot.get_file(fid)
            d = bot.download_file(f.file_path)
            p=f"tmp_{uid}_{i}.jpg"
            open(p,"wb").write(d)
            z.write(p)
            os.remove(p)

    batch_list[uid].clear()
    bot.send_document(uid, open(zp,"rb"), caption="✔ Batch Ready!",reply_markup=main_menu())
    update_usage(uid)
    os.remove(zp)

# ===== VIDEO =====
@bot.message_handler(content_types=['video'])
def vid(msg):
    uid=msg.from_user.id
    if not usage_allowed(uid):
        return bot.reply_to(msg,"❌ Daily limit reached!")

    user_files[uid]=msg.video.file_id
    kb=InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🎥 MP4",callback_data="v_mp4"),
        InlineKeyboardButton("🎧 MP3",callback_data="v_mp3"),
        InlineKeyboardButton("📦 Compress",callback_data="v_zip")
    )
    bot.reply_to(msg,"🎛 Mode:",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("v_"))
def do_video(call):
    uid=call.message.chat.id
    mode=call.data[2:]
    bot.send_message(uid,"🎬 Working…")

    f=bot.get_file(user_files[uid])
    d=bot.download_file(f.file_path)
    inp=f"v_{uid}.mp4"; open(inp,"wb").write(d)

    if mode=="mp3":
        out=f"a_{uid}.mp3"
        ffmpeg.input(inp).output(out,acodec="mp3").run(overwrite_output=True)
    elif mode=="zip":
        out=f"c_{uid}.mp4"
        ffmpeg.input(inp).output(out,vcodec="libx264",crf=30).run(overwrite_output=True)
    else:
        out=f"m_{uid}.mp4"
        ffmpeg.input(inp).output(out).run(overwrite_output=True)

    bot.send_document(uid,open(out,"rb"),caption="✔ Video Ready!",reply_markup=main_menu())
    update_usage(uid)
    os.remove(inp); os.remove(out)

bot.polling(none_stop=True)
