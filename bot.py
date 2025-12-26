import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

user_quality = {}
user_files = {}

SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'webp']

@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg,
           "👋 Welcome to Any2Any Converter!\n\n"
           "📌 Send an Image or Sticker and convert anytime!\n"
           "Commands:\n"
           "/convert — Convert Image\n"
           "/help — All features\n\n"
           "⚡ Start by sending a photo now!")

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    bot.reply_to(msg,
          "🛠 Supported Conversions:\n"
          "• JPG ↔ PNG\n"
          "• WEBP ↔ JPG/PNG\n"
          "• Telegram Sticker → PNG/JPG\n\n"
          "✨ Quality options available!")

@bot.message_handler(commands=['convert'])
def ask_file(msg):
    bot.reply_to(msg, "📥 Send the image or sticker you want to convert!")

@bot.message_handler(content_types=['photo', 'document'])
def file_received(msg):
    chat_id = msg.chat.id

    # Sticker/document image detect
    if msg.content_type == 'document':
        file_ext = msg.document.file_name.split('.')[-1].lower()
        if file_ext not in SUPPORTED_FORMATS:
            bot.reply_to(msg, "⚠️ Unsupported file type! Only images & stickers allowed.")
            return
        file_id = msg.document.file_id
    else:
        file_id = msg.photo[-1].file_id

    user_files[chat_id] = file_id
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Low", callback_data="q_low"),
        InlineKeyboardButton("Medium", callback_data="q_medium"),
        InlineKeyboardButton("High", callback_data="q_high"),
    )
    bot.reply_to(msg, "📌 Select Image Quality:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("q_"))
def quality_selected(call):
    chat_id = call.message.chat.id
    user_quality[chat_id] = call.data.replace("q_", "")

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("PNG", callback_data="f_png"),
        InlineKeyboardButton("JPG", callback_data="f_jpg"),
        InlineKeyboardButton("WEBP", callback_data="f_webp"),
    )
    bot.edit_message_text("🎯 Choose Output Format:",
                          chat_id=chat_id,
                          message_id=call.message.message_id,
                          reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def format_selected(call):
    chat_id = call.message.chat.id
    output_format = call.data.replace("f_", "")
    file_id = user_files.get(chat_id)

    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, "⏳ Converting... please wait")

    try:
        file_info = bot.get_file(file_id)
        img_data = bot.download_file(file_info.file_path)

        input_file = f"temp_{chat_id}.webp"
        with open(input_file, "wb") as f:
            f.write(img_data)

        img = Image.open(input_file).convert("RGB")

        quality_map = {
            "low": 50,
            "medium": 80,
            "high": 95
        }
        q = quality_map.get(user_quality.get(chat_id, "medium"))

        output_file = f"converted_{chat_id}.{output_format}"
        img.save(output_file, quality=q)

        with open(output_file, "rb") as f:
            bot.send_document(chat_id, f)

        os.remove(input_file)
        os.remove(output_file)

        bot.send_message(chat_id, "✨ Done! Send another image to convert.")

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Error: {e}")

bot.polling(none_stop=True)
