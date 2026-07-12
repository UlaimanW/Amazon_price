import os

from dotenv import load_dotenv


load_dotenv()


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WISHLIST_URL = os.getenv("WISHLIST_URL")


def validate_config():
    missing_values = []

    if not TELEGRAM_BOT_TOKEN:
        missing_values.append("TELEGRAM_BOT_TOKEN")

    if not TELEGRAM_CHAT_ID:
        missing_values.append("TELEGRAM_CHAT_ID")

    if not WISHLIST_URL:
        missing_values.append("WISHLIST_URL")

    if missing_values:
        missing_text = ", ".join(missing_values)
        raise ValueError(
            f"Missing configuration values in .env: {missing_text}"
        )