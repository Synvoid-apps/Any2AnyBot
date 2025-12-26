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

SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'webp']


# ================= START COMMAND =================
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg,
           "👋 Welcome to Any2Any Converter!\n\n"
           "📌 Send an Image, Sticker or Video and I will convert it!\n"
           "Use /convert to begin.\n\n"
           "⚙️ Phase-3 Version: Image + Video Support 🔥")


@bot.message_handler(commands=['help'])
def help_cmd(msg):
    bot.reply_to(msg,
          "🛠 Supported:\n"
          "• Image: PNG, JPG, WEBP\n"
          "• Sticker to Image\n"
          "• Video: MP4 conversion + MP3 extract\n\n"
          "✨ More formats coming soon!")


@bot.message_handler(commands=['convert'])
def ask_file(msg):
    bot.reply_to(msg, "📥 Send any image/sticker/video to convert!")


# ============ IMAGE/STICKER RECEIVED ============
@bot.message_handler(content_types=['photo', 'document'])
def image_received(msg):
    chat_id = msg.chat.id

    if msg.content_type == 'document':
        file_ext = msg.document.file_name.split('.')[-1].lower()
        if file_ext not in SUPPORTED_FORMATS:
            bot.reply_to(msg, "⚠️ Only images/stickers supported here.\nTry sending a photo instead.")
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
    bot.reply_to(msg, "📌 Select Quality:", reply_markup=markup)


# ============ IMAGE QUALITY SELECTED ============
@bot.callback_query_handler(func=lambda c: c.data.startswith("q_"))
def quality_selected(call):
    chat_id = call.message.chat.id
    user_quality[chat_id] = call.data.replace("q_", "")

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("PNG", callback_data="f_png"),
        InlineKeyboardButton("JPG", callback_data="f_jpg"),
        InlineKeyboardButton("WEBP", callback_data="f_webp")
    )
    bot.edit_message_text("🎯 Choose Output Format:",
                          chat_id=chat_id,
                          message_id=call.message.message_id,
                          reply_markup=markup)


# ============ IMAGE CONVERSION ============
@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def convert_image(call):
    chat_id = call.message.chat.id
    output_format = call.data.replace("f_", "")
    file_id = user_files.get(chat_id)

    bot.send_message(chat_id, "🛠 Processing your image…")

    try:
        file_info = bot.get_file(file_id)
        img_data = bot.download_file(file_info.file_path)

        input_path = f"input_{chat_id}.webp"
        with open(input_path, "wb") as f:
            f.write(img_data)

        img = Image.open(input_path)
        if img.mode == "RGBA":
            img = img.convert("RGB")

        quality = user_quality.get(chat_id, "medium")
        q_map = {"low": 50, "medium": 80, "high": 95}
        q = q_map.get(quality, 80)

        output_path = f"output_{chat_id}.{output_format}"
        img.save(output_path, quality=q, optimize=True)

        preview = Image.open(output_path)
        preview.thumbnail((300, 300))
        preview_path = f"preview_{chat_id}.jpg"
        preview.save(preview_path)

        with open(preview_path, "rb") as p:
            bot.send_photo(chat_id, p, caption="📌 Preview")

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬇ Download File", callback_data="send_img"))

        with open(output_path, "rb") as f:
            bot.send_document(chat_id, f, caption="✨ Done!", reply_markup=markup)

        os.remove(input_path)
        os.remove(output_path)
        os.remove(preview_path)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Error:\n{e}")


# ================= VIDEO RECEIVED =================
@bot.message_handler(content_types=['video'])
def video_received(msg):
    chat_id = msg.chat.id
    file_id = msg.video.file_id
    user_files[chat_id] = file_id

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Low", callback_data="vq_low"),
        InlineKeyboardButton("Medium", callback_data="vq_medium"),
        InlineKeyboardButton("High", callback_data="vq_high")
    )
    bot.reply_to(msg, "📌 Select Video Quality:", reply_markup=markup)


# ============ VIDEO QUALITY SELECTED ============
@bot.callback_query_handler(func=lambda c: c.data.startswith("vq_"))
def video_quality(call):
    chat_id = call.message.chat.id
    user_quality[chat_id] = call.data.replace("vq_", "")

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎥 MP4", callback_data="vt_mp4"),
        InlineKeyboardButton("🎧 MP3", callback_data="vt_mp3")
    )
    bot.edit_message_text("🎯 Convert To:",
                          chat_id=chat_id,
                          message_id=call.message.message_id,
                          reply_markup=markup)


# ============ VIDEO CONVERT =============
@bot.callback_query_handler(func=lambda c: c.data.startswith("vt_"))
def convert_video(call):
    chat_id = call.message.chat.id
    output_type = call.data.replace("vt_", "")
    file_id = user_files.get(chat_id)

    bot.send_message(chat_id, "⏳ Converting your video…")

    try:
        file_info = bot.get_file(file_id)
        vid_data = bot.download_file(file_info.file_path)

        input_path = f"input_{chat_id}.mp4"
        with open(input_path, "wb") as f:
            f.write(vid_data)

        output_path = f"output_{chat_id}.{output_type}"

        q = {"low": "360", "medium": "720", "high": "1080"}.get(user_quality.get(chat_id), "720")

        if output_type == "mp4":
            ffmpeg.input(input_path)\
                  .filter('scale', -1, q)\
                  .output(output_path, vcodec="libx264", acodec="aac")\
                  .run(overwrite_output=True)
        else:
            ffmpeg.input(input_path)\
                  .output(output_path, acodec="mp3")\
                  .run(overwrite_output=True)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬇ Download File", callback_data="send_vid"))

        with open(output_path, "rb") as vid:
            bot.send_document(chat_id, vid, caption="🎉 Converted!", reply_markup=markup)

        os.remove(input_path)
        os.remove(output_path)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Video Convert Error:\n{e}")


# ================= BOT RUN =================
bot.polling(none_stop=True)
