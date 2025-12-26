import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = 6141075929  # YOU ARE ADMIN 😎
UPI_ID = "adityaraj8578095389-2@okicici"

DAILY_LIMIT = 10
MONTHLY_DAYS = 30
