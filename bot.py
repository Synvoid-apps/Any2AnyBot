import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from dotenv import load_dotenv
from PIL import Image
import ffmpeg
import zipfile
from db import get_user, update_usage, usage_allowed

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

user_quality = {}
user_files = {}
batch_list = {}

# --- USAGE COMMAND ---
@bot.message_handler(commands=['usage'])
def show_usage(msg):
    user = get_user(msg.from_user.id)
    bot.reply_to(msg,
        f"📊 Today Used: {user['today_count']}/10\n"
        f"VIP: {'Yes 💎' if user['is_vip'] else 'No ❌'}"
    )


@bot.message_handler(commands=['start'])
def start(msg):
    chat_id = msg.chat.id
    get_user(chat_id)
    bot.reply_to(msg,
        "👋 Welcome to Any2Any Converter Phase-5 🚀\n"
        "• Batch Convert\n"
        "• VIP System\n"
        "• Usage Limits\n\n"
        "Send any file to begin!")


# ================= IMAGE + BATCH =================
@bot.message_handler(content_types=['photo'])
def photo_file(msg):
    chat_id = msg.chat.id
    if not usage_allowed(chat_id):
        return bot.reply_to(msg,
            "⛔ Limit 10/10 reached!\nUpgrade VIP 🔥")

    file_id = msg.photo[-1].file_id
    batch_list.setdefault(chat_id, []).append(file_id)

    if len(batch_list[chat_id]) >= 2:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("Batch Convert ZIP", callback_data="batch_zip"),
            InlineKeyboardButton("Single Convert", callback_data="single_convert")
        )
        bot.reply_to(msg, "📌 Choose:", reply_markup=markup)
    else:
        bot.reply_to(msg,
            "📌 Send 1 more file for batch OR use /convert for single")


@bot.callback_query_handler(func=lambda c: c.data == "single_convert")
def single_process(call):
    chat_id = call.message.chat.id
    user_files[chat_id] = batch_list[chat_id][-1]
    batch_list[chat_id].clear()

    # Ask quality
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Low", callback_data="q_low"),
        InlineKeyboardButton("Medium", callback_data="q_medium"),
        InlineKeyboardButton("High", callback_data="q_high")
    )
    bot.edit_message_text("🎚 Select Quality:", chat_id=chat_id,
                          message_id=call.message.message_id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "batch_zip")
def batch_convert(call):
    chat_id = call.message.chat.id
    files = batch_list.get(chat_id, [])

    bot.send_message(chat_id, "🛠 Batch Converting…")
    zip_path = f"batch_{chat_id}.zip"

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for idx, fid in enumerate(files):
            file_info = bot.get_file(fid)
            data = bot.download_file(file_info.file_path)

            img_path = f"b_{chat_id}_{idx}.jpg"
            with open(img_path, "wb") as f:
                f.write(data)

            zipf.write(img_path)
            os.remove(img_path)

    with open(zip_path, "rb") as z:
        bot.send_document(chat_id, z, caption="📦 Batch Ready!")

    os.remove(zip_path)
    batch_list[chat_id].clear()
    update_usage(chat_id)


# ========== IMAGE CONVERT (After Phase-4) ==========
# KEEP Phase-4 image conversion code exactly here (convert_image + quality handlers)
# + add:
# update_usage(chat_id)
# after successful conversion


# ========== VIDEO CONVERT (After Phase-4) ==========
# KEEP Phase-4 video handlers exactly here too
# + add update_usage(chat_id)
# after successful conversion


bot.polling(none_stop=True)
