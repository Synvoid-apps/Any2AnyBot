@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def format_selected(call):
    chat_id = call.message.chat.id
    output_format = call.data.replace("f_", "")
    file_id = user_files.get(chat_id)

    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, "🛠 Processing your image...")

    try:
        # Download file
        file_info = bot.get_file(file_id)
        img_data = bot.download_file(file_info.file_path)

        input_path = f"input_{chat_id}.webp"
        with open(input_path, "wb") as f:
            f.write(img_data)

        # Auto format detect convert to RGB if WEBP
        img = Image.open(input_path)
        if img.mode == "RGBA":
            img = img.convert("RGB")

        quality_map = {"low": 50, "medium": 80, "high": 95}
        q = quality_map.get(user_quality.get(chat_id, "medium"), 80)

        output_path = f"converted_{chat_id}.{output_format}"
        img.save(output_path, quality=q, optimize=True)

        # Send preview first 🔥
        preview = Image.open(output_path)
        preview.thumbnail((300, 300))
        preview_path = f"preview_{chat_id}.jpg"
        preview.save(preview_path)

        with open(preview_path, "rb") as p:
            bot.send_photo(chat_id, p, caption="📌 Preview\n👇 Final file below:")

        # Send actual file
        with open(output_path, "rb") as f:
            bot.send_document(chat_id, f)

        # Cleanup
        for file in [input_path, output_path, preview_path]:
            if os.path.exists(file):
                os.remove(file)

        bot.send_message(chat_id, "🎉 Converted Successfully!")

    except Exception as e:
        bot.send_message(chat_id, f"❌ Conversion Failed:\n`{e}`")

