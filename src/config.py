import os

from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Notion
NOTION_API_KEY = os.getenv("NOTION_API_KEY")

# APIs marché
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
EODHD_API_KEY = os.getenv("EODHD_API_KEY")

# Validation au démarrage : plante tôt si une clé manque
REQUIRED_VARS = {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "GROQ_API_KEY": GROQ_API_KEY,
    "NOTION_API_KEY": NOTION_API_KEY,
    "FINNHUB_API_KEY": FINNHUB_API_KEY,
}

for name, value in REQUIRED_VARS.items():
    if not value:
        raise ValueError(f"Variable d'environnement manquante : {name}")