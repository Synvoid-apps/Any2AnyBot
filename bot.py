import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from dotenv import load_dotenv
from PIL import Image
import ffmpeg

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

user_quality = {}
user_files = {}
user_convert_type = {}
user_video_mode = {}

SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'webp']

# ------------------- START -------------------
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg,
        "👋 Welcome to Any2Any Converter!\n\n"
        "📌 Send Image / Sticker / Video to convert\n"
        "⚙️ Phase-4: Compression + VIP System Added 🔥\n\n"
        "Commands:\n"
        "/convert — Convert any file\n"
        "/vip — Unlock premium features\n"
        "/help — Supported formats")


@bot.message_handler(commands=['help'])
def help_cmd(msg):
    bot.reply_to(msg,
        "🛠 Supported:\n"
        "• Image: PNG, JPG, WEBP\n"
        "• Sticker → Image\n"
        "• Video: MP4 + MP3\n"
        "• Video Compression 🔥\n\n"
        "More formats coming soon!")


@bot.message_handler(commands=['vip'])
def vip_info(msg):
    bot.reply_to(msg,
        "💎 VIP Features:\n"
        "✔ Unlimited conversions\n"
        "✔ Fast speed\n"
        "✔ 500MB video limit\n"
        "✔ Batch conversion\n\n"
        "🔒 UPI Subscription Coming Soon…")


@bot.message_handler(commands=['convert'])
def ask_file(msg):
    bot.reply_to(msg, "📥 Send your file to convert…")


# ------------------- IMAGE HANDLER -------------------
@bot.message_handler(content_types=['photo', 'document'])
def image_received(msg):
    chat_id = msg.chat.id

    if msg.content_types == 'document':
        file_ext = msg.document.file_name.split('.')[-1].lower()
        if file_ext not in SUPPORTED_FORMATS:
            bot.reply_to(msg, "⚠️ Unsupported file type.")
            return
        file_id = msg.document.file_id
    else:
        file_id = msg.photo[-1].file_id

    user_files[chat_id] = file_id

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Low", callback_data="q_low"),
        InlineKeyboardButton("Medium", callback_data="q_medium"),
        InlineKeyboardButton("High", callback_data="q_high")
    )
    bot.reply_to(msg, "📌 Choose Quality:", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("q_"))
def choose_image_quality(call):
    chat_id = call.message.chat.id
    user_quality[chat_id] = call.data.replace("q_", "")

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("PNG", callback_data="f_png"),
        InlineKeyboardButton("JPG", callback_data="f_jpg"),
        InlineKeyboardButton("WEBP", callback_data="f_webp"),
    )
    bot.edit_message_text("🎯 Select Output Format:",
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def convert_image(call):
    chat_id = call.message.chat.id
    output_format = call.data.replace("f_", "")
    file_id = user_files.get(chat_id)

    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, "🛠 Converting image…")

    try:
        file_info = bot.get_file(file_id)
        img_data = bot.download_file(file_info.file_path)

        input_path = f"input_{chat_id}.webp"
        with open(input_path, "wb") as f:
            f.write(img_data)

        img = Image.open(input_path)
        if img.mode == "RGBA":
            img = img.convert("RGB")

        q_map = {"low": 50, "medium": 80, "high": 95}
        q = q_map.get(user_quality.get(chat_id), 80)

        output_path = f"output_{chat_id}.{output_format}"
        img.save(output_path, optimize=True, quality=q)

        # Preview
        preview_path = f"preview_{chat_id}.jpg"
        p_img = Image.open(output_path)
        p_img.thumbnail((300, 300))
        p_img.save(preview_path)

        with open(preview_path, "rb") as p:
            bot.send_photo(chat_id, p, caption="📌 Preview:")

        # Download Button
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬇ Download File", callback_data="get_img"))

        with open(output_path, "rb") as f:
            bot.send_document(chat_id, f, caption="✨ Done!", reply_markup=markup)

        os.remove(input_path)
        os.remove(output_path)
        os.remove(preview_path)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {e}")


# ------------------- VIDEO HANDLER -------------------
@bot.message_handler(content_types=['video'])
def video_received(msg):
    chat_id = msg.chat.id
    user_files[chat_id] = msg.video.file_id

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Normal Convert 🎥", callback_data="vm_normal"),
        InlineKeyboardButton("Compress Video 📦", callback_data="vm_compress"),
        InlineKeyboardButton("MP3 Extract 🎧", callback_data="vm_mp3")
    )
    bot.reply_to(msg, "🎛 Processing Mode:", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("vm_"))
def video_mode(call):
    chat_id = call.message.chat.id
    user_video_mode[chat_id] = call.data.replace("vm_", "")

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Low", callback_data="vq_low"),
        InlineKeyboardButton("Medium", callback_data="vq_medium"),
        InlineKeyboardButton("High", callback_data="vq_high"),
    )
    bot.edit_message_text("📌 Select Video Quality:",
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("vq_"))
def convert_video(call):
    chat_id = call.message.chat.id
    user_quality[chat_id] = call.data.replace("vq_", "")
    file_id = user_files.get(chat_id)
    mode = user_video_mode.get(chat_id)

    bot.send_message(chat_id, "⏳ Video processing started…")

    try:
        file_info = bot.get_file(file_id)
        data = bot.download_file(file_info.file_path)

        input_vid = f"vid_{chat_id}.mp4"
        with open(input_vid, "wb") as f:
            f.write(data)

        quality_res = {"low": "360", "medium": "720", "high": "1080"}
        res = quality_res.get(user_quality.get(chat_id), "720")

        if mode == "mp3":
            output = f"out_{chat_id}.mp3"
            ffmpeg.input(input_vid).output(output, acodec="mp3").run(overwrite_output=True)

        elif mode == "compress":
            output = f"out_{chat_id}.mp4"
            ffmpeg.input(input_vid)\
                .filter('scale', -1, res)\
                .output(output, vcodec="libx264", crf=30, preset="veryfast")\
                .run(overwrite_output=True)

        else:
            output = f"out_{chat_id}.mp4"
            ffmpeg.input(input_vid)\
                .filter('scale', -1, res)\
                .output(output, vcodec="libx264", acodec="aac")\
                .run(overwrite_output=True)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬇ Download File", callback_data="get_vid"))

        with open(output, "rb") as v:
            bot.send_document(chat_id, v, caption="🎉 Done!", reply_markup=markup)

        os.remove(input_vid)
        os.remove(output)

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Video Error: {e}")


# ------------------- DOWNLOAD BUTTON FIX -------------------
@bot.callback_query_handler(func=lambda c: c.data == "get_img")
def d_img(call):
    bot.answer_callback_query(call.id, "Downloading…")


@bot.callback_query_handler(func=lambda c: c.data == "get_vid")
def d_vid(call):
    bot.answer_callback_query(call.id, "Downloading…")


# ------------------- BOT RUN -------------------
bot.polling(none_stop=True)
